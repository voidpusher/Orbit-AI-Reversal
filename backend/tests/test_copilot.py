from app.services.copilot import answer_report_question


def _document() -> dict:
    return {
        "architecture": {
            "nodes": [
                {
                    "id": "frontend", "label": "React frontend", "kind": "frontend",
                    "role": "Application shell", "responsibilities": ["Optimistic UI state"],
                    "classification": "observed", "confidence": 95,
                    "evidence": ["React runtime markers and client mutations observed"],
                },
                {
                    "id": "auth", "label": "Auth0", "kind": "auth",
                    "role": "Identity provider", "responsibilities": ["Issues session state"],
                    "classification": "observed", "confidence": 91,
                    "evidence": ["auth0.com host and OAuth callback observed"],
                },
                {
                    "id": "data", "label": "Relational store", "kind": "data",
                    "role": "Persistence", "responsibilities": ["Stores application state"],
                    "classification": "inferred", "confidence": 61,
                    "evidence": ["Relational response shapes"],
                },
            ],
            "connections": [
                {
                    "from": "frontend", "to": "auth", "label": "Identity exchange",
                    "protocol": "OAuth/OIDC", "classification": "observed", "confidence": 90,
                    "evidence": ["/oauth/callback request"],
                },
                {
                    "from": "frontend", "to": "data", "label": "State persistence",
                    "protocol": "Internal", "classification": "inferred", "confidence": 58,
                    "evidence": ["API returns stable relational identifiers"],
                },
            ],
            "request_flows": [
                {
                    "name": "Identity flow", "steps": ["browser", "frontend", "auth"],
                    "transport": "OAuth/OIDC", "classification": "observed", "confidence": 90,
                    "evidence": ["OAuth redirect and callback observed"],
                }
            ],
            "patterns": [],
            "unknowns": ["The session storage mechanism is not observable from the public surface."],
            "evidence": ["Public application and network behavior"],
        },
        "api": {
            "endpoints": [
                {"method": "POST", "path": "/api/billing/checkout", "confidence": 88, "note": "Observed in billing journey"},
                {"method": "GET", "path": "/api/issues", "confidence": 92, "note": "Observed issue query"},
            ]
        },
        "features": {"items": []},
        "integrations": {
            "items": [{"name": "Stripe", "category": "Payments", "confidence": 96, "evidence": ["js.stripe.com"]}]
        },
        "tech_stack": {"items": []},
        "insights": {"items": []},
        "user_flows": {"flows": []},
        "permissions": {"roles": []},
    }


def test_authentication_answer_cites_observed_report_evidence() -> None:
    result = answer_report_question(_document(), "How does authentication probably work?")

    assert result["citations"]
    assert "[E1]" in result["answer"]
    assert any("Auth0" in citation["title"] for citation in result["citations"])
    assert result["basis"] in {"observed", "mixed"}


def test_billing_endpoint_answer_returns_only_relevant_endpoint() -> None:
    result = answer_report_question(_document(), "Show all billing-related endpoints")

    assert "/api/billing/checkout" in result["answer"]
    assert "/api/issues" not in result["answer"]
    assert any(citation["section"] == "API" for citation in result["citations"])


def test_uncertainty_answer_labels_inferred_claims() -> None:
    result = answer_report_question(_document(), "What parts of this architecture are uncertain?")

    assert "session storage" in result["answer"].lower()
    assert result["citations"]
    assert any(citation["classification"] == "inferred" for citation in result["citations"])


def test_system_design_answer_is_evidence_grounded() -> None:
    result = answer_report_question(_document(), "Generate a system-design interview explanation")

    assert "system-design interview" in result["answer"]
    assert result["citations"]
    assert all(citation["evidence"] for citation in result["citations"])
    assert result["limitations"]
