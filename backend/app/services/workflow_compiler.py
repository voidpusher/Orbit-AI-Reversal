"""Compile report evidence into an evidence-backed workflow contract.

The compiler is intentionally deterministic. It never upgrades inferred report
claims into observed automation steps, and it keeps missing selectors and
request bodies visible as blockers instead of fabricating them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _CandidateEndpoint:
    method: str
    path: str
    confidence: int
    note: str
    score: int


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "workflow"


def _terms(value: str) -> set[str]:
    ignored = {
        "a", "an", "and", "api", "app", "core", "flow", "for", "from",
        "in", "of", "on", "primary", "the", "to", "user", "with",
    }
    return {
        word for word in re.findall(r"[a-z0-9]+", value.lower())
        if len(word) > 2 and word not in ignored
    }


def _classification(value: object, default: str = "inferred") -> str:
    return "observed" if str(value).lower() == "observed" else default


def _endpoint_candidates(document: dict, flow_text: str, *, include_session_scope: bool = False) -> list[_CandidateEndpoint]:
    flow_terms = _terms(flow_text)
    candidates: list[_CandidateEndpoint] = []
    for endpoint in (document.get("api") or {}).get("endpoints") or []:
        method = str(endpoint.get("method") or "GET").upper()
        path = str(endpoint.get("path") or "").strip()
        if not path:
            continue
        note = str(endpoint.get("note") or "Observed API operation")
        endpoint_terms = _terms(f"{method} {path} {note}")
        overlap = len(flow_terms & endpoint_terms)
        confidence = max(0, min(100, int(endpoint.get("confidence") or 50)))
        if overlap or include_session_scope:
            score = overlap * 30 + confidence
            candidates.append(_CandidateEndpoint(method, path, confidence, note, score))
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def _escape_ts(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _regex_source(value: str) -> str:
    return _escape_ts(re.escape(value))


def _playwright(contract: dict) -> str:
    target = _escape_ts(str(contract["target_url"]))
    name = _escape_ts(str(contract["name"]))
    lines = [
        "import { test, expect } from '@playwright/test';",
        "",
        f"test('{name}', async ({{ page }}) => {{",
        f"  await page.goto('{target}');",
    ]

    endpoints = contract.get("endpoints") or []
    for index, step in enumerate(contract.get("steps") or []):
        action = str(step["action"])
        safe_action = _escape_ts(action)
        action_pattern = _regex_source(action)
        lines.append("")
        lines.append(f"  await test.step('{safe_action}', async () => {{")
        selector = _escape_ts(str(step.get("selector") or ""))
        if step["kind"] == "navigate":
            destination = _escape_ts(str(step.get("url") or contract["target_url"]))
            lines.append(f"    await page.goto('{destination}');")
        elif step["kind"] == "assertion":
            if selector:
                lines.append(f"    await expect(page.locator('{selector}').first()).toBeVisible();")
            else:
                lines.append(f"    await expect(page.getByText(new RegExp('{action_pattern}', 'i')).first()).toBeVisible();")
        elif step["kind"] == "input":
            variable = re.sub(r"[^A-Z0-9]+", "_", str(step.get("input_kind") or "text").upper()).strip("_")
            lines.append(f"    await page.locator('{selector}').fill(process.env.ORBIT_INPUT_{variable} ?? '');")
        elif step["kind"] == "keyboard":
            key = _escape_ts(str(step.get("key") or "Enter"))
            lines.append(f"    await page.keyboard.press('{key}');")
        elif step["kind"] == "scroll":
            lines.append("    await page.mouse.wheel(0, 600);")
        else:
            endpoint = endpoints[min(index - 1, len(endpoints) - 1)] if endpoints and index else None
            if endpoint:
                path = _escape_ts(str(endpoint["path"]))
                method = _escape_ts(str(endpoint["method"]))
                lines.append("    const operation = page.waitForResponse((response) =>")
                lines.append(f"      response.url().includes('{path}') && response.request().method() === '{method}',")
                lines.append("    );")
            if selector:
                lines.append(f"    await page.locator('{selector}').click();")
            else:
                lines.append(f"    const action = new RegExp('{action_pattern}', 'i');")
                lines.append("    await page.getByRole('button', { name: action }).or(page.getByRole('link', { name: action })).first().click();")
            if endpoint:
                lines.append("    await operation;")
        lines.append("  });")

    lines.extend(["});", ""])
    return "\n".join(lines)


def available_workflows(document: dict) -> list[dict]:
    """Return report journeys that can be compiled, with no invented fallback."""
    result: list[dict] = []
    seen: set[str] = set()
    for flow in (document.get("user_flows") or {}).get("flows") or []:
        name = str(flow.get("name") or "").strip()
        steps = [str(step) for step in flow.get("steps") or [] if str(step).strip()]
        if not name or not steps or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        result.append({
            "name": name,
            "steps": len(steps),
            "confidence": max(0, min(100, int(flow.get("confidence") or 50))),
            "classification": _classification(flow.get("classification")),
        })
    return result


def compile_workflow(document: dict, flow_name: str) -> dict:
    """Compile a named report journey into a transparent automation contract."""
    user_flows = (document.get("user_flows") or {}).get("flows") or []
    flow = next(
        (item for item in user_flows if str(item.get("name") or "").casefold() == flow_name.strip().casefold()),
        None,
    )
    if flow is None:
        raise ValueError("The selected workflow is not available in this report")

    actions = [str(step).strip() for step in flow.get("steps") or [] if str(step).strip()]
    if not actions:
        raise ValueError("The selected workflow has no usable steps")

    meta = document.get("meta") or {}
    architecture = document.get("architecture") or {}
    architecture_flows = architecture.get("request_flows") or []
    related_arch_flow = max(
        architecture_flows,
        key=lambda item: len(_terms(str(item.get("name") or "")) & _terms(flow_name)),
        default=None,
    )
    capture_steps = [step for step in flow.get("capture_steps") or [] if isinstance(step, dict)]
    flow_text = " ".join([flow_name, *actions])
    endpoints = _endpoint_candidates(document, flow_text, include_session_scope=bool(capture_steps))[:4]

    flow_classification = _classification(flow.get("classification"))
    base_confidence = max(0, min(100, int(flow.get("confidence") or 50)))
    evidence: list[dict] = []

    reasoning = str((document.get("user_flows") or {}).get("reasoning") or "").strip()
    if reasoning:
        evidence.append({
            "id": "E1", "source": "User-flow reasoning", "detail": reasoning,
            "classification": flow_classification, "confidence": base_confidence,
        })

    for detail in flow.get("evidence") or []:
        evidence.append({
            "id": f"E{len(evidence) + 1}", "source": "Workflow recording", "detail": str(detail),
            "classification": flow_classification, "confidence": base_confidence,
        })

    if related_arch_flow:
        for detail in related_arch_flow.get("evidence") or []:
            evidence.append({
                "id": f"E{len(evidence) + 1}", "source": "Architecture request path",
                "detail": str(detail),
                "classification": _classification(related_arch_flow.get("classification")),
                "confidence": max(0, min(100, int(related_arch_flow.get("confidence") or 50))),
            })

    endpoint_payload: list[dict] = []
    for endpoint in endpoints:
        evidence_id = f"E{len(evidence) + 1}"
        evidence.append({
            "id": evidence_id, "source": "API operation", "detail": endpoint.note,
            "classification": "observed" if endpoint.confidence >= 80 else "inferred",
            "confidence": endpoint.confidence,
        })
        endpoint_payload.append({
            "method": endpoint.method, "path": endpoint.path, "confidence": endpoint.confidence,
            "classification": "observed" if endpoint.confidence >= 80 else "inferred",
            "evidence_ids": [evidence_id],
        })

    steps: list[dict] = []
    for index, action in enumerate(actions):
        captured = capture_steps[index] if index < len(capture_steps) else {}
        captured_type = str(captured.get("type") or "")
        if captured_type == "navigate":
            kind = "navigate"
        elif captured_type == "change":
            kind = "input"
        elif captured_type == "keyDown":
            kind = "keyboard"
        elif captured_type == "scroll":
            kind = "scroll"
        elif captured_type == "waitForElement":
            kind = "assertion"
        elif captured_type == "click":
            kind = "interaction"
        elif index == 0:
            kind = "navigate"
        elif index == len(actions) - 1:
            kind = "assertion"
        else:
            kind = "interaction"
        step_evidence = [item["id"] for item in evidence[:2]]
        steps.append({
            "id": f"step-{index + 1}", "order": index + 1, "action": action, "kind": kind,
            "classification": flow_classification, "confidence": base_confidence,
            "evidence_ids": step_evidence,
            "requires_review": flow_classification != "observed" or (kind in {"interaction", "input", "assertion"} and not captured.get("selector")),
            **({"selector": str(captured.get("selector"))} if captured.get("selector") else {}),
            **({"url": str(captured.get("url"))} if captured.get("url") else {}),
            **({"key": str(captured.get("key"))} if captured.get("key") else {}),
            **({"input_kind": str(captured.get("value_kind"))} if captured.get("value_kind") else {}),
        })

    observed_count = sum(item["classification"] == "observed" for item in evidence)
    reviewed_steps = sum(not step["requires_review"] for step in steps)
    readiness = min(98, round((reviewed_steps / max(1, len(steps))) * 65 + (observed_count / max(1, len(evidence))) * 20 + (len(endpoints) > 0) * 13))
    blockers: list[str] = []
    if not capture_steps or flow_classification != "observed":
        blockers.append("Journey actions are inferred; capture the workflow to confirm their order.")
    if any(step["requires_review"] and step["kind"] in {"interaction", "input", "assertion"} for step in steps):
        blockers.append("One or more interactive element selectors are missing and must be confirmed.")
    if not endpoints:
        blockers.append("No request was correlated to this journey; import an authenticated HAR capture.")

    unknowns = [str(item) for item in architecture.get("unknowns") or []][:3]
    unknowns.extend(blockers)
    contract = {
        "version": "orbit.workflow.v1",
        "id": f"{_slug(str(meta.get('host') or 'product'))}.{_slug(flow_name)}",
        "name": flow_name,
        "product_name": str(meta.get("product_name") or "Product"),
        "target_url": str(meta.get("url") or "https://example.com"),
        "classification": "observed" if flow_classification == "observed" and observed_count else "inferred",
        "confidence": base_confidence,
        "automation_readiness": readiness,
        "status": "ready" if readiness >= 80 and not blockers else "review_required",
        "steps": steps,
        "endpoints": endpoint_payload,
        "evidence": evidence,
        "unknowns": list(dict.fromkeys(unknowns)),
    }
    return {
        "contract": contract,
        "playwright": _playwright(contract),
        "contract_json": json.dumps(contract, indent=2, ensure_ascii=False),
    }
