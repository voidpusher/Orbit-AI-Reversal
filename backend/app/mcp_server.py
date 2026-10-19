"""Orbit as an MCP server, so agents (Claude Code, Cursor, Codex) can analyze public products.

The server is a thin client of Orbit's HTTP API: analyses run in the normal backend with
its URL-safety checks, quotas, and tenancy. Nothing here touches the database directly.

    python -m app.mcp_server          # stdio transport

Environment:
    ORBIT_API_URL    Orbit backend base URL (default http://localhost:8000)
    ORBIT_API_TOKEN  Bearer token; optional when the backend runs with auth disabled
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

API_PREFIX = "/api/v1"
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
_SKIP_SECTIONS = {"meta", "overview"}


class OrbitError(ToolError):
    """Raised for conditions the agent should see and can act on (MCP shows ToolError text to the model)."""


class OrbitClient:
    def __init__(self, base_url: str, token: str | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + API_PREFIX, headers=headers, timeout=60, transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise OrbitError(f"Could not reach the Orbit API ({type(error).__name__}). Is the backend running?") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise OrbitError(f"Orbit API returned {response.status_code}: {detail}")
        return response.json() if response.content else None

    async def analyze(self, url: str, max_pages: int, deep_crawl: bool, wait_seconds: int, poll_interval: float = 3.0) -> dict:
        analysis = await self._request(
            "POST", "/analyses",
            json={
                "target_url": url,
                "options": {"max_pages": max_pages, "deep_crawl": deep_crawl, "capture_network_requests": True},
                "authorized_public_analysis": True,
            },
            headers={"Idempotency-Key": f"mcp-{uuid.uuid4().hex}"},
        )
        deadline = asyncio.get_running_loop().time() + max(0, wait_seconds)
        while analysis["status"] not in TERMINAL_STATUSES and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(poll_interval)
            analysis = await self._request("GET", f"/analyses/{analysis['id']}")
        return await self._analysis_result(analysis)

    async def analysis(self, analysis_id: str) -> dict:
        return await self._analysis_result(await self._request("GET", f"/analyses/{analysis_id}"))

    async def _analysis_result(self, analysis: dict) -> dict:
        result = {
            "analysis_id": analysis["id"],
            "target_url": analysis["target_url"],
            "status": analysis["status"],
            "progress": analysis.get("progress"),
            "report_id": analysis.get("report_id"),
        }
        if analysis.get("error_code"):
            result["error_code"] = analysis["error_code"]
        if analysis.get("report_id"):
            result["report"] = summarize_report(await self.report(analysis["report_id"]))
        elif analysis["status"] not in TERMINAL_STATUSES:
            result["next_step"] = "Still running. Call get_analysis with this analysis_id to check again."
        return result

    async def report(self, report_id: str) -> dict:
        return await self._request("GET", f"/reports/{report_id}")

    async def reports(self, limit: int, query: str | None) -> list[dict]:
        params: dict[str, Any] = {"limit": max(1, min(limit, 50))}
        if query:
            params["q"] = query
        payload = await self._request("GET", "/reports", params=params)
        return [
            {key: item.get(key) for key in ("id", "product_name", "target_url", "headline", "overall_confidence", "published_at")}
            for item in payload.get("items", [])
        ]

    async def ask(self, report_id: str, question: str) -> dict:
        return await self._request("POST", f"/reports/{report_id}/ask", json={"question": question})

    async def compare(self, report_a: str, report_b: str) -> dict:
        return await self._request("GET", "/reports/compare", params={"a": report_a, "b": report_b})


def _section_digest(section: dict) -> dict:
    digest: dict[str, Any] = {key: section[key] for key in ("summary", "confidence", "grade") if key in section}
    findings = section.get("findings") or []
    if findings:
        digest["findings"] = [f"[{f.get('status', 'info')}] {f.get('title')}" for f in findings[:6]]
    for key, label in (("items", "items"), ("endpoints", "endpoints"), ("flows", "flows"), ("roles", "roles")):
        values = section.get(key)
        if isinstance(values, list) and values:
            names = []
            for value in values[:12]:
                if isinstance(value, dict):
                    name = value.get("name") or value.get("title") or " ".join(
                        str(value[k]) for k in ("method", "path") if value.get(k)
                    )
                    names.append(str(name))
            if names:
                digest[label] = names
    return digest


def summarize_report(detail: dict) -> dict:
    """A compact view sized for an agent's context; get_report(section=...) returns the full section."""
    document = detail.get("document") or {}
    return {
        "report_id": detail.get("id"),
        "product_name": detail.get("product_name"),
        "target_url": detail.get("target_url"),
        "headline": detail.get("headline"),
        "summary": detail.get("summary"),
        "overall_confidence": detail.get("overall_confidence"),
        "sections": {
            key: _section_digest(value)
            for key, value in document.items()
            if key not in _SKIP_SECTIONS and isinstance(value, dict)
        },
    }


