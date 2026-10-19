from app.models import EvidenceItem
from app.schemas import HarEntryRequest
from app.services.ai import _fallback_synthesis
from app.services.analyzer import AnalysisInputs, build_document, extract_inputs, infer_entities
from app.services.bundle_intel import extract_code_signals
from app.services.har_import import sanitize_field_paths, sanitize_har_entry


def _evidence(kind: str, url: str, meta: dict) -> EvidenceItem:
    item = EvidenceItem(analysis_id="a1", kind=kind, source_url=url, content_hash="x")
    item.metadata_json = meta
    return item


def test_sanitize_field_paths_keeps_schema_and_masks_identifier_keys() -> None:
    cleaned = sanitize_field_paths([
        "data[].id:string",
        "data[].title:string",
        "usersById.u_8f3k29dk3j20:object",   # dynamic key → masked
        "contacts.jane@acme.com:string",      # email-shaped key → rejected by the key rules
        "data[].title:string",                # duplicate
        "token=abc123:string",                # not a field path
        "a..b:string",                        # empty segment
        "deep.a.b.c.d.e.f.g.h:number",        # depth capped
    ])
    assert cleaned[:3] == ["data[].id:string", "data[].title:string", "usersById.:key:object"]
    assert all("jane" not in item and "abc123" not in item for item in cleaned)
    assert "deep.a.b.c.d.e:number" in cleaned


def test_har_entry_carries_value_free_shapes() -> None:
    _, metadata = sanitize_har_entry(HarEntryRequest(
        url="https://api.acme.com/v1/projects/918273?session=private",
        method="GET", status=200, resource_type="fetch",
        response_fields=["data.id:string", "data.name:string", "data.owner_id:string"],
        request_fields=[],
    ))
    assert metadata["response_fields"] == ["data.id:string", "data.name:string", "data.owner_id:string"]
    assert "request_fields" not in metadata


def test_entities_are_observed_from_response_shapes() -> None:
    inputs = AnalysisInputs("Acme", "acme.com", "https://acme.com")
    inputs.api_calls = [
        {"method": "GET", "path": "/api/v1/projects/:id", "status": 200, "request_fields": [],
         "response_fields": ["data.id:string", "data.name:string", "data.team_id:string", "meta.request_id:string"]},
        {"method": "GET", "path": "/api/v1/teams", "status": 200, "request_fields": [],
         "response_fields": ["items[].id:string", "items[].name:string", "items[].plan:string", "pagination.next:string"]},
    ]
    result = infer_entities(inputs, features=[])
    by_name = {e["name"]: e for e in result["items"]}
    assert by_name["Project"]["fields"] == ["id", "name", "team_id"]
    assert by_name["Project"]["classification"] == "observed"
    assert by_name["Team"]["fields"] == ["id", "name", "plan"]
    assert {"from": "Team", "to": "Project", "kind": "1:N"} in result["relationships"]
    assert "observed" in result["summary"]


def test_build_document_merges_code_intel_and_observed_calls() -> None:
    bundle = 'fetch("/api/v1/invoices",{method:"POST"});n.variation("usage-billing");var r={path:"/settings/billing"};'
    signals = extract_code_signals(bundle, "acme.com")
    probes = {"code": {
        "available": True, "scripts_analyzed": 1, "bytes_analyzed": len(bundle), "route_source": "router config",
        **signals, "endpoint_count": len(signals["endpoints"]), "route_count": len(signals["routes"]),
        "flag_count": len(signals["flags"]), "source_map": None,
    }}
    evidence = [
        _evidence("page", "https://acme.com/", {"title": "Acme", "status_code": 200, "scripts": [], "markers": [], "headers": {}}),
        _evidence("network_signal", "https://acme.com/api/v1/projects/:id", {
            "host": "acme.com", "path": "/api/v1/projects/:id", "status": 200, "method": "PATCH",
            "request_fields": ["name:string"], "response_fields": ["id:string", "name:string"],
        }),
        _evidence("site_probe", "https://acme.com/", probes),
    ]
    inputs = extract_inputs("https://acme.com/", evidence)
    synthesis = _fallback_synthesis({"product_name": "Acme", "host": "acme.com", "technologies": [], "categories": [],
                                     "pages_explored": 1, "evidence_count": len(evidence)})
    document, claims = build_document(inputs, synthesis, len(evidence))

    endpoints = {(e["method"], e["path"]): e for e in document["api"]["endpoints"]}
    assert endpoints[("PATCH", "/api/v1/projects/:id")]["request_fields"] == ["name:string"]
    assert endpoints[("POST", "/api/v1/invoices")]["note"] == "Referenced in shipped JavaScript"
    assert document["code_intel"]["flags"] == [{"key": "usage-billing", "provider": "LaunchDarkly"}]
    billing = next(f for f in document["features"]["items"] if f["name"] == "Billing & subscriptions")
    assert any("shipped JavaScript" in citation for citation in billing["evidence"])
    assert any(c["section"] == "code_intel" for c in claims)
