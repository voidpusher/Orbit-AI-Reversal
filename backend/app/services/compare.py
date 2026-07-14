"""Structured diff of two reports for Compare Mode.

Pure function over two persisted reports. It contrasts observable technology,
detected features, engineering insights, and architecture shape so the UI can
present an honest side-by-side without re-running any analysis.
"""

from __future__ import annotations

from app.models import Report


def _tech_index(report: Report) -> dict[str, dict]:
    return {t["name"]: t for t in report.document.get("tech_stack", {}).get("items", [])}


def _feature_names(report: Report) -> set[str]:
    return {f["name"] for f in report.document.get("features", {}).get("items", [])}


def _insight_titles(report: Report) -> set[str]:
    return {i["title"] for i in report.document.get("insights", {}).get("items", [])}


def _side(report: Report) -> dict:
    meta = report.document.get("meta", {})
    return {
        "id": report.id,
        "product_name": report.product_name,
        "host": meta.get("host", ""),
        "target_url": report.target_url,
        "overall_confidence": report.overall_confidence,
        "pages_explored": report.pages_explored,
        "evidence_count": report.evidence_count,
        "features_count": report.features_count,
        "technologies_count": meta.get("technologies_count", 0),
    }


def _tech_items(index: dict[str, dict], names: list[str]) -> list[dict]:
    return [
        {"name": n, "category": index[n].get("category", ""), "confidence": index[n].get("confidence", 0)}
        for n in names
    ]


def _arch_labels(report: Report) -> list[str]:
    return [n["label"] for n in report.document.get("architecture", {}).get("nodes", [])]


def build_comparison(a: Report, b: Report) -> dict:
    tech_a, tech_b = _tech_index(a), _tech_index(b)
    shared_tech = sorted(set(tech_a) & set(tech_b), key=lambda n: tech_a[n].get("confidence", 0), reverse=True)
    only_a_tech = sorted(set(tech_a) - set(tech_b), key=lambda n: tech_a[n].get("confidence", 0), reverse=True)
    only_b_tech = sorted(set(tech_b) - set(tech_a), key=lambda n: tech_b[n].get("confidence", 0), reverse=True)

    feats_a, feats_b = _feature_names(a), _feature_names(b)
    ins_a, ins_b = _insight_titles(a), _insight_titles(b)

    overlap = len(feats_a & feats_b)
    union = len(feats_a | feats_b) or 1
    similarity = round(overlap / union * 100)

    headline = (
        f"{a.product_name} and {b.product_name} share {len(shared_tech)} technolog"
        f"{'y' if len(shared_tech) == 1 else 'ies'} and {overlap} feature area"
        f"{'' if overlap == 1 else 's'} ({similarity}% product-surface similarity)."
    )

    return {
        "a": _side(a),
        "b": _side(b),
        "similarity": similarity,
        "confidence_delta": a.overall_confidence - b.overall_confidence,
        "headline": headline,
        "shared_tech": _tech_items(tech_a, shared_tech),
        "only_a_tech": _tech_items(tech_a, only_a_tech),
        "only_b_tech": _tech_items(tech_b, only_b_tech),
        "shared_features": sorted(feats_a & feats_b),
        "only_a_features": sorted(feats_a - feats_b),
        "only_b_features": sorted(feats_b - feats_a),
        "shared_insights": sorted(ins_a & ins_b),
        "architecture_a": _arch_labels(a),
        "architecture_b": _arch_labels(b),
    }
