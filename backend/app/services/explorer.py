from __future__ import annotations

import hashlib
import logging
import re
from html import unescape
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from playwright.async_api import BrowserContext, Page, async_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import Analysis, AnalysisStatus, EvidenceItem
from app.services.analyzer import ReportGenerator
from app.services.events import EventService
from app.services.page_signals import extract_page_signals
from app.services.site_probes import run_site_probes
from app.services.url_policy import assert_public_resolution, normalize_public_url

logger = logging.getLogger(__name__)

# Header names worth retaining for technology and security inference.
_INTERESTING_HEADERS = (
    "server", "x-powered-by", "via", "cf-ray", "x-vercel-id", "x-amz-cf-id", "x-served-by",
    "content-security-policy", "strict-transport-security", "x-frame-options", "x-nextjs-cache",
)
# Lowercased framework/library markers scanned in page HTML.
_HTML_MARKERS = (
    "__next_data__", "/_next/", "data-reactroot", "reactroot", "__vue__", "data-v-", "ng-version",
    "___gatsby", "__nuxt", "/_nuxt/", "astro-island", "__remixcontext", "svelte-", "/graphql",
    "__typename", "apollo", "socket.io", "websocket", "stripe", "cdn-cgi",
    # CMS / commerce platform markers — path/attribute-specific to avoid matching
    # brand names that merely appear in page copy (e.g. customer logos).
    "/wp-content/", "/wp-includes/", "/wp-json/", "wc-ajax", "wc_add_to_cart", "/cdn/shop/",
    "shopify.loadfeatures", "data-wf-", "wf-page", "data-wix", "/ghost/api/", "drupal-settings-json",
    "option=com_content", "/on/demandware.store", "data-framer-", "hs-scripts.com",
)


def _select_headers(headers: dict) -> dict[str, str]:
    lowered = {str(k).lower(): str(v) for k, v in headers.items()}
    return {name: lowered[name][:200] for name in _INTERESTING_HEADERS if name in lowered}


def extract_html_signals(html: str, base_url: str) -> tuple[list[str], list[str], str | None]:
    """Return (script srcs, matched markers, generator) from raw HTML."""
    lowered = html.lower()
    scripts = [urljoin(base_url, src) for src in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, flags=re.I)]
    markers = [m for m in _HTML_MARKERS if m in lowered]
    generator_match = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']', html, flags=re.I)
    generator = generator_match.group(1) if generator_match else None
    return scripts[:40], markers, generator


def extract_visible_text(html: str, limit: int = 20_000) -> str:
    """Extract readable page copy without letting scripts/styles become evidence."""
    cleaned = re.sub(
        r"<(script|style|noscript|template|svg)[^>]*>.*?</\1>",
        " ", html, flags=re.I | re.S,
    )
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    text = re.sub(r"\s+", " ", unescape(cleaned)).strip()
    return text[:limit]


def extract_link_paths(html: str, base_url: str, origin_host: str | None) -> list[str]:
    """Same-host link paths reachable from this page.

    The link graph is evidence in its own right: a nav link to /pricing shows the product
    exposes a pricing surface whether or not we fetch that page. This is what lets a
    single-page (non-deep-crawl) analysis still infer features from observed structure.
    """
    paths: list[str] = []
    seen: set[str] = set()
    for href in re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html, flags=re.I)[:400]:
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        parts = urlsplit(urljoin(base_url, href))
        if parts.scheme not in ("http", "https"):
            continue
        if origin_host and (parts.hostname or "").lower() != origin_host.lower():
            continue  # third-party links say nothing about this product's surface
        path = parts.path or "/"
        if path not in seen:
            seen.add(path)
            paths.append(path)
        if len(paths) >= 80:
            break
    return paths


