"""Evidence-backed reconstruction of a public software system's architecture."""

from __future__ import annotations

from typing import Any

from app.services.tech_detect import Detection


_INTEGRATION_CATEGORIES = {
    "Authentication": ("auth", "Identity provider", ["Authenticates users", "Issues session state"]),
    "Payments": ("payment", "Payment processor", ["Processes checkout", "Handles payment events"]),
    "Analytics": ("analytics", "Product analytics", ["Receives behavioral events", "Measures usage"]),
    "Monitoring": ("monitoring", "Observability service", ["Receives errors", "Collects telemetry"]),
    "Search": ("search", "Search service", ["Indexes content", "Returns ranked results"]),
    "Storage": ("storage", "Asset storage", ["Stores or transforms media", "Delivers assets"]),
    "CMS": ("cms", "Content platform", ["Stores managed content", "Publishes content"]),
    "Commerce": ("commerce", "Commerce platform", ["Manages catalog", "Provides checkout APIs"]),
    "Experimentation": ("experimentation", "Experimentation platform", ["Evaluates flags", "Assigns experiments"]),
    "Support": ("support", "Customer support", ["Provides messaging", "Receives support interactions"]),
    "Email": ("email", "Email service", ["Sends product email", "Handles lifecycle messaging"]),
    "Marketing": ("marketing", "Marketing automation", ["Receives lead events", "Runs campaigns"]),
}

_INTEGRATION_CONNECTIONS = {
    "auth": ("Identity and session exchange", "OAuth/OIDC/HTTPS"),
    "payment": ("Checkout and payment events", "HTTPS"),
    "analytics": ("Behavioral event collection", "HTTPS/beacon"),
    "monitoring": ("Error and telemetry reporting", "HTTPS"),
    "search": ("Search queries", "HTTPS/SDK"),
    "storage": ("Asset retrieval", "HTTPS/CDN"),
    "cms": ("Content retrieval", "HTTPS/API"),
    "commerce": ("Catalog and checkout operations", "HTTPS/API"),
    "experimentation": ("Flag and experiment evaluation", "HTTPS/SDK"),
    "support": ("Support messaging", "HTTPS/SDK"),
    "email": ("Lifecycle event handoff", "HTTPS/API"),
    "marketing": ("Lead and marketing events", "HTTPS/beacon"),
}


