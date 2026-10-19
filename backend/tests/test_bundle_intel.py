import json

import httpx
import pytest

from app.services.bundle_intel import (
    extract_code_signals,
    normalize_endpoint,
    parse_build_manifest,
    probe_code_intel,
    routes_from_script_urls,
    select_app_scripts,
    summarize_source_map,
)
from app.services.deep_analysis import analyze_code

BUNDLE = """
!function(){var e=fetch("/api/v2/projects/"+t,{method:"POST",body:x});
axios.delete("/api/v2/projects/${id}/members/${uid}");
const q=gql`query ListIssues($team: ID!) { issues { id } }`;
const m=gql`mutation CreateIssue($input: IssueInput!) { createIssue }`;
n.variation("new-billing-ui",!1);s.checkGate("ai_composer");
var c=new WebSocket("wss://realtime.acme.com/socket");
var u="https://api.acme.com/v1/search";var st="https://staging-api.acme.com/graphql";
var ext="https://www.google-analytics.com/collect";var asset="/api/v2/static/logo.svg";
var pk="__STRIPE_PUBLISHABLE_TEST_KEY__";var leak="__STRIPE_SECRET_TEST_KEY__";
var r=[{path:"/settings/billing"},{path:"/team/:teamId/projects"}];
Symbol.for("react.element");var t="ProseMirror";
}();
//# sourceMappingURL=main.abc123.js.map
"""
# Generate unmistakably synthetic values at runtime, not credential-shaped literals
# in the repository. The live-mode prefix still exercises the production detector.
BUNDLE = BUNDLE.replace("__STRIPE_PUBLISHABLE_TEST_KEY__", "pk_" + "test_" + "0" * 26)
BUNDLE = BUNDLE.replace("__STRIPE_SECRET_TEST_KEY__", "sk_" + "live_" + "0" * 26)


def test_extract_code_signals_finds_references_without_values() -> None:
    signals = extract_code_signals(BUNDLE, "acme.com")
    endpoints = {(e["method"], e["path"], e["host"]) for e in signals["endpoints"]}
    assert ("POST", "/api/v2/projects", None) in endpoints
    assert ("DELETE", "/api/v2/projects/:param/members/:param", None) in endpoints
    assert ("ANY", "/v1/search", "api.acme.com") in endpoints
    assert not any("logo.svg" in path for _, path, _ in endpoints)
    assert not any(host and "google-analytics" in host for _, _, host in endpoints)

    assert {o["name"]: o["kind"] for o in signals["graphql_operations"]} == {"ListIssues": "query", "CreateIssue": "mutation"}
    assert {f["key"]: f["provider"] for f in signals["flags"]} == {"new-billing-ui": "LaunchDarkly", "ai_composer": "Statsig"}
    assert signals["realtime"] == ["wss://realtime.acme.com/socket"]
    assert {"React", "ProseMirror"} <= set(signals["libraries"])
    assert signals["non_production_hosts"] == ["staging-api.acme.com"]
    assert {"/settings/billing", "/team/:teamId/projects"} <= set(signals["routes"])

    # Secrets are reported masked: kind + prefix + length, never the value.
    assert signals["secrets"] == [{"kind": "Stripe secret key", "masked": "sk_l…(34 chars)"}]
    assert signals["public_keys"][0]["kind"] == "Stripe publishable key"
    assert "0" * 26 not in json.dumps(signals)


def test_normalize_endpoint_keeps_route_shape() -> None:
    assert normalize_endpoint("/api/users/12345/notification-preferences?x=1") == "/api/users/:param/notification-preferences"
    assert normalize_endpoint("/api/items/${item.id}/") == "/api/items/:param"


def test_routes_from_next_manifest_and_chunk_names() -> None:
    manifest = 'self.__BUILD_MANIFEST={__rewrites:{},"/":["a.js"],"/pricing":["b.js"],"/[workspace]/settings":["c.js"],"/_error":["d.js"]};'
    assert parse_build_manifest(manifest) == ["/", "/:workspace/settings", "/pricing"]
    assert routes_from_script_urls([
        "https://acme.com/_next/static/chunks/app/(marketing)/pricing/page-1a2b3c.js",
        "https://acme.com/_next/static/chunks/pages/projects/[id]-9f8e7d.js",
        "https://acme.com/_next/static/chunks/pages/_app-123abc.js",
    ]) == ["/pricing", "/projects/:id"]


