"""Evidence-grounded question answering over an Orbit report.

The copilot is deliberately retrieval-first and deterministic. It never answers from
general model memory: every response is composed from persisted report claims and
returns the exact report records used as citations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_STOP_WORDS = {
    "a", "all", "an", "and", "are", "as", "at", "be", "does", "for", "from",
    "how", "i", "in", "is", "it", "me", "of", "on", "or", "probably", "show",
    "that", "the", "this", "to", "uses", "what", "would",
}


@dataclass
class EvidenceChunk:
    key: str
    section: str
    title: str
    detail: str
    evidence: list[str]
    classification: str
    confidence: int

    @property
    def searchable(self) -> str:
        return " ".join([self.section, self.title, self.detail, *self.evidence]).lower()


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9][a-z0-9._/-]+", value.lower())
        if token not in _STOP_WORDS and len(token) > 1
    }


def _classification(value: Any, default: str = "inferred") -> str:
    candidate = str(value or default).lower()
    return candidate if candidate in {"observed", "inferred"} else default


def _confidence(value: Any, default: int = 55) -> int:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return default


def _strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def build_evidence_index(document: dict[str, Any]) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    architecture = document.get("architecture") or {}
    for index, node in enumerate(architecture.get("nodes") or []):
        responsibilities = "; ".join(_strings(node.get("responsibilities")))
        chunks.append(EvidenceChunk(
            key=f"architecture.node.{index}", section="Architecture",
            title=str(node.get("label") or node.get("kind") or "Component"),
            detail=". ".join(part for part in [str(node.get("role") or ""), responsibilities] if part),
            evidence=_strings(node.get("evidence")),
            classification=_classification(node.get("classification")),
            confidence=_confidence(node.get("confidence")),
        ))
    for index, connection in enumerate(architecture.get("connections") or []):
        chunks.append(EvidenceChunk(
            key=f"architecture.connection.{index}", section="Architecture",
            title=f"{connection.get('from', '?')} → {connection.get('to', '?')}",
            detail=f"{connection.get('label', 'Connection')} over {connection.get('protocol', 'unknown transport')}",
            evidence=_strings(connection.get("evidence")),
            classification=_classification(connection.get("classification")),
            confidence=_confidence(connection.get("confidence")),
        ))
    for index, flow in enumerate(architecture.get("request_flows") or []):
        chunks.append(EvidenceChunk(
            key=f"architecture.flow.{index}", section="Architecture",
            title=str(flow.get("name") or "Request flow"),
            detail=f"{' → '.join(_strings(flow.get('steps')))} via {flow.get('transport', 'unknown transport')}",
            evidence=_strings(flow.get("evidence")),
            classification=_classification(flow.get("classification")),
            confidence=_confidence(flow.get("confidence")),
        ))
    for index, pattern in enumerate(architecture.get("patterns") or []):
        chunks.append(EvidenceChunk(
            key=f"architecture.pattern.{index}", section="Architecture",
            title=str(pattern.get("title") or "Architecture pattern"),
            detail=str(pattern.get("detail") or ""), evidence=_strings(pattern.get("evidence")),
            classification=_classification(pattern.get("classification")),
            confidence=_confidence(pattern.get("confidence")),
        ))
    for index, unknown in enumerate(architecture.get("unknowns") or []):
        chunks.append(EvidenceChunk(
            key=f"architecture.unknown.{index}", section="Architecture uncertainty",
            title="Unresolved architecture detail", detail=str(unknown), evidence=[str(unknown)],
            classification="inferred", confidence=25,
        ))

    for section_name, key in (("Features", "features"), ("Integrations", "integrations"), ("Technology", "tech_stack"), ("Insights", "insights")):
        section = document.get(key) or {}
        for index, item in enumerate(section.get("items") or []):
            title = str(item.get("name") or item.get("title") or "Report claim")
            detail = str(item.get("description") or item.get("detail") or item.get("category") or "")
            chunks.append(EvidenceChunk(
                key=f"{key}.{index}", section=section_name, title=title, detail=detail,
                evidence=_strings(item.get("evidence")),
                classification=_classification(item.get("classification"), "observed"),
                confidence=_confidence(item.get("confidence")),
            ))

    api = document.get("api") or {}
    for index, endpoint in enumerate(api.get("endpoints") or []):
        method = str(endpoint.get("method") or "GET").upper()
        path = str(endpoint.get("path") or "/")
        note = str(endpoint.get("note") or "Observed API surface")
        chunks.append(EvidenceChunk(
            key=f"api.endpoint.{index}", section="API", title=f"{method} {path}", detail=note,
            evidence=[note, path], classification="observed", confidence=_confidence(endpoint.get("confidence")),
        ))

    for section_name, key in (("User flows", "user_flows"), ("Permissions", "permissions")):
        section = document.get(key) or {}
        items = section.get("flows") if key == "user_flows" else section.get("roles")
        for index, item in enumerate(items or []):
            title = str(item.get("name") or "Product behavior")
            values = item.get("steps") if key == "user_flows" else item.get("capabilities")
            chunks.append(EvidenceChunk(
                key=f"{key}.{index}", section=section_name, title=title,
                detail=" → ".join(_strings(values)) if key == "user_flows" else "; ".join(_strings(values)),
                evidence=[str(section.get("reasoning"))] if section.get("reasoning") else [],
                classification="inferred", confidence=_confidence(item.get("confidence"), _confidence(section.get("confidence"))),
            ))
    return chunks


def _score(chunk: EvidenceChunk, query_tokens: set[str], boosts: tuple[str, ...]) -> int:
    searchable = chunk.searchable
    overlap = sum(1 for token in query_tokens if token in searchable)
    boost = sum(3 for term in boosts if term in searchable)
    evidence_bonus = 1 if chunk.evidence else 0
    return overlap * 4 + boost + evidence_bonus + round(chunk.confidence / 25)


def _rank(chunks: list[EvidenceChunk], question: str, boosts: tuple[str, ...] = (), limit: int = 5) -> list[EvidenceChunk]:
    query_tokens = _tokens(question)
    scored = sorted(((chunk, _score(chunk, query_tokens, boosts)) for chunk in chunks), key=lambda item: item[1], reverse=True)
    positive = [chunk for chunk, score in scored if score > 2]
    return (positive or [chunk for chunk, _ in scored])[:limit]


def _citation(chunk: EvidenceChunk, number: int) -> dict[str, Any]:
    source = chunk.evidence[0] if chunk.evidence else chunk.detail
    return {
        "id": f"E{number}", "section": chunk.section, "title": chunk.title,
        "evidence": source, "classification": chunk.classification,
        "confidence": chunk.confidence,
    }


def _basis(chunks: list[EvidenceChunk]) -> str:
    classes = {chunk.classification for chunk in chunks}
    if classes == {"observed"}:
        return "observed"
    if classes == {"inferred"}:
        return "inferred"
    return "mixed"


def _with_refs(chunks: list[EvidenceChunk]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    citations = [_citation(chunk, index + 1) for index, chunk in enumerate(chunks)]
    refs = {chunk.key: f"[E{index + 1}]" for index, chunk in enumerate(chunks)}
    return citations, refs


def _auth_answer(document: dict[str, Any], chunks: list[EvidenceChunk]) -> tuple[str, list[EvidenceChunk], list[str]]:
    ranked = _rank(chunks, "authentication identity session oauth permissions login", ("auth", "identity", "session", "oauth"), 5)
    auth_chunks = [chunk for chunk in ranked if any(term in chunk.searchable for term in ("auth", "identity", "session", "oauth", "login"))][:4]
    selected = auth_chunks or ranked[:3]
    _, refs = _with_refs(selected)
    sentences = []
    for chunk in selected[:3]:
        qualifier = "Orbit observed" if chunk.classification == "observed" else "Orbit infers"
        sentences.append(f"{qualifier} {chunk.title}: {chunk.detail or chunk.evidence[0]} {refs[chunk.key]}")
    answer = "Authentication most likely combines a browser session with an identity boundary, but private token validation and session storage are not directly visible. " + " ".join(sentences)
    return answer, selected, ["Which authentication details remain uncertain?", "Explain the trust boundaries around sign-in"]


def _billing_answer(chunks: list[EvidenceChunk]) -> tuple[str, list[EvidenceChunk], list[str]]:
    terms = ("billing", "payment", "checkout", "subscription", "stripe", "invoice", "plan")
    relevant = [chunk for chunk in chunks if any(term in chunk.searchable for term in terms)]
    endpoints = [chunk for chunk in relevant if chunk.section == "API"]
    selected = (endpoints + [chunk for chunk in relevant if chunk.section != "API"])[:6]
    if not selected:
        return (
            "No billing-related endpoints or provider signals were captured in this report. Orbit cannot responsibly invent a billing API from the current evidence.",
            [], ["What integrations were observed?", "Which API endpoints were captured?"],
        )
    _, refs = _with_refs(selected)
    if endpoints:
        endpoint_lines = ", ".join(f"{chunk.title} {refs[chunk.key]}" for chunk in endpoints)
        answer = f"The report contains these billing-related endpoints: {endpoint_lines}."
    else:
        answer = "No billing-specific endpoint path was directly captured. "
    supporting = [chunk for chunk in selected if chunk not in endpoints]
    if supporting:
        answer += " Supporting billing signals include " + "; ".join(f"{chunk.title} {refs[chunk.key]}" for chunk in supporting) + "."
    return answer, selected, ["How does checkout probably work?", "What billing evidence is still missing?"]


def _uncertainty_answer(chunks: list[EvidenceChunk]) -> tuple[str, list[EvidenceChunk], list[str]]:
    unknowns = [chunk for chunk in chunks if chunk.section == "Architecture uncertainty"]
    inferred = sorted((chunk for chunk in chunks if chunk.classification == "inferred" and chunk.section.startswith("Architecture")), key=lambda chunk: chunk.confidence)[:5]
    selected = (unknowns + inferred)[:7]
    if not selected:
        return "The report does not list a specific architecture unknown, but absence of an uncertainty record is not proof that the model is complete.", [], []
    _, refs = _with_refs(selected)
    lines = [f"{chunk.detail or chunk.title} {refs[chunk.key]}" for chunk in selected]
    return "The least certain parts are: " + " ".join(f"{index + 1}) {line}" for index, line in enumerate(lines)), selected, ["Show only inferred connections", "What evidence would reduce these uncertainties?"]


def _system_design_answer(document: dict[str, Any], chunks: list[EvidenceChunk]) -> tuple[str, list[EvidenceChunk], list[str]]:
    architecture = document.get("architecture") or {}
    selected = _rank(chunks, "architecture request flow browser frontend api realtime worker database storage", ("architecture", "flow"), 6)
    _, refs = _with_refs(selected)
    node_labels = [str(node.get("label")) for node in (architecture.get("nodes") or []) if node.get("label")]
    flows = architecture.get("request_flows") or []
    opening = f"In a system-design interview, describe this as a {len(node_labels)}-component system: " + ", ".join(node_labels[:8]) + "."
    if flows:
        strongest = max(flows, key=lambda flow: _confidence(flow.get("confidence")))
        flow_chunk = next((chunk for chunk in selected if chunk.title == strongest.get("name")), None)
        opening += f" The clearest runtime path is {strongest.get('name')}: {' → '.join(_strings(strongest.get('steps')))}"
        if flow_chunk:
            opening += f" {refs[flow_chunk.key]}"
        opening += "."
    observed = [chunk for chunk in selected if chunk.classification == "observed"]
    inferred = [chunk for chunk in selected if chunk.classification == "inferred"]
    if observed:
        opening += " Lead with observed delivery and protocol signals: " + "; ".join(f"{chunk.title} {refs[chunk.key]}" for chunk in observed[:3]) + "."
    if inferred:
        opening += " Then label the hidden implementation as hypotheses: " + "; ".join(f"{chunk.title} {refs[chunk.key]}" for chunk in inferred[:2]) + "."
    return opening, selected, ["Turn this into a 60-second explanation", "What tradeoffs does this architecture imply?"]


def _build_answer(document: dict[str, Any], chunks: list[EvidenceChunk], question: str) -> tuple[str, list[EvidenceChunk], list[str]]:
    selected = _rank(chunks, question + " workflow feature api architecture", ("flow", "feature", "api"), 6)
    _, refs = _with_refs(selected)
    answer = "To build a similar workflow, start from the observed product contract, then choose private implementation details deliberately. "
    if selected:
        answer += "The report supports these requirements: " + "; ".join(f"{chunk.title} — {chunk.detail} {refs[chunk.key]}" for chunk in selected[:4]) + ". "
    answer += "Implementation inference: model the core state and permissions, expose the required API operations, add realtime or background processing only where the cited behavior needs it, and instrument the same user journey. The exact database schema and service boundaries may differ because they are not fully observable."
    return answer, selected, ["Draft the API contract for this workflow", "List the core entities I would need"]


def answer_report_question(document: dict[str, Any], question: str) -> dict[str, Any]:
    question = question.strip()
    chunks = build_evidence_index(document)
    lowered = question.lower()

    if any(term in lowered for term in ("billing", "payment", "checkout", "subscription", "invoice")) and any(term in lowered for term in ("endpoint", "api", "show", "all")):
        answer, selected, followups = _billing_answer(chunks)
    elif any(term in lowered for term in ("uncertain", "uncertainty", "unknown", "not sure", "confidence")):
        answer, selected, followups = _uncertainty_answer(chunks)
    elif any(term in lowered for term in ("system-design", "system design", "interview", "explain the architecture")):
        answer, selected, followups = _system_design_answer(document, chunks)
    elif any(term in lowered for term in ("build", "implement", "similar workflow", "recreate")):
        answer, selected, followups = _build_answer(document, chunks, question)
    elif re.search(r"\b(auth|authentication|login|session|identity)\b|\bsign[ -]?in\b", lowered):
        answer, selected, followups = _auth_answer(document, chunks)
    else:
        selected = _rank(chunks, question, (), 5)
        citations, refs = _with_refs(selected)
        if not selected:
            return {
                "answer": "This report does not contain enough evidence to answer that question.",
                "basis": "insufficient", "confidence": 0, "citations": [],
                "limitations": ["No matching report evidence was found."], "followups": [],
            }
        answer = "The strongest matching report evidence is: " + " ".join(
            f"{chunk.title} — {chunk.detail or chunk.evidence[0]} {refs[chunk.key]}" for chunk in selected
        )
        followups = ["Which parts of that answer are inferred?", "Show the underlying architecture evidence"]
        return {
            "answer": answer, "basis": _basis(selected),
            "confidence": round(sum(chunk.confidence for chunk in selected) / len(selected)),
            "citations": citations,
            "limitations": ["Orbit answers only from this report; unobserved private implementation details remain unknown."],
            "followups": followups,
        }

    citations, _ = _with_refs(selected)
    confidence = round(sum(chunk.confidence for chunk in selected) / len(selected)) if selected else 0
    return {
        "answer": answer, "basis": _basis(selected) if selected else "insufficient",
        "confidence": confidence, "citations": citations,
        "limitations": ["Observed means directly supported by the report. Inferred means a likely explanation, not a verified private implementation detail."],
        "followups": followups,
    }
