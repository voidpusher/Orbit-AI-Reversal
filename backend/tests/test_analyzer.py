from app.models import EvidenceItem
from app.services.ai import _fallback_synthesis
from app.services.analyzer import (
    AnalysisInputs,
    PageInfo,
    build_document,
    extract_inputs,
    infer_entities,
    infer_permissions,
    infer_user_flows,
)
from app.services.architecture import infer_architecture
from app.services.tech_detect import Detection, Signals, detect


def test_entities_unable_to_determine_without_account_features() -> None:
    # A marketing-only surface (no auth/dashboard/billing) must NOT fabricate a data model.
    result = infer_entities(AnalysisInputs("Acme", "acme.com", "https://acme.com"), features=[])
    assert result["items"] == []
    assert result["confidence"] < 40  # "unknown" per the confidence scale
    assert "unable to determine" in result["summary"].lower()
    assert "reasoning" in result


def test_entities_inferred_when_account_features_present() -> None:
    features = [{"name": "Authentication"}, {"name": "Projects & workspaces"}]
    result = infer_entities(AnalysisInputs("Acme", "acme.com", "https://acme.com"), features)
    names = {e["name"] for e in result["items"]}
    assert "User" in names and "Project" in names
    assert result["reasoning"]


def test_user_flows_unable_to_determine_without_journey_evidence() -> None:
    # Only documentation observed → no signup/billing/dev surface → no journeys.
    result = infer_user_flows(AnalysisInputs("Acme", "acme.com", "https://acme.com"), [{"name": "Documentation"}])
    assert result["flows"] == []
    assert result["confidence"] < 40
    assert "unable" in result["summary"].lower()


def test_user_flows_reconstructed_from_observed_surfaces() -> None:
    features = [{"name": "Authentication"}, {"name": "Billing & subscriptions"}]
    result = infer_user_flows(AnalysisInputs("Acme", "acme.com", "https://acme.com"), features)
    names = {f["name"] for f in result["flows"]}
    assert "Primary activation flow" in names and "Upgrade flow" in names
    assert result["reasoning"]


def test_permissions_unable_to_determine_without_account_surface() -> None:
    result = infer_permissions([{"name": "Documentation"}])
    assert result["roles"] == []
    assert result["confidence"] < 40
    assert "unable to determine" in result["summary"].lower()


def test_permissions_multi_tenant_when_teams_observed() -> None:
    result = infer_permissions([{"name": "Authentication"}, {"name": "Team collaboration"}])
    names = {r["name"] for r in result["roles"]}
    assert {"Owner", "Admin", "Member"} <= names
    assert result["reasoning"]


def _evidence(kind: str, url: str, meta: dict) -> EvidenceItem:
    item = EvidenceItem(analysis_id="a1", kind=kind, source_url=url, content_hash="x")
    item.metadata_json = meta
    return item


def test_tech_detection_from_hosts_and_markers() -> None:
    signals = Signals(
        hosts={"js.stripe.com", "cdn.segment.com", "app.company.vercel.app"},
        scripts=["https://js.stripe.com/v3"],
        html_markers=["__next_data__", "/graphql"],
        headers={"server": "Vercel", "cf-ray": "abc"},
    )
    names = {d.name for d in detect(signals)}
    assert {"Stripe", "Segment", "Next.js", "GraphQL", "Vercel", "Cloudflare"} <= names


def test_build_document_produces_all_sections() -> None:
    evidence = [
        _evidence("page", "https://linear.app/", {
            "title": "Linear – Issue tracking", "status_code": 200,
            "scripts": ["https://js.stripe.com/v3", "https://cdn.segment.com/analytics.js"],
            "markers": ["__next_data__", "/graphql"], "generator": None,
            "headers": {"server": "vercel", "strict-transport-security": "max-age=63072000"},
        }),
        _evidence("page", "https://linear.app/pricing", {"title": "Pricing", "status_code": 200, "scripts": [], "markers": [], "headers": {}}),
        _evidence("page", "https://linear.app/docs", {"title": "Docs", "status_code": 200, "scripts": [], "markers": [], "headers": {}}),
        _evidence("network_signal", "https://linear.app/graphql", {"host": "linear.app", "path": "/graphql", "status": 200}),
    ]
    inputs = extract_inputs("https://linear.app/", evidence)
    assert inputs.product_name == "Linear"
    assert "/graphql" in inputs.api_paths

    synthesis = _fallback_synthesis({
        "product_name": inputs.product_name, "host": inputs.host,
        "technologies": [{"name": "Next.js"}, {"name": "Stripe"}], "categories": ["Framework", "Payments"],
        "pages_explored": 3, "evidence_count": len(evidence),
    })
    document, claims = build_document(inputs, synthesis, len(evidence))

    for section in ("overview", "architecture", "user_flows", "features", "entities",
                    "permissions", "database", "api", "tech_stack", "integrations",
                    "insights", "infrastructure", "security"):
        assert section in document, section
        if section != "overview":
            assert "confidence" in document[section]

    assert document["meta"]["overall_confidence"] > 0
    assert document["api"]["style"] == "GraphQL"
    assert any(c["section"] == "tech_stack" for c in claims)
    assert document["features"]["items"], "should detect features from pricing/docs pages"