def infer_architecture(inputs: Any, detections: list[Detection]) -> dict:
    """Build a topology, flows, and trust model from observable public signals.

    Invisible API or database tiers are not emitted as facts. Missing internal
    information is called out explicitly in ``unknowns``.
    """
    by_category: dict[str, Detection] = {}
    for detection in detections:
        by_category.setdefault(detection.category, detection)

    frontend = by_category.get("Framework") or by_category.get("Frontend")
    cdn = by_category.get("CDN")
    hosting = by_category.get("Hosting")
    api_detection = by_category.get("API")
    data = by_category.get("Database")
    realtime = by_category.get("Realtime")

    page_evidence = [f"HTTP {page.status} {page.url}" for page in inputs.pages[:3]]
    accessible_pages = [page for page in inputs.pages if 200 <= page.status < 400]
    application_accessible = bool(accessible_pages)
    api_evidence = _api_evidence(inputs)
    nodes: list[dict] = []
    connections: list[dict] = []

    def add_node(
        node_id: str,
        label: str,
        kind: str,
        confidence: int,
        role: str,
        responsibilities: list[str],
        evidence: list[str],
        classification: str = "observed",
    ) -> None:
        nodes.append({
            "id": node_id,
            "label": label,
            "kind": kind,
            "confidence": confidence,
            "classification": classification,
            "role": role,
            "responsibilities": responsibilities,
            "evidence": list(dict.fromkeys(evidence))[:4],
        })

    def connect(
        source: str,
        target: str,
        label: str,
        protocol: str,
        confidence: int,
        evidence: list[str],
        classification: str = "observed",
    ) -> None:
        connections.append({
            "from": source,
            "to": target,
            "label": label,
            "protocol": protocol,
            "confidence": confidence,
            "classification": classification,
            "evidence": list(dict.fromkeys(evidence))[:3],
        })

    add_node(
        "browser", "Browser client", "client", 100, "User execution boundary",
        ["Renders the public interface", "Runs client JavaScript", "Initiates network requests"],
        page_evidence or [f"Public URL {inputs.url}"],
    )
    if cdn:
        add_node(
            "edge", cdn.name, "edge", cdn.confidence, "Delivery edge",
            ["Terminates public HTTP traffic", "Caches or accelerates assets"], cdn.evidence,
        )
    add_node(
        "frontend", frontend.name if frontend else "Web frontend", "frontend",
        frontend.confidence if frontend else (92 if application_accessible else 25),
        "Presentation and interaction layer",
        ["Renders product surfaces", "Owns navigation state", "Calls downstream services"],
        (frontend.evidence if frontend else page_evidence) or ["HTML returned to the browser"],
        "observed" if frontend or application_accessible else "inferred",
    )

    api_style = _api_style(inputs, api_detection)
    if api_detection or inputs.api_paths:
        api_confidence = max(api_detection.confidence if api_detection else 0, 88 if inputs.api_paths else 0)
        add_node(
            "api", f"{api_style} application API", "api", api_confidence, "Application service boundary",
            ["Accepts product data requests", "Applies business operations", "Returns structured responses"],
            api_evidence + (api_detection.evidence if api_detection else []),
        )
    if realtime:
        add_node(
            "realtime", realtime.name, "realtime", realtime.confidence, "Realtime event channel",
            ["Pushes state changes", "Supports live product updates"], realtime.evidence,
        )
    if data:
        add_node(
            "data", data.name, "data", data.confidence, "Persistence/data service",
            ["Stores application state", "Serves structured product data"], data.evidence,
        )
    if hosting:
        add_node(
            "hosting", hosting.name, "infra", hosting.confidence, "Runtime and deployment platform",
            ["Hosts public workloads", "Provides deployment infrastructure"], hosting.evidence,
        )

    integration_ids: list[str] = []
    counts: dict[str, int] = {}
    for detection in detections:
        spec = _INTEGRATION_CATEGORIES.get(detection.category)
        if not spec:
            continue
        kind, role, responsibilities = spec
        counts[kind] = counts.get(kind, 0) + 1
        node_id = kind if counts[kind] == 1 else f"{kind}-{counts[kind]}"
        integration_ids.append(node_id)
        add_node(
            node_id, detection.name, kind, detection.confidence, role,
            responsibilities, detection.evidence,
        )

    delivery_target = "edge" if cdn else "frontend"
    connect(
        "browser", delivery_target, "Page and asset delivery", "HTTPS",
        96 if application_accessible else 35,
        page_evidence or [f"Public HTTPS origin {inputs.url}"],
        "observed",
    )
    if cdn and application_accessible:
        connect("edge", "frontend", "Cached application delivery", "HTTPS", cdn.confidence, cdn.evidence)
    if api_detection or inputs.api_paths:
        connect(
            "frontend", "api", "Application data requests",
            "GraphQL over HTTPS" if api_style == "GraphQL" else "HTTPS/JSON",
            max(78, api_detection.confidence if api_detection else 0),
            api_evidence + (api_detection.evidence if api_detection else []),
        )
    if realtime:
        connect(
            "frontend", "realtime", "Live state synchronization", "WebSocket/events",
            realtime.confidence, realtime.evidence,
        )
    if data:
        direct_data = data.name in {"Supabase", "Firebase"}
        api_present = any(node["id"] == "api" for node in nodes)
        source = "frontend" if direct_data or not api_present else "api"
        connect(
            source, "data", "Direct data SDK calls" if direct_data else "Read/write persistence",
            "SDK/HTTPS" if direct_data else "Internal data access", max(62, data.confidence - 8),
            data.evidence, "observed" if direct_data else "inferred",
        )
    if hosting:
        connect(
            "hosting", "frontend", "Hosts application runtime", "deployment",
            hosting.confidence, hosting.evidence,
        )

    node_by_id = {node["id"]: node for node in nodes}
    for node_id in integration_ids:
        node = node_by_id[node_id]
        label, protocol = _INTEGRATION_CONNECTIONS[node["kind"]]
        connect(
            "frontend", node_id, label, protocol, node["confidence"], node["evidence"],
        )

    request_flows = _request_flows(
        inputs, nodes, node_by_id, cdn, data, api_style, api_detection, realtime,
        api_evidence, application_accessible,
    )
    trust_boundaries = _trust_boundaries(
        nodes, node_by_id, integration_ids, delivery_target, page_evidence, data,
    )
    patterns = _architecture_patterns(inputs, realtime)
    node_ids = {node["id"] for node in nodes}
    unknowns = _unknowns(node_ids, nodes)
    if not application_accessible:
        unknowns.insert(
            0,
            "Application access was blocked by the target, so internal product routes and runtime calls were not observed.",
        )
    layers = _layers(node_ids)

    scores = [node["confidence"] for node in nodes if node["id"] != "browser"]
    scores.extend(connection["confidence"] for connection in connections)
    confidence = round(sum(scores) / len(scores)) if scores else 45
    if not application_accessible:
        confidence = min(confidence, 30)
    observed = sum(node["classification"] == "observed" for node in nodes)
    inferred = len(nodes) - observed
    evidence = list(dict.fromkeys(
        [item for node in nodes for item in node["evidence"]] + api_evidence
    ))[:12]

    summary = f"Reconstructed {len(nodes)} components across {len(layers)} layers with {len(connections)} evidence-linked connections"
    if not application_accessible:
        summary = "Target access was blocked; only the public delivery edge could be observed reliably"
    if api_style != "Unknown":
        summary += f" and a {api_style} application interface."
    else:
        summary += "."
    return {
        "summary": summary,
        "confidence": confidence,
        "nodes": nodes,
        "edges": [[item["from"], item["to"]] for item in connections],
        "connections": connections,
        "layers": layers,
        "request_flows": request_flows,
        "trust_boundaries": trust_boundaries,
        "patterns": patterns,
        "unknowns": unknowns,
        "evidence": evidence or ["Public application structure and response behavior"],
        "reasoning": f"The model contains {observed} observed component(s) and {inferred} inferred component(s). "
                     "Connections require a network path, response/header fingerprint, page marker, or provider signal. "
                     "Unobservable internal services are listed as unknowns instead of being fabricated.",
    }


