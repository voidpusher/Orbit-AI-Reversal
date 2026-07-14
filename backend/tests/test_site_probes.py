import httpx
import pytest

from app.services.deep_analysis import analyze_domain, analyze_performance, analyze_security, analyze_seo
from app.services.page_signals import extract_page_signals
from app.services.site_probes import _parse_cert_datetime, probe_robots

ROBOTS_TXT = """
# example
User-agent: *
Disallow: /admin
Disallow: /api/internal
Allow: /api/public

User-agent: GPTBot
Disallow: /

User-agent: CCBot
Disallow: /

Sitemap: https://acme.com/sitemap.xml
"""


def test_parse_cert_datetime_handles_space_padded_day() -> None:
    dt = _parse_cert_datetime("Jun  1 00:00:00 2026 GMT")
    assert dt.year == 2026 and dt.month == 6 and dt.day == 1


@pytest.mark.asyncio
async def test_probe_robots_parses_rules_and_ai_blocks() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=ROBOTS_TXT, headers={"content-type": "text/plain"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await probe_robots(client, "https://acme.com")

    assert result["present"] is True
    assert result["disallow_count"] == 4  # /admin, /api/internal, and two "/" for AI bots
    assert "/admin" in result["sample_disallows"]
    assert set(result["blocks_ai_bots"]) == {"gptbot", "ccbot"}
    assert result["sitemaps"] == ["https://acme.com/sitemap.xml"]


def _signals():
    return extract_page_signals("<html><head><title>x</title></head><body>lots of text here to be ssr</body></html>",
                                {"content-security-policy": "default-src 'self'"}, "https://acme.com/", "HTTP/2", 200, [])


def test_probes_enrich_deep_sections() -> None:
    probes = {
        "tls": {"available": True, "protocol": "TLSv1.3", "cipher": "TLS_AES_256_GCM_SHA384",
                "cipher_bits": 256, "issuer": "Let's Encrypt", "san_count": 3, "wildcard": True,
                "valid_until": "2026-09-01T00:00:00+00:00", "days_until_expiry": 60},
        "bundles": {"available": True, "analyzed": 6, "total_bytes": 2_400_000, "largest_url": "https://acme.com/_next/x.js",
                    "largest_bytes": 500_000, "sourcemaps_exposed": 2},
        "robots": {"present": True, "disallow_count": 3, "sample_disallows": ["/admin"], "blocks_ai_bots": ["gptbot"], "sitemaps": []},
        "sitemap": {"present": True, "kind": "url set", "entry_count": 1240, "url": "https://acme.com/sitemap.xml"},
    }
    sec = analyze_security([_signals()], probes)
    assert any("TLS certificate" in f["title"] for f in sec["findings"])
    assert any(m["label"] == "TLS" for m in sec["metrics"])

    perf = analyze_performance([_signals()], probes)
    assert any("JavaScript payload" in f["title"] for f in perf["findings"])
    assert any(f["status"] == "bad" and "Source maps" in f["title"] for f in perf["findings"])

    seo = analyze_seo([_signals()], probes)
    titles = " ".join(f["title"] for f in seo["findings"])
    assert "AI crawlers" in titles and "Sitemap" in titles


def test_analyze_domain_grades_email_and_disclosure() -> None:
    probes = {
        "dns": {
            "available": True, "mx_count": 5, "email_provider": "Google Workspace",
            "ns_provider": "AWS Route 53", "has_spf": True, "spf_senders": ["Stripe"],
            "dmarc_policy": "reject", "verified_tools": ["DocuSign", "Atlassian"], "caa_issuers": ["digicert.com"],
        },
        "redirect": {"checked": True, "status": 301, "redirects_to_https": True},
        "security_txt": {"present": True, "contact": "https://hackerone.com/acme", "has_policy": True},
    }
    section = analyze_domain(probes)
    assert section is not None
    titles = [f["title"] for f in section["findings"]]
    assert "DMARC enforced" in titles
    assert any("HTTP → HTTPS" in t for t in titles)
    assert any("security.txt" in t for t in titles)
    assert any("SaaS tools via DNS" in t for t in titles)
    assert section["grade"] in {"A", "B"}
    assert any(m["label"] == "Email" and m["value"] == "Google Workspace" for m in section["metrics"])


def test_analyze_domain_absent_without_dns() -> None:
    assert analyze_domain({"dns": {"available": False}}) is None


OPENAPI = {
    "openapi": "3.0.1",
    "info": {"title": "Acme API", "version": "2.1.0"},
    "paths": {"/v1/users": {"get": {}, "post": {}}, "/v1/orders": {"get": {}}},
    "servers": [{"url": "https://api.acme.com"}],
}


@pytest.mark.asyncio
async def test_probe_api_reads_openapi_and_graphql_introspection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/openapi.json":
            return httpx.Response(200, json=OPENAPI)
        if path == "/graphql" and request.method == "POST":
            return httpx.Response(200, json={"data": {"__schema": {
                "queryType": {"name": "Query"}, "mutationType": {"name": "Mutation"},
                "types": [{"name": "User", "kind": "OBJECT"}, {"name": "__Type", "kind": "OBJECT"}],
            }}})
        return httpx.Response(404)

    from app.services.site_probes import probe_api
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://acme.com") as client:
        result = await probe_api(client, "https://acme.com")

    assert result["openapi"]["title"] == "Acme API"
    assert result["openapi"]["path_count"] == 2
    assert {(o["method"], o["path"]) for o in result["openapi"]["operations"]} >= {("GET", "/v1/users"), ("POST", "/v1/users")}
    assert result["graphql"]["introspection_enabled"] is True
    assert result["graphql"]["type_count"] == 1  # __Type excluded


@pytest.mark.asyncio
async def test_probe_wellknown_detects_mobile_apps() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "apple-app-site-association" in request.url.path:
            return httpx.Response(200, json={"applinks": {"details": [{"appIDs": ["TEAM.com.acme.app"]}]}})
        if "assetlinks.json" in request.url.path:
            return httpx.Response(200, json=[{"target": {"package_name": "com.acme.android"}}])
        return httpx.Response(404)

    from app.services.site_probes import probe_wellknown
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://acme.com") as client:
        result = await probe_wellknown(client, "https://acme.com")

    assert result["ios_app"] and result["android_app"]
    assert result["ios_app_ids"] == ["TEAM.com.acme.app"]
    assert result["android_packages"] == ["com.acme.android"]


def test_infer_api_uses_openapi_and_flags_introspection() -> None:
    from app.services.analyzer import AnalysisInputs, infer_api
    probes = {"api": {
        "openapi": {"url": "https://acme.com/openapi.json", "title": "Acme API", "version": "2.1.0",
                    "spec_version": "3.0.1", "path_count": 12,
                    "operations": [{"method": "GET", "path": "/v1/users"}]},
        "graphql": {"endpoint": "https://acme.com/graphql", "introspection_enabled": True, "type_count": 80},
    }}
    section = infer_api(AnalysisInputs(product_name="Acme", host="acme.com", url="https://acme.com"), [], probes)
    assert section["spec"]["path_count"] == 12
    assert any(e["path"] == "/v1/users" and e["note"] == "From OpenAPI spec" for e in section["endpoints"])
    titles = [f["title"] for f in section["findings"]]
    assert "Public OpenAPI specification" in titles
    assert "GraphQL introspection enabled" in titles