def test_architecture_reconstructs_topology_flows_and_boundaries() -> None:
    inputs = AnalysisInputs(
        product_name="Acme",
        host="acme.com",
        url="https://acme.com",
        pages=[PageInfo("https://acme.com", "/", "Acme", 200)],
        api_paths=["/graphql"],
        network_signals=[{
            "host": "api.acme.com", "path": "/graphql", "method": "POST",
            "status": 200, "resource_type": "fetch", "content_type": "application/json",
        }],
        page_signals=[{
            "next_data": {"present": True},
            "delivery": {"cache_control": "public, s-maxage=60"},
        }],
    )
    detections = [
        Detection("Next.js", "Framework", 92, ["__NEXT_DATA__"]),
        Detection("Cloudflare", "CDN", 94, ["cf-ray response header"]),
        Detection("GraphQL", "API", 90, ["/graphql network path"]),
        Detection("Supabase", "Database", 88, ["supabase.co host"]),
        Detection("Auth0", "Authentication", 91, ["auth0.com host"]),
        Detection("Stripe", "Payments", 96, ["js.stripe.com host"]),
        Detection("Pusher", "Realtime", 87, ["pusher.com host"]),
        Detection("Vercel", "Hosting", 90, ["server: Vercel"]),
    ]

    result = infer_architecture(inputs, detections)
    kinds = {node["kind"] for node in result["nodes"]}

    assert {"client", "edge", "frontend", "api", "data", "auth", "payment", "realtime"} <= kinds
    assert result["connections"]
    assert any(flow["name"] == "Application data flow" for flow in result["request_flows"])
    assert any(boundary["name"] == "First-party application to third parties" for boundary in result["trust_boundaries"])
    assert any(pattern["title"] == "Server-rendered or hybrid React delivery" for pattern in result["patterns"])
    assert all(node["classification"] in {"observed", "inferred"} for node in result["nodes"])
    assert all(node["responsibilities"] and node["evidence"] for node in result["nodes"])


def test_architecture_keeps_unobservable_internal_tiers_unknown() -> None:
    inputs = AnalysisInputs(
        product_name="Acme",
        host="acme.com",
        url="https://acme.com",
        pages=[PageInfo("https://acme.com", "/", "Acme", 200)],
    )

    result = infer_architecture(inputs, [])
    kinds = {node["kind"] for node in result["nodes"]}

    assert "api" not in kinds
    assert "data" not in kinds
    assert any("backend" in unknown.lower() for unknown in result["unknowns"])
    assert any("persistence" in unknown.lower() for unknown in result["unknowns"])


def test_blocked_target_caps_confidence_and_stops_at_delivery_edge() -> None:
    inputs = AnalysisInputs(
        product_name="Blocked",
        host="blocked.example",
        url="https://blocked.example",
        pages=[PageInfo("https://blocked.example", "/", "Access denied", 403)],
    )
    cloudflare = Detection("Cloudflare", "CDN", 93, ["server: cloudflare"])

    architecture = infer_architecture(inputs, [cloudflare])
    frontend = next(node for node in architecture["nodes"] if node["id"] == "frontend")

    assert architecture["confidence"] <= 30
    assert frontend["classification"] == "inferred"
    assert architecture["request_flows"][0]["steps"] == ["browser", "edge"]
    assert any("blocked" in item.lower() for item in architecture["unknowns"])

    synthesis = _fallback_synthesis({
        "product_name": inputs.product_name,
        "host": inputs.host,
        "technologies": [{"name": "Cloudflare"}],
        "categories": ["CDN"],
        "pages_explored": 1,
        "evidence_count": 1,
    })
    document, _ = build_document(inputs, synthesis, 1)
    assert document["meta"]["access_limited"] is True
    assert document["meta"]["access_statuses"] == [403]
    assert document["meta"]["overall_confidence"] <= 35
    metrics = {item["label"]: item["value"] for item in document["overview"]["metrics"]}
    assert metrics["Features observed"] == "N/A"
    assert metrics["Entities inferred"] == "N/A"
