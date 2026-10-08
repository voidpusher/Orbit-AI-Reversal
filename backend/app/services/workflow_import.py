from __future__ import annotations

import hashlib
from urllib.parse import urlsplit, urlunsplit

from app.models import EvidenceItem
from app.schemas import WorkflowStepRequest
from app.services.har_import import normalize_har_path


def _safe_url(value: str | None, fallback: str) -> str:
    try:
        parsed = urlsplit(value or fallback)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError
        path = normalize_har_path(parsed.path or "/")
        port = f":{parsed.port}" if parsed.port else ""
        return urlunsplit((parsed.scheme, f"{parsed.hostname.lower()}{port}", path, "", ""))
    except ValueError:
        return fallback


def build_workflow_evidence(
    analysis_id: str,
    target_url: str,
    title: str,
    steps: list[WorkflowStepRequest],
) -> EvidenceItem:
    sanitized_steps: list[dict] = []
    for index, step in enumerate(steps):
        item: dict[str, str | int] = {"id": f"capture-{index + 1}", "type": step.type}
        if step.selector:
            item["selector"] = step.selector.strip()[:500]
        if step.url:
            item["url"] = _safe_url(step.url, target_url)
        if step.key:
            item["key"] = step.key.strip()[:40]
        if step.value_kind:
            item["value_kind"] = step.value_kind
            item["value_length"] = step.value_length or 0
        sanitized_steps.append(item)

    fingerprint = "|".join(
        f"{item.get('type')}:{item.get('selector', '')}:{item.get('url', '')}"
        for item in sanitized_steps
    )
    return EvidenceItem(
        analysis_id=analysis_id,
        kind="workflow_capture",
        source_url=target_url,
        content_hash=hashlib.sha256(fingerprint.encode()).hexdigest(),
        metadata_json={
            "title": title.strip()[:160],
            "steps": sanitized_steps,
            "step_count": len(sanitized_steps),
            "capture_engine": "chrome-devtools-recorder",
        },
        redaction_version="workflow-v1",
    )