class AnalysisExplorer:
    """Controlled public-surface explorer. It never handles user credentials or downloads."""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        events: EventService,
        artifact_root: Path | None = None,
        report_generator: ReportGenerator | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._events = events
        self._artifact_root = artifact_root or Path(settings.artifact_root)
        self._artifacts_disabled = False
        self._reports = report_generator or ReportGenerator(settings, session_factory)

    async def process(self, analysis_id: str, *, raise_on_failure: bool = False) -> None:
        analysis = await self._load_analysis(analysis_id)
        if analysis is None or analysis.status in {AnalysisStatus.CANCELLED, AnalysisStatus.COMPLETED}:
            return
        try:
            await self._set_status(analysis_id, AnalysisStatus.RUNNING, 5)
            evidence_mode = analysis.options.get("evidence_mode", "crawl")
            if evidence_mode == "har":
                await self._events.append(
                    analysis_id,
                    "har.processing",
                    "Reconstructing the product from sanitized browser-session evidence",
                )
            else:
                if self._settings.browser_exploration:
                    await self._events.append(analysis_id, "browser.opening", "Opening isolated browser context")
                await assert_public_resolution(analysis.target_url)
                await self._explore(analysis)
            if await self._is_cancelled(analysis_id):
                return
            if evidence_mode != "har":
                await self._run_site_probes(analysis)
            await self._set_status(analysis_id, AnalysisStatus.GENERATING_REPORT, 92)
            await self._events.append(
                analysis_id, "report.generating", "Inferring architecture and synthesizing the report"
            )
            report = await self._reports.generate(analysis)
            await self._events.append(
                analysis_id,
                "report.ready",
                "Report generated",
                {
                    "report_id": report.id,
                    "overall_confidence": report.overall_confidence,
                    "features": report.features_count,
                },
            )
            await self._set_status(analysis_id, AnalysisStatus.COMPLETED, 100)
            await self._events.append(analysis_id, "analysis.completed", "Exploration completed successfully")
        except Exception as error:  # worker boundary: persist a safe failure before acknowledging a job
            logger.exception("analysis worker failed", extra={"analysis_id": analysis_id})
            await self._mark_failed(analysis_id, error)
            if raise_on_failure:
                raise

    async def _explore(self, analysis: Analysis) -> None:
        max_pages = min(int(analysis.options.get("max_pages", self._settings.max_pages)), self._settings.max_pages)
        deep_crawl = bool(analysis.options.get("deep_crawl", False))
        capture_network = bool(analysis.options.get("capture_network_requests", True))
        origin_host = urlsplit(analysis.target_url).hostname
        pending = [analysis.target_url]
        visited: set[str] = set()
        network_signals: list[dict[str, str | int]] = []
        self._ensure_artifact_root()

        if self._settings.browser_exploration:
            try:
                await self._explore_with_browser(analysis, max_pages, deep_crawl, capture_network, origin_host, pending, visited, network_signals)
                return
            except Exception as error:
                # A missing/blocked browser binary must not abort the analysis; fall back to a
                # lightweight HTTP fetch so evidence is still collected and a report is produced.
                logger.warning("browser exploration unavailable, using HTTP fallback: %s", error)
                await self._events.append(
                    analysis.id, "browser.fallback", "Browser unavailable; using lightweight HTTP exploration"
                )
                visited.clear()
                network_signals.clear()
        else:
            if self._settings.browser_capture_url and self._settings.capture_secret:
                try:
                    await self._explore_with_remote_browser(
                        analysis, max_pages, deep_crawl, origin_host, network_signals
                    )
                    return
                except Exception as error:
                    logger.warning("serverless browser capture unavailable, using HTTP fallback: %s", error)
                    await self._events.append(
                        analysis.id, "browser.fallback",
                        "Serverless browser unavailable; using lightweight HTTP exploration",
                    )
                    network_signals.clear()
            else:
                # Configured browserless: skip straight to HTTP instead of waiting
                # for Playwright to fail without an installed Chromium binary.
                await self._events.append(
                    analysis.id, "browser.fallback", "Using lightweight HTTP exploration"
                )

        await self._explore_with_http(analysis, max_pages, deep_crawl, origin_host, [analysis.target_url], visited, network_signals)

    async def _explore_with_remote_browser(
        self,
        analysis: Analysis,
        max_pages: int,
        deep_crawl: bool,
        origin_host: str | None,
        network_signals: list[dict[str, str | int]],
    ) -> None:
        await self._events.append(
            analysis.id, "browser.starting", "Starting serverless Chromium exploration"
        )
        timeout = httpx.Timeout(min(self._settings.max_analysis_seconds, 120), connect=20)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self._settings.browser_capture_url,
                headers={"x-orbit-capture-secret": self._settings.capture_secret or ""},
                json={
                    "targetUrl": analysis.target_url,
                    "maxPages": min(max_pages, 3),
                    "deepCrawl": deep_crawl,
                },
            )
            response.raise_for_status()
            payload = response.json()

        pages = payload.get("pages") or []
        if not pages:
            raise RuntimeError("serverless browser returned no pages")

        for captured in pages:
            url = str(captured.get("url") or analysis.target_url)
            await assert_public_resolution(url)
            html = str(captured.get("html") or "")
            headers = {str(key).lower(): str(value) for key, value in (captured.get("headers") or {}).items()}
            status_code = int(captured.get("status") or 0)
            scripts, markers, generator = extract_html_signals(html, url)
            signals = extract_page_signals(
                html, headers, url, "HTTP/2", status_code,
                [headers["set-cookie"]] if headers.get("set-cookie") else [],
            )
            metadata = {
                "title": str(captured.get("title") or "")[:300],
                "status_code": status_code,
                "artifact_uri": None,
                "scripts": scripts,
                "markers": markers,
                "generator": generator,
                "links": extract_link_paths(html, url, origin_host),
                "headers": _select_headers(headers),
                "signals": signals,
                "capture_engine": str(payload.get("engine") or "remote-browser"),
                "access_blocked": status_code in {401, 403, 429},
                "visible_text": extract_visible_text(html),
            }
            await self._persist_evidence(analysis.id, "page", url, metadata)

        for signal in (payload.get("network_signals") or [])[:100]:
            if isinstance(signal, dict) and signal.get("host") and signal.get("path") is not None:
                network_signals.append(signal)
        await self._store_network_evidence(analysis.id, network_signals[:100])
        await self._events.append(
            analysis.id, "evidence.recorded",
            f"Captured browser evidence from {len(pages)} page(s)",
            {"pages_explored": len(pages), "network_signals": len(network_signals), "engine": payload.get("engine")},
        )

    def _ensure_artifact_root(self) -> bool:
        """Prepare the screenshot directory. Artifacts are optional: on a read-only
        filesystem (serverless) we disable them rather than abort the analysis."""
        if self._artifacts_disabled:
            return False
        try:
            self._artifact_root.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as error:
            logger.warning("artifact directory unavailable, screenshots disabled: %s", error)
            self._artifacts_disabled = True
            return False

    async def _run_site_probes(self, analysis: Analysis) -> None:
        """Host-level TLS, JS-bundle, and crawlability probes (best effort)."""
        try:
            async with self._session_factory() as session:
                first = await session.scalar(
                    select(EvidenceItem)
                    .where(EvidenceItem.analysis_id == analysis.id, EvidenceItem.kind == "page")
                    .order_by(EvidenceItem.created_at)
                    .limit(1)
                )
            scripts = (first.metadata_json.get("signals") or {}).get("scripts_external", []) if first else []
            probes = await run_site_probes(analysis.target_url, scripts)
            await self._persist_evidence(analysis.id, "site_probe", analysis.target_url, probes)
            await self._events.append(
                analysis.id, "probes.recorded", "Ran TLS, bundle, and crawlability probes",
                {
                    "tls": bool(probes.get("tls", {}).get("available")),
                    "js_bytes": probes.get("bundles", {}).get("total_bytes"),
                    "sourcemaps_exposed": probes.get("bundles", {}).get("sourcemaps_exposed"),
                },
            )
        except Exception:
            logger.warning("site probes failed", extra={"analysis_id": analysis.id}, exc_info=True)

    async def _explore_with_browser(
        self, analysis: Analysis, max_pages: int, deep_crawl: bool, capture_network: bool,
        origin_host: str | None, pending: list[str], visited: set[str], network_signals: list[dict[str, str | int]],
    ) -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                accept_downloads=False,
                ignore_https_errors=False,
                service_workers="block",
                viewport={"width": 1440, "height": 900},
            )
            try:
                await self._apply_request_policy(context, origin_host)
                while pending and len(visited) < max_pages:
                    if await self._is_cancelled(analysis.id):
                        return
                    url = pending.pop(0)
                    if url in visited:
                        continue
                    page = await context.new_page()
                    if capture_network:
                        page.on("response", lambda response: self._collect_response_signal(response, network_signals))
                    try:
                        await self._events.append(
                            analysis.id, "page.exploring", f"Exploring {url}", {"url": url}
                        )
                        response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                        await assert_public_resolution(page.url)
                        visited.add(url)
                        headers = await response.all_headers() if response else {}
                        await self._store_page_evidence(analysis.id, page, response.status if response else 0, headers)
                        if deep_crawl:
                            pending.extend(await self._discover_same_host_links(page, origin_host, visited, pending))
                        await self._set_progress(analysis.id, min(88, 10 + int(len(visited) / max_pages * 75)))
                    finally:
                        await page.close()
                await self._store_network_evidence(analysis.id, network_signals)
                await self._events.append(
                    analysis.id, "evidence.recorded", f"Captured evidence from {len(visited)} page(s)",
                    {"pages_explored": len(visited), "network_signals": len(network_signals)},
                )
            finally:
                await context.close()
                await browser.close()

    async def _apply_request_policy(self, context: BrowserContext, origin_host: str | None) -> None:
        async def guard(route) -> None:  # type: ignore[no-untyped-def]
            parsed = urlsplit(route.request.url)
            host = (parsed.hostname or "").lower()
            allowed = parsed.scheme in {"http", "https"} and host not in {"localhost", "127.0.0.1", "::1"}
            # Exploration navigates only within the initially-authorized public product origin.
            if route.request.is_navigation_request() and host != origin_host:
                allowed = False
            if not allowed:
                await route.abort("blockedbyclient")
                return
            if route.request.is_navigation_request():
                try:
                    await assert_public_resolution(route.request.url)
                except Exception:
                    await route.abort("blockedbyclient")
                    return
            await route.continue_()

        await context.route("**/*", guard)

    @staticmethod
    def _collect_response_signal(response, signals: list[dict[str, str | int]]) -> None:  # type: ignore[no-untyped-def]
        if len(signals) >= 100:
            return
        parsed = urlsplit(response.url)
        if parsed.scheme not in {"http", "https"}:
            return
        headers = response.headers
        signals.append({
            "host": parsed.hostname or "",
            "path": parsed.path[:200],
            "status": response.status,
            "method": response.request.method,
            "resource_type": response.request.resource_type,
            "content_type": headers.get("content-type", "")[:120],
            "cache_control": headers.get("cache-control", "")[:120],
            "server": headers.get("server", "")[:80],
        })

    async def _discover_same_host_links(
        self, page: Page, origin_host: str | None, visited: set[str], pending: list[str]
    ) -> list[str]:
        hrefs = await page.locator("a[href]").evaluate_all("links => links.map(link => link.href)")
        discovered: list[str] = []
        for href in hrefs[:300]:
            absolute = urljoin(page.url, href)
            parsed = urlsplit(absolute)
            if parsed.hostname != origin_host or parsed.scheme not in {"http", "https"}:
                continue
            normalized = normalize_public_url(absolute, self._settings.allowed_analysis_hosts)
            if normalized not in visited and normalized not in pending and normalized not in discovered:
                discovered.append(normalized)
        return discovered

    async def _store_page_evidence(self, analysis_id: str, page: Page, status_code: int, headers: dict) -> None:
        title = await page.title()
        html = await page.content()
        scripts, markers, generator = extract_html_signals(html, page.url)
        artifact_uri: str | None = None
        if self._ensure_artifact_root():
            screenshot_path = (
                self._artifact_root / analysis_id / f"{hashlib.sha256(page.url.encode()).hexdigest()[:16]}.png"
            )
            try:
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot_path), full_page=False)
                artifact_uri = str(screenshot_path)
            except Exception:
                artifact_uri = None
        set_cookie = [headers["set-cookie"]] if headers.get("set-cookie") else []
        signals = extract_page_signals(html, headers, page.url, "HTTP/2", status_code, set_cookie)
        metadata = {
            "title": title[:300],
            "status_code": status_code,
            "artifact_uri": artifact_uri,
            "scripts": scripts,
            "markers": markers,
            "generator": generator,
            "links": extract_link_paths(html, page.url, urlsplit(page.url).hostname),
            "headers": _select_headers(headers),
            "signals": signals,
            "visible_text": extract_visible_text(html),
        }
        await self._persist_evidence(analysis_id, "page", page.url, metadata)

    async def _explore_with_http(
        self, analysis: Analysis, max_pages: int, deep_crawl: bool, origin_host: str | None,
        pending: list[str], visited: set[str], network_signals: list[dict[str, str | int]],
    ) -> None:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            while pending and len(visited) < max_pages:
                if await self._is_cancelled(analysis.id):
                    return
                url = pending.pop(0)
                if url in visited:
                    continue
                await self._events.append(analysis.id, "page.exploring", f"Exploring {url}", {"url": url})
                try:
                    response = await client.get(url)
                except httpx.HTTPError:
                    continue
                await assert_public_resolution(str(response.url))
                visited.add(url)
                html = response.text
                scripts, markers, generator = extract_html_signals(html, str(response.url))
                title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
                signals = extract_page_signals(
                    html, dict(response.headers), str(response.url),
                    response.http_version, response.status_code,
                    response.headers.get_list("set-cookie"),
                )
                metadata = {
                    "title": (title_match.group(1).strip()[:300] if title_match else ""),
                    "status_code": response.status_code,
                    "artifact_uri": None,
                    "scripts": scripts,
                    "markers": markers,
                    "generator": generator,
                    "links": extract_link_paths(html, str(response.url), origin_host),
                    "headers": _select_headers(dict(response.headers)),
                    "signals": signals,
                    "access_blocked": response.status_code in {401, 403, 429},
                    "visible_text": extract_visible_text(html),
                }
                await self._persist_evidence(analysis.id, "page", str(response.url), metadata)
                for src in scripts:
                    host = urlsplit(src).hostname
                    if host:
                        network_signals.append({
                            "host": host,
                            "path": urlsplit(src).path[:200],
                            "status": 200,
                            "method": "GET",
                            "resource_type": "script",
                            "content_type": "application/javascript",
                        })
                if deep_crawl:
                    for href in re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html, flags=re.I)[:200]:
                        absolute = urljoin(str(response.url), href)
                        parsed = urlsplit(absolute)
                        if parsed.hostname == origin_host and parsed.scheme in {"http", "https"}:
                            normalized = normalize_public_url(absolute, self._settings.allowed_analysis_hosts)
                            if normalized not in visited and normalized not in pending:
                                pending.append(normalized)
                await self._set_progress(analysis.id, min(88, 10 + int(len(visited) / max_pages * 75)))
        await self._store_network_evidence(analysis.id, network_signals[:100])
        await self._events.append(
            analysis.id, "evidence.recorded", f"Captured evidence from {len(visited)} page(s)",
            {"pages_explored": len(visited), "network_signals": len(network_signals)},
        )

    async def _store_network_evidence(self, analysis_id: str, signals: list[dict[str, str | int]]) -> None:
        for signal in signals:
            fingerprint = f"{signal['host']}{signal['path']}"
            await self._persist_evidence(analysis_id, "network_signal", f"https://{signal['host']}{signal['path']}", signal, fingerprint)

    async def _persist_evidence(
        self, analysis_id: str, kind: str, source_url: str, metadata: dict, fingerprint: str | None = None
    ) -> None:
        async with self._session_factory() as session:
            session.add(EvidenceItem(
                analysis_id=analysis_id,
                kind=kind,
                source_url=source_url,
                content_hash=hashlib.sha256((fingerprint or source_url).encode()).hexdigest(),
                metadata_json=metadata,
            ))
            await session.commit()

    async def _load_analysis(self, analysis_id: str) -> Analysis | None:
        async with self._session_factory() as session:
            return await session.get(Analysis, analysis_id)

    async def _set_status(self, analysis_id: str, status: AnalysisStatus, progress: int) -> None:
        async with self._session_factory() as session:
            analysis = await session.get(Analysis, analysis_id)
            if analysis is None:
                return
            analysis.status, analysis.progress = status, progress
            if status == AnalysisStatus.RUNNING:
                analysis.started_at = datetime.now(timezone.utc)
            if status in {AnalysisStatus.COMPLETED, AnalysisStatus.FAILED, AnalysisStatus.CANCELLED}:
                analysis.completed_at = datetime.now(timezone.utc)
            await session.commit()
        await self._events.append(analysis_id, "analysis.status", f"Analysis status: {status}", {"status": status, "progress": progress})

    async def _set_progress(self, analysis_id: str, progress: int) -> None:
        async with self._session_factory() as session:
            analysis = await session.get(Analysis, analysis_id)
            if analysis:
                analysis.progress = progress
                await session.commit()

    async def _is_cancelled(self, analysis_id: str) -> bool:
        async with self._session_factory() as session:
            analysis = await session.get(Analysis, analysis_id)
            return analysis is None or analysis.status == AnalysisStatus.CANCELLED

    async def _mark_failed(self, analysis_id: str, error: Exception) -> None:
        async with self._session_factory() as session:
            analysis = await session.get(Analysis, analysis_id)
            if analysis is None:
                return
            analysis.status = AnalysisStatus.FAILED
            analysis.error_code = "exploration_failed"
            analysis.error_detail = "The browser exploration could not be completed."
            analysis.completed_at = datetime.now(timezone.utc)
            await session.commit()
        await self._events.append(analysis_id, "analysis.failed", "Exploration could not be completed", {"error": type(error).__name__})
