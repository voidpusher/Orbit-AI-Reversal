from app.models import Report
from app.services.compare import build_comparison


def _report(name: str, techs: list[tuple[str, str, int]], features: list[str], insights: list[str], arch: list[str], confidence: int) -> Report:
    report = Report(
        id=name.lower(),
        analysis_id=f"an-{name}",
        target_url=f"https://{name.lower()}.com",
        product_name=name,
        headline="",
        overall_confidence=confidence,
        pages_explored=5,
        evidence_count=40,
        features_count=len(features),
    )
    report.document = {
        "meta": {"host": f"{name.lower()}.com", "technologies_count": len(techs)},
        "tech_stack": {"items": [{"name": n, "category": c, "confidence": conf} for n, c, conf in techs]},
        "features": {"items": [{"name": f} for f in features]},
        "insights": {"items": [{"title": t} for t in insights]},
        "architecture": {"nodes": [{"label": label} for label in arch]},
    }
    return report


def test_build_comparison_diffs_tech_and_features() -> None:
    a = _report(
        "Linear",
        [("Next.js", "Framework", 92), ("Stripe", "Payments", 90), ("GraphQL", "API", 80)],
        ["Authentication", "Projects & workspaces", "Billing & subscriptions"],
        ["Realtime synchronization", "Optimistic UI updates"],
        ["Browser", "Next.js", "API layer", "Data services"],
        94,
    )
    b = _report(
        "Notion",
        [("Next.js", "Framework", 90), ("Amplitude", "Analytics", 84)],
        ["Authentication", "Documentation"],
        ["Optimistic UI updates"],
        ["Browser", "Next.js", "API layer"],
        88,
    )

    result = build_comparison(a, b)

    assert [t["name"] for t in result["shared_tech"]] == ["Next.js"]
    assert {t["name"] for t in result["only_a_tech"]} == {"Stripe", "GraphQL"}
    assert {t["name"] for t in result["only_b_tech"]} == {"Amplitude"}
    assert result["shared_features"] == ["Authentication"]
    assert "Projects & workspaces" in result["only_a_features"]
    assert result["shared_insights"] == ["Optimistic UI updates"]
    assert result["confidence_delta"] == 6
    assert 0 <= result["similarity"] <= 100
    assert "Linear" in result["headline"] and "Notion" in result["headline"]