def test_summarize_source_map_keeps_structure_not_contents() -> None:
    summary = summarize_source_map({
        "version": 3,
        "sources": [
            "webpack://_N_E/./src/features/billing/Invoice.tsx",
            "webpack://_N_E/./src/features/billing/Plans.tsx",
            "webpack://_N_E/./src/features/editor/Toolbar.tsx",
            "webpack://_N_E/./node_modules/react-dom/index.js",
            "webpack://_N_E/./node_modules/@tanstack/react-query/build/index.js",
            "webpack/runtime/chunk loaded",
        ],
        "sourcesContent": ["secret source text"],
    })
    assert summary["app_files"] == 3
    assert summary["dependencies"] == ["@tanstack/react-query", "react-dom"]
    assert summary["areas"][0] == {"area": "features/billing", "files": 2}
    assert summary["language"] == "TypeScript"
    assert summary["sources_content"] is True
    assert "secret source text" not in json.dumps(summary)


def test_select_app_scripts_skips_third_party() -> None:
    selected = select_app_scripts([
        "https://acme.com/_next/static/chunks/main.js",
        "https://cdn.acme.com/app.js",
        "https://d1abc.cloudfront.net/assets/index-abc.js",
        "https://www.googletagmanager.com/gtm.js",
        "data:text/javascript,alert(1)",
    ], "acme.com")
    assert selected == [
        "https://acme.com/_next/static/chunks/main.js",
        "https://cdn.acme.com/app.js",
        "https://d1abc.cloudfront.net/assets/index-abc.js",
    ]


async def _public(host: str) -> bool:
    return host != "internal.acme.com"


@pytest.mark.asyncio
async def test_probe_code_intel_follows_source_map_and_manifest() -> None:
    source_map = {"version": 3, "sources": ["webpack://app/./src/app/dashboard/page.tsx", "webpack://app/./node_modules/zod/lib/index.js"]}
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        path = request.url.path
        if path.endswith("main.abc123.js"):
            return httpx.Response(200, text=BUNDLE)
        if path.endswith("main.abc123.js.map"):
            return httpx.Response(200, json=source_map)
        if path.endswith("_buildManifest.js"):
            return httpx.Response(200, text='self.__BUILD_MANIFEST={"/":[],"/changelog":[]}')
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await probe_code_intel(
            client,
            ["https://acme.com/_next/static/chunks/main.abc123.js", "https://internal.acme.com/app.js"],
            "https://acme.com/",
            build_id="build_42",
            resolver=_public,
        )

    assert result["available"] is True
    assert result["scripts_analyzed"] == 1
    assert "https://internal.acme.com/app.js" not in seen  # non-public host never fetched
    assert "/changelog" in result["routes"] and result["route_source"] == "Next.js build manifest"
    assert result["source_map"]["app_files"] == 1
    assert result["source_map"]["dependencies"] == ["zod"]
    assert result["secrets"][0]["masked"].startswith("sk_l")


@pytest.mark.asyncio
async def test_probe_code_intel_reports_absence_honestly() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404))) as client:
        result = await probe_code_intel(client, ["https://www.googletagmanager.com/gtm.js"], "https://acme.com/", resolver=_public)
    assert result["available"] is False and result["reason"]


def test_analyze_code_section_grades_secrets_and_exposure() -> None:
    signals = extract_code_signals(BUNDLE, "acme.com")
    probes = {"code": {
        "available": True, "scripts_analyzed": 1, "bytes_analyzed": 2048, "route_source": "router config",
        **signals, "endpoint_count": len(signals["endpoints"]), "route_count": len(signals["routes"]),
        "flag_count": len(signals["flags"]),
        "source_map": {"maps": 1, "files": 9, "app_files": 7, "dependencies": ["react"], "dependency_count": 1,
                       "areas": [{"area": "features/billing", "files": 4}], "language": "TypeScript", "sources_content": True},
    }}
    section = analyze_code(probes)
    statuses = {f["title"]: f["status"] for f in section["findings"]}
    assert statuses["Possible Stripe secret key in shipped JavaScript"] == "bad"
    assert statuses["Original source structure exposed"] == "bad"
    assert statuses["Non-production hosts referenced"] == "warn"
    assert section["metrics"][0] == {"label": "Bundles read", "value": "1"}
    assert analyze_code({"code": {"available": False}}) is None