def _api_evidence(inputs: Any) -> list[str]:
    evidence: list[str] = []
    for signal in inputs.network_signals:
        path = str(signal.get("path", ""))
        if path not in inputs.api_paths:
            continue
        method = str(signal.get("method", "GET"))
        host = str(signal.get("host", inputs.host))
        evidence.append(f"{method} https://{host}{path} returned {signal.get('status', '?')}")
    return evidence[:6]


def _api_style(inputs: Any, detection: Detection | None) -> str:
    if any("graphql" in path.lower() for path in inputs.api_paths):
        return "GraphQL"
    if detection and detection.name in {"GraphQL", "Apollo"}:
        return "GraphQL"
    if any("/rpc" in path.lower() for path in inputs.api_paths):
        return "RPC"
    return "REST" if inputs.api_paths else "Unknown"


def _request_flows(
    inputs: Any,
    nodes: list[dict],
    node_by_id: dict[str, dict],
    cdn: Detection | None,
    data: Detection | None,
    api_style: str,
    api_detection: Detection | None,
    realtime: Detection | None,
    api_evidence: list[str],
    application_accessible: bool,
) -> list[dict]:
    page_evidence = [f"HTTP {page.status} {page.url}" for page in inputs.pages[:3]]
    flows = [{
        "name": "Page delivery",
        "steps": ["browser"] + (["edge"] if cdn else []) + (["frontend"] if application_accessible else []),
        "transport": "HTTPS",
        "confidence": 96 if application_accessible else 35,
        "classification": "observed",
        "evidence": page_evidence,
    }]
    if "api" in node_by_id:
        flows.append({
            "name": "Application data flow",
            "steps": ["browser", "frontend", "api"] + (["data"] if data else []),
            "transport": "GraphQL over HTTPS" if api_style == "GraphQL" else "HTTPS/JSON",
            "confidence": 86 if inputs.api_paths else 72,
            "classification": "observed" if inputs.api_paths else "inferred",
            "evidence": (api_evidence or (api_detection.evidence if api_detection else []))[:3],
        })
    for kind, name, transport in (
        ("auth", "Identity flow", "OAuth/OIDC/HTTPS"),
        ("payment", "Checkout flow", "HTTPS"),
        ("realtime", "Realtime update flow", "WebSocket/events"),
    ):
        target = next((node["id"] for node in nodes if node["kind"] == kind), None)
        if target:
            flows.append({
                "name": name,
                "steps": ["browser", "frontend", target],
                "transport": transport,
                "confidence": node_by_id[target]["confidence"],
                "classification": "observed",
                "evidence": node_by_id[target]["evidence"][:3],
            })
    return flows