def build_server(client: OrbitClient | None = None) -> MCPServer:
    server = MCPServer(
        name="orbit",
        title="Orbit software intelligence",
        instructions=(
            "Orbit analyzes PUBLIC software products from the outside: architecture, tech stack, API surface, "
            "client code references, security headers, performance, and more. Every claim carries evidence and a "
            "confidence; 'observed' facts are distinct from 'inferred' ones, so relay that distinction. "
            "Start with analyze_url, then drill in with get_report(section=...) or ask_report."
        ),
    )
    state: dict[str, OrbitClient] = {}

    def orbit() -> OrbitClient:
        if client is not None:
            return client
        if "client" not in state:
            state["client"] = OrbitClient(
                os.environ.get("ORBIT_API_URL", "http://localhost:8000"), os.environ.get("ORBIT_API_TOKEN") or None,
            )
        return state["client"]

    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True))
    async def analyze_url(url: str, max_pages: int = 10, deep_crawl: bool = False, wait_seconds: int = 240) -> dict:
        """Analyze a public product URL and return a compact report summary.

        Orbit crawls public pages, reads the public JavaScript bundles, and probes DNS/TLS/API endpoints.
        Waits up to wait_seconds for the report; if it is still running, call get_analysis later.
        Only analyze products you are allowed to research; Orbit refuses local and private-network targets.
        """
        return await orbit().analyze(url, max(1, min(max_pages, 50)), deep_crawl, max(0, min(wait_seconds, 600)))

    @server.tool(annotations=read_only)
    async def get_analysis(analysis_id: str) -> dict:
        """Check an analysis started by analyze_url; includes the report summary once it is complete."""
        return await orbit().analysis(analysis_id)

    @server.tool(annotations=read_only)
    async def list_reports(limit: int = 10, query: str | None = None) -> list[dict]:
        """List recent Orbit reports, optionally filtered by product name or URL."""
        return await orbit().reports(limit, query)

    @server.tool(annotations=read_only)
    async def get_report(report_id: str, section: str | None = None) -> dict:
        """Get a report. Without `section`, returns a compact summary of every section.

        With `section` (for example "api", "code_intel", "architecture", "security", "entities",
        "tech_stack", "performance"), returns that section in full, including evidence.
        """
        detail = await orbit().report(report_id)
        if section is None:
            return summarize_report(detail)
        document = detail.get("document") or {}
        if section not in document:
            available = sorted(k for k in document if k not in _SKIP_SECTIONS)
            raise OrbitError(f"Report has no section '{section}'. Available: {', '.join(available)}")
        return {"report_id": report_id, "section": section, "content": document[section]}

    @server.tool(annotations=read_only)
    async def ask_report(report_id: str, question: str) -> dict:
        """Ask a question about one report. Answers cite the report's evidence and state their limitations."""
        return await orbit().ask(report_id, question)

    @server.tool(annotations=read_only)
    async def compare_reports(report_a: str, report_b: str) -> dict:
        """Compare two reports: shared and unique technologies, features, and architecture."""
        return await orbit().compare(report_a, report_b)

    return server


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one INFO line per poll drowns the host's log view
    build_server().run("stdio")


if __name__ == "__main__":
    main()
