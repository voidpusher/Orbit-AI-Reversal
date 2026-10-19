import json

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from app.mcp_server import OrbitClient, build_server, summarize_report

REPORT = {
    "id": "r1", "product_name": "Acme", "target_url": "https://acme.com/", "headline": "Acme is a tracker",
    "summary": "…", "overall_confidence": 81,
    "document": {
        "meta": {"pages_explored": 3},
        "overview": {"headline": "x"},
        "api": {"summary": "GraphQL API", "confidence": 88, "endpoints": [{"method": "POST", "path": "/graphql"}]},
        "code_intel": {"summary": "Read 2 bundles", "confidence": 84,
                       "findings": [{"title": "3 feature flag(s) referenced", "status": "info"}], "flags": [{"key": "beta"}]},
        "security": {"summary": "Graded B", "confidence": 90, "grade": "B",
                     "findings": [{"title": "No HSTS header", "status": "warn"}]},
    },
}


def _transport(log: list[httpx.Request]) -> httpx.MockTransport:
    polls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        log.append(request)
        path = request.url.path
        if request.method == "POST" and path == "/api/v1/analyses":
            return httpx.Response(202, json={"id": "a1", "target_url": "https://acme.com/", "status": "queued", "progress": 0})
        if path == "/api/v1/analyses/a1":
            polls["count"] += 1
            done = polls["count"] >= 2
            return httpx.Response(200, json={
                "id": "a1", "target_url": "https://acme.com/", "status": "completed" if done else "running",
                "progress": 100 if done else 40, "report_id": "r1" if done else None,
            })
        if path == "/api/v1/reports/r1":
            return httpx.Response(200, json=REPORT)
        if path == "/api/v1/reports/missing":
            return httpx.Response(404, json={"detail": "Report not found"})
        return httpx.Response(500, text="unexpected")

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_analyze_polls_until_report_and_summarizes() -> None:
    log: list[httpx.Request] = []
    client = OrbitClient("http://orbit.test", token="secret-token", transport=_transport(log))
    result = await client.analyze("https://acme.com", max_pages=5, deep_crawl=False, wait_seconds=30, poll_interval=0)
    await client.aclose()

    create = log[0]
    assert create.headers["authorization"] == "Bearer secret-token"
    assert create.headers["idempotency-key"].startswith("mcp-")
    assert json.loads(create.content)["options"]["max_pages"] == 5
    assert result["status"] == "completed" and result["report_id"] == "r1"
    assert result["report"]["sections"]["security"]["findings"] == ["[warn] No HSTS header"]


@pytest.mark.asyncio
async def test_analyze_returns_next_step_when_still_running() -> None:
    client = OrbitClient("http://orbit.test", transport=_transport([]))
    result = await client.analyze("https://acme.com", max_pages=5, deep_crawl=False, wait_seconds=0, poll_interval=0)
    await client.aclose()
    assert result["status"] == "queued" and "get_analysis" in result["next_step"]


def test_summarize_report_is_compact_and_skips_meta() -> None:
    summary = summarize_report(REPORT)
    assert set(summary["sections"]) == {"api", "code_intel", "security"}
    assert summary["sections"]["api"]["endpoints"] == ["POST /graphql"]
    assert summary["sections"]["security"]["grade"] == "B"


@pytest.mark.asyncio
async def test_server_exposes_tools_and_drills_into_sections() -> None:
    client = OrbitClient("http://orbit.test", transport=_transport([]))
    server = build_server(client)
    tools = {tool.name: tool for tool in await server.list_tools()}
    assert set(tools) == {"analyze_url", "get_analysis", "list_reports", "get_report", "ask_report", "compare_reports"}
    assert tools["get_report"].annotations.read_only_hint is True
    assert tools["analyze_url"].annotations.read_only_hint is False

    section = await server.call_tool("get_report", {"report_id": "r1", "section": "code_intel"})
    assert not section.is_error
    assert "beta" in section.content[0].text

    # ToolError text is what the protocol layer hands back to the agent as an error result.
    with pytest.raises(ToolError, match="no section 'nope'. Available: api, code_intel, security"):
        await server.call_tool("get_report", {"report_id": "r1", "section": "nope"})
    with pytest.raises(ToolError, match="404: Report not found"):
        await server.call_tool("get_report", {"report_id": "missing"})
    await client.aclose()
