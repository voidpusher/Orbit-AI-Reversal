"""Deep, observable signal extraction from a page's HTML and response headers.

This module is the heart of Orbit's "detail nobody gives you": from a single
public response it derives security posture, delivery/caching behavior, rendering
strategy, deployment fingerprint, SEO/structured data, privacy/cookie hygiene,
and data-fetching shape — all grounded in concrete, quotable evidence.

Pure functions over raw strings so they are fully testable and reused by both the
browser and the HTTP-fallback explorer.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlsplit

_META_RE = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR_RE = re.compile(r'([a-zA-Z:\-]+)\s*=\s*"([^"]*)"')
_LINK_RE = re.compile(r"<link\b[^>]*>", re.I)
_SCRIPT_TAG_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.I | re.S)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_HTML_TAG_RE = re.compile(r"<html\b([^>]*)>", re.I)
_IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
_JSONLD_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
_NEXT_DATA_RE = re.compile(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', re.I | re.S)


def _attrs(tag: str) -> dict[str, str]:
    return {k.lower(): v for k, v in _ATTR_RE.findall(tag)}


def _meta_map(html: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for tag in _META_RE.findall(html):
        attrs = _attrs(tag)
        key = attrs.get("name") or attrs.get("property") or attrs.get("http-equiv")
        if key and "content" in attrs:
            result[key.lower()] = attrs["content"]
    return result


def _text_bytes_without_tags(html: str) -> int:
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", body)
    return len(re.sub(r"\s+", " ", text).strip())


def _parse_cookies(set_cookie_values: list[str]) -> list[dict]:
    cookies = []
    for raw in set_cookie_values:
        name = raw.split("=", 1)[0].strip()
        lowered = raw.lower()
        samesite = None
        match = re.search(r"samesite=(\w+)", lowered)
        if match:
            samesite = match.group(1)
        cookies.append({
            "name": name[:60],
            "secure": "secure" in lowered,
            "http_only": "httponly" in lowered,
            "same_site": samesite,
        })
    return cookies


def _jsonld_types(html: str) -> list[str]:
    types: list[str] = []
    for block in _JSONLD_RE.findall(html)[:8]:
        try:
            data = json.loads(block.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict):
                t = item.get("@type")
                if isinstance(t, list):
                    types.extend(str(x) for x in t)
                elif t:
                    types.append(str(t))
    return list(dict.fromkeys(types))[:12]


def _next_data(html: str) -> dict | None:
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return None
    blob = match.group(1).strip()
    info: dict = {"present": True, "props_bytes": len(blob)}
    try:
        data = json.loads(blob)
        info["build_id"] = data.get("buildId")
        info["page"] = data.get("page")
        info["locale"] = data.get("locale")
        info["is_ssg"] = bool(data.get("isFallback") is not None or data.get("gssp") is None and data.get("gsp"))
        props = data.get("props", {})
        info["has_page_props"] = bool(props.get("pageProps"))
        info["runtime_config"] = bool(data.get("runtimeConfig"))
    except (json.JSONDecodeError, ValueError):
        pass
    return info


def extract_page_signals(html: str, headers: dict[str, str], url: str, http_version: str, status: int,
                         set_cookie: list[str] | None = None) -> dict:
    """Return a rich, structured signal bundle for one explored page."""
    lower_headers = {str(k).lower(): str(v) for k, v in headers.items()}
    meta = _meta_map(html)
    origin_host = (urlsplit(url).hostname or "").lower()

    # Scripts: external vs inline, module vs classic, async/defer.
    scripts_external: list[str] = []
    inline_scripts = 0
    module_scripts = 0
    async_defer = 0
    third_party_hosts: set[str] = set()
    for attr_str, body in _SCRIPT_TAG_RE.findall(html):
        attrs = _attrs(f"<x {attr_str}>")
        src = attrs.get("src")
        if src:
            absolute = urljoin(url, src)
            scripts_external.append(absolute)
            host = (urlsplit(absolute).hostname or "").lower()
            if host and host != origin_host:
                third_party_hosts.add(host)
            if attrs.get("type") == "module":
                module_scripts += 1
            if "async" in attr_str.lower() or "defer" in attr_str.lower():
                async_defer += 1
        elif body.strip():
            inline_scripts += 1

    # Link tags: resource hints, stylesheets, icons, alternates/hreflang, manifest.
    rels: dict[str, int] = {}
    hreflangs: list[str] = []
    for tag in _LINK_RE.findall(html):
        attrs = _attrs(tag)
        rel = (attrs.get("rel") or "").lower()
        if rel:
            rels[rel] = rels.get(rel, 0) + 1
        if rel == "alternate" and attrs.get("hreflang"):
            hreflangs.append(attrs["hreflang"])
        href = attrs.get("href")
        if href:
            host = (urlsplit(urljoin(url, href)).hostname or "").lower()
            if host and host != origin_host:
                third_party_hosts.add(host)

    # Images and modern formats.
    images = _IMG_RE.findall(html)
    image_formats: dict[str, int] = {}
    lazy_images = 0
    for tag in images:
        attrs = _attrs(tag)
        src = attrs.get("src", "") + " " + attrs.get("srcset", "")
        for fmt in ("avif", "webp", "svg", "png", "jpg", "jpeg", "gif"):
            if f".{fmt}" in src.lower():
                image_formats[fmt] = image_formats.get(fmt, 0) + 1
        if attrs.get("loading", "").lower() == "lazy":
            lazy_images += 1

    html_attrs = _attrs(_HTML_TAG_RE.search(html).group(1)) if _HTML_TAG_RE.search(html) else {}
    title_match = _TITLE_RE.search(html)
    text_bytes = _text_bytes_without_tags(html)

    security = {
        "csp": lower_headers.get("content-security-policy"),
        "hsts": lower_headers.get("strict-transport-security"),
        "x_frame_options": lower_headers.get("x-frame-options"),
        "x_content_type_options": lower_headers.get("x-content-type-options"),
        "referrer_policy": lower_headers.get("referrer-policy"),
        "permissions_policy": lower_headers.get("permissions-policy"),
        "coop": lower_headers.get("cross-origin-opener-policy"),
        "coep": lower_headers.get("cross-origin-embedder-policy"),
    }
    delivery = {
        "http_version": http_version,
        "content_encoding": lower_headers.get("content-encoding"),
        "content_type": lower_headers.get("content-type"),
        "cache_control": lower_headers.get("cache-control"),
        "etag": bool(lower_headers.get("etag")),
        "age": lower_headers.get("age"),
        "vary": lower_headers.get("vary"),
        "cdn_cache_status": (
            lower_headers.get("x-vercel-cache") or lower_headers.get("cf-cache-status")
            or lower_headers.get("x-nextjs-cache") or lower_headers.get("x-cache")
        ),
        "server": lower_headers.get("server"),
        "region_hint": (
            lower_headers.get("x-vercel-id") or lower_headers.get("cf-ray")
            or lower_headers.get("x-amz-cf-pop") or lower_headers.get("fly-region")
        ),
        "powered_by": lower_headers.get("x-powered-by"),
    }

    return {
        "url": url,
        "status": status,
        "html_bytes": len(html),
        "text_bytes": text_bytes,
        "text_ratio": round(text_bytes / max(1, len(html)), 3),
        "lang": html_attrs.get("lang"),
        "title": (title_match.group(1).strip()[:300] if title_match else ""),
        "meta_description": meta.get("description"),
        "canonical": next((_attrs(t).get("href") for t in _LINK_RE.findall(html) if _attrs(t).get("rel") == "canonical"), None),
        "robots": meta.get("robots"),
        "viewport": meta.get("viewport"),
        "generator": meta.get("generator"),
        "open_graph": {k[3:]: v for k, v in meta.items() if k.startswith("og:")},
        "twitter": {k[8:]: v for k, v in meta.items() if k.startswith("twitter:")},
        "jsonld_types": _jsonld_types(html),
        "hreflangs": list(dict.fromkeys(hreflangs))[:12],
        "scripts_external": scripts_external[:60],
        "external_script_count": len(scripts_external),
        "inline_script_count": inline_scripts,
        "module_scripts": module_scripts,
        "async_defer_scripts": async_defer,
        "stylesheet_count": rels.get("stylesheet", 0),
        "resource_hints": {k: rels[k] for k in ("preload", "prefetch", "preconnect", "dns-prefetch", "modulepreload") if k in rels},
        "has_manifest": "manifest" in rels,
        "image_count": len(images),
        "image_formats": image_formats,
        "lazy_images": lazy_images,
        "third_party_hosts": sorted(third_party_hosts)[:40],
        "cookies": _parse_cookies(set_cookie or []),
        "next_data": _next_data(html),
        "security_headers": security,
        "delivery": delivery,
        "has_ssr_content": text_bytes > 500,
    }