def _trust_boundaries(
    nodes: list[dict],
    node_by_id: dict[str, dict],
    integration_ids: list[str],
    delivery_target: str,
    page_evidence: list[str],
    data: Detection | None,
) -> list[dict]:
    boundaries = [{
        "name": "Public client to application",
        "between": ["browser", delivery_target],
        "implication": "Browser inputs and tokens cross an untrusted boundary and require server-side validation.",
        "confidence": 96,
        "evidence": page_evidence[:2],
    }]
    if integration_ids:
        evidence = [node_by_id[node_id]["evidence"][0] for node_id in integration_ids if node_by_id[node_id]["evidence"]]
        boundaries.append({
            "name": "First-party application to third parties",
            "between": ["frontend", "third-party services"],
            "implication": "Telemetry, identity, payment, or support data may leave the first-party origin.",
            "confidence": round(sum(node_by_id[node_id]["confidence"] for node_id in integration_ids) / len(integration_ids)),
            "evidence": evidence[:4],
        })
    node_ids = {node["id"] for node in nodes}
    if data and {"api", "data"} <= node_ids:
        boundaries.append({
            "name": "Application service to persistence",
            "between": ["api", "data"],
            "implication": "Authorization and tenant isolation must precede persistent reads and writes.",
            "confidence": max(60, data.confidence - 10),
            "evidence": data.evidence[:3],
        })
    return boundaries


def _architecture_patterns(inputs: Any, realtime: Detection | None) -> list[dict]:
    patterns: list[dict] = []
    if any((signal.get("next_data") or {}).get("present") for signal in inputs.page_signals):
        patterns.append({
            "title": "Server-rendered or hybrid React delivery",
            "detail": "Next.js bootstrap data in the initial HTML indicates pre-rendering plus client hydration.",
            "confidence": 90,
            "classification": "observed",
            "evidence": ["__NEXT_DATA__ payload in initial HTML"],
        })
    elif inputs.page_signals and any(signal.get("has_ssr_content") for signal in inputs.page_signals):
        patterns.append({
            "title": "Meaningful initial HTML",
            "detail": "The server returns substantial readable content before client-side execution.",
            "confidence": 78,
            "classification": "observed",
            "evidence": ["Initial HTML contained substantial text content"],
        })
    cached = next((
        signal.get("delivery", {}).get("cache_control")
        for signal in inputs.page_signals
        if signal.get("delivery", {}).get("cache_control")
    ), None)
    if cached:
        patterns.append({
            "title": "Explicit HTTP caching policy",
            "detail": f"Public responses declare: {cached}.",
            "confidence": 92,
            "classification": "observed",
            "evidence": [f"cache-control: {cached}"],
        })
    if realtime:
        patterns.append({
            "title": "Event-driven client synchronization",
            "detail": "A realtime transport is loaded alongside the application frontend.",
            "confidence": realtime.confidence,
            "classification": "observed",
            "evidence": realtime.evidence[:3],
        })
    return patterns


def _unknowns(node_ids: set[str], nodes: list[dict]) -> list[str]:
    unknowns: list[str] = []
    if "edge" not in node_ids:
        unknowns.append("No CDN or edge provider could be attributed from public headers and hosts.")
    if "api" not in node_ids:
        unknowns.append("No first-party API endpoint was observed; backend service boundaries remain unknown.")
    if "data" not in node_ids:
        unknowns.append("The persistence engine and internal data stores are not observable from the public surface.")
    if not any(node["kind"] == "auth" for node in nodes):
        unknowns.append("The identity/session implementation could not be attributed to a specific provider.")
    return unknowns


def _layers(node_ids: set[str]) -> list[dict]:
    core = {"browser", "edge", "frontend", "api", "realtime", "data"}
    layers = [
        {"name": "Client & delivery", "node_ids": [item for item in ("browser", "edge") if item in node_ids]},
        {"name": "Application", "node_ids": [item for item in ("frontend", "api", "realtime") if item in node_ids]},
        {"name": "Data", "node_ids": ["data"] if "data" in node_ids else []},
        {"name": "Platform & integrations", "node_ids": sorted(node_ids - core)},
    ]
    return [layer for layer in layers if layer["node_ids"]]
