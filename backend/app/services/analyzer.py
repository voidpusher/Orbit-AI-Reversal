"""Turns collected evidence into a structured, evidence-backed report document.

The heavy lifting is deterministic inference over observable signals so reports are
reproducible and testable. A model adapter only polishes narrative prose. Every
section carries a summary, a confidence score, and supporting evidence.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import Analysis, EvidenceItem, Report, ReportClaim
from app.services.ai import ModelAdapter, Synthesis
from app.services.architecture import infer_architecture
from app.services.deep_analysis import (
    analyze_domain,
    analyze_performance,
    analyze_privacy,
    analyze_rendering,
    analyze_security,
    analyze_seo,
)
from app.services.tech_detect import Detection, Signals, detect

logger = logging.getLogger(__name__)


@dataclass
class PageInfo:
    url: str
    path: str
    title: str
    status: int
    text: str = ""


@dataclass
class AnalysisInputs:
    product_name: str
    host: str
    url: str
    pages: list[PageInfo] = field(default_factory=list)
    link_paths: list[str] = field(default_factory=list)
    api_paths: list[str] = field(default_factory=list)
    network_signals: list[dict] = field(default_factory=list)
    signals: Signals = field(default_factory=Signals)
    page_signals: list[dict] = field(default_factory=list)
    probes: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------------

def _product_name(host: str) -> str:
    core = host.split(":")[0]
    for prefix in ("www.", "app.", "my.", "dashboard."):
        if core.startswith(prefix):
            core = core[len(prefix):]
    label = core.split(".")[0]
    return label.replace("-", " ").title() if label else host


def extract_inputs(analysis_url: str, evidence: list[EvidenceItem]) -> AnalysisInputs:
    host = (urlsplit(analysis_url).hostname or "").lower()
    inputs = AnalysisInputs(product_name=_product_name(host), host=host, url=analysis_url)

    for item in evidence:
        meta = item.metadata_json or {}
        if item.kind == "page":
            inputs.pages.append(
                PageInfo(
                    url=item.source_url,
                    path=urlsplit(item.source_url).path or "/",
                    title=str(meta.get("title", "")),
                    status=int(meta.get("status_code", 0) or 0),
                    text=str(meta.get("visible_text", "")),
                )
            )
            for script in meta.get("scripts", []) or []:
                inputs.signals.scripts.append(str(script))
                shost = urlsplit(str(script)).hostname
                if shost:
                    inputs.signals.hosts.add(shost.lower())
            for marker in meta.get("markers", []) or []:
                inputs.signals.html_markers.append(str(marker))
            for link in meta.get("links", []) or []:
                if str(link) not in inputs.link_paths:
                    inputs.link_paths.append(str(link))
            if meta.get("generator"):
                inputs.signals.generators.append(str(meta["generator"]))
            for key, value in (meta.get("headers") or {}).items():
                inputs.signals.headers.setdefault(str(key), str(value))
            signals = meta.get("signals")
            if isinstance(signals, dict):
                inputs.page_signals.append(signals)
                # Broaden technology detection with every third-party host seen.
                for host in signals.get("third_party_hosts", []):
                    inputs.signals.hosts.add(str(host).lower())
        elif item.kind == "network_signal":
            inputs.network_signals.append(dict(meta))
            shost = str(meta.get("host", ""))
            if shost:
                inputs.signals.hosts.add(shost.lower())
            path = str(meta.get("path", ""))
            host_parts = host.split(".")
            site_suffix = ".".join(host_parts[-2:]) if len(host_parts) >= 2 else host
            first_party = shost == host or (site_suffix and shost.endswith(f".{site_suffix}"))
            if first_party and any(seg in path.lower() for seg in ("/api", "/graphql", "/v1", "/rest", "/rpc")):
                if path not in inputs.api_paths:
                    inputs.api_paths.append(path)
        elif item.kind == "site_probe":
            inputs.probes = item.metadata_json or {}
    return inputs


# ---------------------------------------------------------------------------
# Section inference
# ---------------------------------------------------------------------------

_FEATURE_KEYWORDS = {
    "Authentication": ("login", "sign in", "signin", "sign up", "signup", "auth", "account"),
    "Billing & subscriptions": ("pricing", "billing", "plans", "subscription", "checkout", "upgrade"),
    "Dashboard": ("dashboard", "overview", "home", "workspace"),
    "Search": ("search", "explore", "find"),
    "Team collaboration": ("team", "members", "invite", "workspace", "organization", "collaborat"),
    "Settings & configuration": ("settings", "preferences", "profile", "config"),
    "Documentation": ("docs", "documentation", "guide", "help", "support"),
    "Developer API": ("api", "developers", "graphql", "webhook", "integration"),
    "Notifications": ("notification", "inbox", "activity", "alerts"),
    "Analytics & reporting": ("analytics", "reports", "insights", "metrics", "usage"),
    "Projects & workspaces": ("project", "board", "issue", "task", "workspace"),
    "Integrations": ("integration", "connect", "marketplace", "apps"),
}


def _confidence_band(score: int) -> str:
    if score >= 88:
        return "Strong evidence"
    if score >= 74:
        return "Good evidence"
    if score >= 60:
        return "Moderate evidence"
    return "Weak evidence"


def _feature_sources(inputs: AnalysisInputs) -> list[tuple[str, str]]:
    """(haystack, citation) pairs a feature keyword may be observed in.

    Link paths matter most: on a single-page analysis the navigation is the only place
    the rest of the product surface is visible.
    """
    sources: list[tuple[str, str]] = []
    for page in inputs.pages:
        if not 200 <= page.status < 400:
            continue
        sources.append((page.path.lower(), f"explored page {page.path}"))
        if page.title:
            sources.append((page.title.lower(), f"title of {page.path}: “{page.title[:60]}”"))
    for page in inputs.pages:
        if page.text and 200 <= page.status < 400:
            sources.append((page.text.lower(), f"rendered text on {page.path}"))
    for path in inputs.link_paths:
        sources.append((path.lower(), f"link to {path} in site navigation"))
    for marker in inputs.signals.html_markers:
        sources.append((marker.lower(), f"HTML marker '{marker}'"))
    for signal in inputs.page_signals:
        description = str(signal.get("meta_description") or "")
        if description:
            sources.append((description.lower(), "page meta description"))
        open_graph = signal.get("open_graph") or {}
        for key in ("title", "description"):
            value = str(open_graph.get(key) or "")
            if value:
                sources.append((value.lower(), f"Open Graph {key}"))
    host_parts = inputs.host.split(".")
    site_suffix = ".".join(host_parts[-2:]) if len(host_parts) >= 2 else inputs.host
    for signal in inputs.network_signals:
        signal_host = str(signal.get("host") or "").lower()
        if signal_host == inputs.host or (site_suffix and signal_host.endswith(f".{site_suffix}")):
            path = str(signal.get("path") or "")
            if path:
                sources.append((path.lower(), f"observed first-party request {path}"))
    return sources


def _matches(keyword: str, haystack: str) -> bool:
    # Left word-boundary only: 'auth' must still hit "authentication", but 'api' must not
    # hit "rapidly" and 'search' must not hit "researchers".
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}", haystack) is not None


def infer_features(inputs: AnalysisInputs) -> list[dict]:
    sources = _feature_sources(inputs)
    features: list[dict] = []
    for name, keywords in _FEATURE_KEYWORDS.items():
        matched: set[str] = set()
        citations: list[str] = []
        for keyword in keywords:
            for haystack, citation in sources:
                if _matches(keyword, haystack):
                    matched.add(keyword)
                    if citation not in citations:
                        citations.append(citation)
                    break  # one citation per keyword is enough
        if not matched:
            continue
        features.append(
            {
                "name": name,
                "description": _feature_description(name),
                "confidence": min(95, 62 + len(matched) * 8),
                "classification": "observed",
                "evidence": citations[:3],
            }
        )
    features.sort(key=lambda f: f["confidence"], reverse=True)
    return features


def _feature_description(name: str) -> str:
    return {
        "Authentication": "Account creation and sign-in surfaces were observed in the public product.",
        "Billing & subscriptions": "Pricing and plan surfaces suggest a self-serve subscription model.",
        "Dashboard": "An authenticated application shell / dashboard entry point was observed.",
        "Search": "Search or discovery surfaces are exposed in the product.",
        "Team collaboration": "Team, member, and workspace concepts indicate multi-user collaboration.",
        "Settings & configuration": "User- and workspace-level configuration surfaces were found.",
        "Documentation": "Public documentation or help content supports the product.",
        "Developer API": "Developer-facing API or integration surfaces were observed.",
        "Notifications": "Notification / activity surfaces suggest event-driven updates.",
        "Analytics & reporting": "Reporting and analytics surfaces expose product usage data.",
        "Projects & workspaces": "Project, board, or issue concepts structure the core workflow.",
        "Integrations": "Third-party integration or marketplace surfaces were observed.",
    }.get(name, "Observed in the public product surface.")


def _infer_architecture_legacy(inputs: AnalysisInputs, detections: list[Detection]) -> dict:
    by_cat: dict[str, Detection] = {}
    for d in detections:
        by_cat.setdefault(d.category, d)

    frontend = by_cat.get("Framework") or by_cat.get("Frontend")
    cdn = by_cat.get("CDN")
    hosting = by_cat.get("Hosting")
    api = by_cat.get("API")
    data = by_cat.get("Database")
    realtime = by_cat.get("Realtime")

    nodes = [{"id": "browser", "label": "Browser", "kind": "client", "confidence": 100}]
    if cdn:
        nodes.append({"id": "cdn", "label": cdn.name, "kind": "edge", "confidence": cdn.confidence})
    nodes.append(
        {"id": "frontend", "label": frontend.name if frontend else "Web frontend", "kind": "frontend",
         "confidence": frontend.confidence if frontend else 70}
    )
    nodes.append(
        {"id": "api", "label": f"{api.name} API" if api else "API layer", "kind": "api",
         "confidence": api.confidence if api else 66}
    )
    if realtime:
        nodes.append({"id": "realtime", "label": realtime.name, "kind": "realtime", "confidence": realtime.confidence})
    nodes.append(
        {"id": "data", "label": data.name if data else "Data services", "kind": "data",
         "confidence": data.confidence if data else 58}
    )
    if hosting:
        nodes.append({"id": "hosting", "label": hosting.name, "kind": "infra", "confidence": hosting.confidence})

    ids = [n["id"] for n in nodes]
    edges: list[list[str]] = []
    linear = [i for i in ["browser", "cdn", "frontend", "api", "data"] if i in ids]
    edges.extend([[linear[i], linear[i + 1]] for i in range(len(linear) - 1)])
    if "realtime" in ids and "frontend" in ids:
        edges.append(["frontend", "realtime"])
    if "hosting" in ids and "api" in ids:
        edges.append(["api", "hosting"])

    confidence = round(sum(n["confidence"] for n in nodes) / len(nodes))
    evidence = [f"{d.name} ({d.category})" for d in detections[:5]] or ["Public application structure and response behavior"]
    observed = [n["label"] for n in nodes if n["confidence"] >= 85]
    inferred = [n["label"] for n in nodes if n["confidence"] < 85]
    return {
        "summary": "Request flow from the browser through the delivery edge, frontend, API, and data tiers.",
        "confidence": confidence,
        "nodes": nodes,
        "edges": edges,
        "evidence": evidence,
        "reasoning": "The browser client and any edge/frontend/hosting nodes are grounded in observed hosts, "
                     "headers, and detected technologies"
                     + (f" ({', '.join(observed)})" if observed else "")
                     + ". The API and data tiers"
                     + (f" ({', '.join(inferred)})" if inferred else "")
                     + " are inferred from response behavior — they are not directly observable on the public "
                     "surface and carry lower confidence accordingly.",
    }


def infer_user_flows(inputs: AnalysisInputs, features: list[dict]) -> dict:
    feature_names = {f["name"] for f in features}
    flows: list[dict] = []
    basis: list[str] = []

    # Each journey is emitted only when the surface that implies it was observed —
    # no generic "signup → dashboard" flow for sites without an auth surface.
    if "Authentication" in feature_names:
        steps = ["Land on site", "Sign up"]
        if "Team collaboration" in feature_names or "Projects & workspaces" in feature_names:
            steps += ["Create workspace", "Invite team"]
        if "Dashboard" in feature_names:
            steps.append("Open dashboard")
        steps.append("Perform core action")
        if "Notifications" in feature_names:
            steps.append("Receive notification")
        flows.append({"name": "Primary activation flow", "steps": steps, "confidence": min(82, 58 + len(steps) * 4)})
        basis.append("an observed authentication surface")
    if "Billing & subscriptions" in feature_names:
        flows.append({"name": "Upgrade flow", "steps": ["View pricing", "Select plan", "Checkout", "Confirm subscription", "Unlock features"], "confidence": 74})
        basis.append("pricing / billing surfaces")
    if "Developer API" in feature_names:
        flows.append({"name": "Developer integration", "steps": ["Read docs", "Create API key", "Call API", "Handle webhook"], "confidence": 68})
        basis.append("developer / API surfaces")

    if not flows:
        return {
            "summary": "Unable to reconstruct primary user journeys from the public surface.",
            "confidence": 35,
            "flows": [],
            "reasoning": "No authentication, billing, or developer surfaces were observed. User journeys "
                         "require account or transactional behavior that a public surface does not expose, "
                         "so inferring a signup or activation flow would be a guess rather than an inference.",
        }
    return {
        "summary": "Primary product journeys inferred from the feature surfaces actually discovered.",
        "confidence": round(sum(f["confidence"] for f in flows) / len(flows)),
        "flows": flows,
        "reasoning": f"Journeys are reconstructed from {', '.join(basis)}. Individual steps are conventional "
                     "for such surfaces and are not each independently observed.",
    }


# Features that imply the product stores per-account data (so entities can be inferred).
_ACCOUNT_FEATURES = {
    "Authentication", "Team collaboration", "Projects & workspaces", "Dashboard",
    "Settings & configuration", "Billing & subscriptions", "Notifications", "Analytics & reporting",
}


def infer_entities(inputs: AnalysisInputs, features: list[dict]) -> dict:
    feature_names = {f["name"] for f in features}

    # Forensic discipline: do not invent a data model. Without any account-bearing
    # surface, the public evidence is insufficient to infer entities.
    if not (_ACCOUNT_FEATURES & feature_names):
        return {
            "summary": "Unable to determine a data model from the public surface.",
            "confidence": 35,
            "items": [],
            "relationships": [],
            "reasoning": "No authentication, dashboard, workspace, or billing surfaces were observed, "
                         "so there is no observable basis to infer persisted entities. Entities require "
                         "account or application behavior that a public marketing surface does not expose.",
        }

    has_auth = "Authentication" in feature_names
    entities: list[dict] = [
        {"name": "User", "fields": ["id", "email", "name", "avatar_url", "created_at"], "confidence": 88 if has_auth else 66},
    ]
    relationships: list[dict] = []

    if "Team collaboration" in feature_names or "Projects & workspaces" in feature_names:
        entities.append({"name": "Organization", "fields": ["id", "name", "slug", "plan"], "confidence": 82})
        entities.append({"name": "Membership", "fields": ["id", "user_id", "organization_id", "role"], "confidence": 78})
        relationships += [
            {"from": "User", "to": "Membership", "kind": "1:N"},
            {"from": "Organization", "to": "Membership", "kind": "1:N"},
        ]
    if "Projects & workspaces" in feature_names:
        entities.append({"name": "Project", "fields": ["id", "organization_id", "name", "status"], "confidence": 76})
        entities.append({"name": "Item", "fields": ["id", "project_id", "title", "state", "assignee_id"], "confidence": 70})
        relationships += [
            {"from": "Organization", "to": "Project", "kind": "1:N"},
            {"from": "Project", "to": "Item", "kind": "1:N"},
        ]
    if "Billing & subscriptions" in feature_names:
        entities.append({"name": "Subscription", "fields": ["id", "organization_id", "plan", "status", "renews_at"], "confidence": 74})
        relationships.append({"from": "Organization", "to": "Subscription", "kind": "1:1"})
    if "Notifications" in feature_names:
        entities.append({"name": "Notification", "fields": ["id", "user_id", "type", "read_at"], "confidence": 68})
        relationships.append({"from": "User", "to": "Notification", "kind": "1:N"})

    confidence = round(sum(e["confidence"] for e in entities) / len(entities))
    return {
        "summary": "Likely core entities and relationships inferred from observed product concepts.",
        "confidence": confidence,
        "items": entities,
        "relationships": relationships,
        "reasoning": "Entities are inferred from the account-bearing features observed"
                     + (" (authentication present)" if has_auth else "")
                     + f": {', '.join(sorted(_ACCOUNT_FEATURES & feature_names))}. Field lists are conventional, not observed.",
    }


def infer_api(inputs: AnalysisInputs, detections: list[Detection], probes: dict | None = None) -> dict:
    probes = probes or {}
    api_probe = probes.get("api", {}) or {}
    openapi = api_probe.get("openapi")
    graphql = api_probe.get("graphql")
    is_graphql = bool(graphql) or any(d.name in {"GraphQL", "Apollo"} for d in detections)

    endpoints: list[dict] = []
    findings: list[dict] = []
    spec = None
    style = "GraphQL" if is_graphql else "REST / JSON over HTTPS"
    confidence = 80 if inputs.api_paths else (70 if is_graphql else 58)

    if openapi:
        # A published OpenAPI document is the strongest possible API evidence.
        style = f"OpenAPI {openapi.get('spec_version', '')}".strip()
        spec = {"title": openapi.get("title"), "version": openapi.get("version"), "path_count": openapi.get("path_count", 0)}
        for op in openapi.get("operations", []):
            endpoints.append({"method": op["method"], "path": op["path"], "confidence": 96, "note": "From OpenAPI spec"})
        confidence = 96
        findings.append({
            "title": "Public OpenAPI specification",
            "detail": f"A machine-readable OpenAPI doc exposes {openapi.get('path_count', 0)} paths"
                      + (f" for “{openapi['title']}”" if openapi.get("title") else "") + ".",
            "status": "info",
            "evidence": openapi.get("url", ""),
        })

    for path in inputs.api_paths[:12]:
        if not any(e["path"] == path for e in endpoints):
            endpoints.append({"method": "GET", "path": path, "confidence": 72, "note": "Observed in network traffic"})

    if graphql:
        if graphql.get("introspection_enabled"):
            findings.append({
                "title": "GraphQL introspection enabled",
                "detail": "The GraphQL endpoint answers introspection queries, exposing its full schema"
                          + (f" (~{graphql.get('type_count')} types)" if graphql.get("type_count") else "")
                          + " — usually disabled in production to reduce attack surface.",
                "status": "warn",
                "evidence": graphql.get("endpoint", ""),
            })
            confidence = max(confidence, 90)
        else:
            findings.append({"title": "GraphQL endpoint detected", "detail": "A GraphQL endpoint responds; introspection appears disabled.", "status": "good", "evidence": graphql.get("endpoint", "")})

    if not endpoints:
        endpoints = [{"method": "POST", "path": "/graphql" if is_graphql else "/api/*", "confidence": 60, "note": "Inferred API entry point"}]

    return {
        "summary": f"The product exposes a {style} interface." if openapi or graphql else f"The product appears to expose a {style} interface.",
        "confidence": confidence,
        "style": style,
        "spec": spec,
        "endpoints": endpoints,
        "findings": findings,
        "evidence": ([openapi["url"]] if openapi else []) + [f"observed path {p}" for p in inputs.api_paths[:4]] or ["API style inferred from client signals"],
    }


def infer_insights(inputs: AnalysisInputs, detections: list[Detection]) -> list[dict]:
    names = {d.name for d in detections}
    cats = {d.category for d in detections}
    insights: list[dict] = []

    def add(title: str, detail: str, confidence: int, classification: str = "inferred") -> None:
        insights.append({"title": title, "detail": detail, "confidence": confidence, "classification": classification})

    if {"React", "Vue.js", "Svelte", "Angular"} & names:
        add("Optimistic UI updates", "A client-side rendering framework suggests local state updates before server confirmation for perceived speed.", 78)
    if "Realtime" in cats or "WebSocket" in names:
        add("Realtime synchronization", "Realtime transport signals indicate event-driven updates and live collaboration.", 82)
    if "CDN" in cats:
        add("Edge caching / CDN delivery", "Static assets are served from a CDN edge, reducing latency and origin load.", 88, "observed")
    if "GraphQL" in names or "Apollo" in names:
        add("Typed GraphQL data layer", "A GraphQL interface enables precise client queries and strong typing.", 80)
    if "Next.js" in names or "Nuxt" in names or "Remix" in names:
        add("Server-side rendering", "A hybrid meta-framework points to SSR/SSG for fast first paint and SEO.", 84, "observed")
    if any(p for p in inputs.api_paths):
        add("List pagination", "Observed list surfaces imply cursor or offset pagination for scalable data access.", 70)
    if "Monitoring" in cats:
        add("Production observability", "An error/monitoring SDK indicates active production telemetry.", 84, "observed")
    if "Payments" in cats:
        add("Third-party payments", "A payments provider handles PCI-sensitive billing outside the core app.", 86, "observed")
    if not insights:
        add("Standard web delivery", "The product is delivered as a standard HTTPS web application.", 62)
    insights.sort(key=lambda i: i["confidence"], reverse=True)
    return insights


def infer_security(inputs: AnalysisInputs, detections: list[Detection]) -> dict:
    items: list[dict] = []
    https = inputs.url.startswith("https://") or all(p.status for p in inputs.pages)
    if https:
        items.append({"title": "HTTPS everywhere", "detail": "All observed traffic used TLS.", "confidence": 96, "classification": "observed"})
    headers = {k.lower(): v for k, v in inputs.signals.headers.items()}
    if "content-security-policy" in headers:
        items.append({"title": "Content Security Policy", "detail": "A CSP header was returned, mitigating XSS/injection.", "confidence": 90, "classification": "observed"})
    if "strict-transport-security" in headers:
        items.append({"title": "HSTS enabled", "detail": "Strict-Transport-Security enforces HTTPS on repeat visits.", "confidence": 92, "classification": "observed"})
    auth = next((d for d in detections if d.category == "Authentication"), None)
    if auth:
        items.append({"title": f"Managed auth ({auth.name})", "detail": "Authentication is delegated to a dedicated identity provider.", "confidence": auth.confidence, "classification": "observed"})
    if not items:
        items.append({"title": "Baseline transport security", "detail": "Standard web security posture observed on public surfaces.", "confidence": 60, "classification": "inferred"})
    confidence = round(sum(i["confidence"] for i in items) / len(items))
    return {"summary": "Security posture observed from public transport and headers.", "confidence": confidence, "items": items}


def infer_infrastructure(detections: list[Detection], probes: dict | None = None) -> dict:
    items = [
        {"title": d.name, "detail": f"{d.category} signal — {'; '.join(d.evidence[:2])}", "confidence": d.confidence}
        for d in detections
        if d.category in {"Hosting", "CDN", "Storage", "Monitoring", "Database", "Realtime", "Search"}
    ]
    # Native mobile apps discovered via universal-link / app-link association files.
    wk = (probes or {}).get("wellknown", {})
    if wk.get("ios_app"):
        ids = ", ".join(wk.get("ios_app_ids", [])[:3])
        items.append({"title": "iOS app (universal links)", "detail": f"apple-app-site-association declares native iOS app(s): {ids}.", "confidence": 92})
    if wk.get("android_app"):
        pkgs = ", ".join(wk.get("android_packages", [])[:3])
        items.append({"title": "Android app (app links)", "detail": f"assetlinks.json declares native Android app(s): {pkgs}.", "confidence": 92})
    confidence = round(sum(i["confidence"] for i in items) / len(items)) if items else 55
    return {
        "summary": "Infrastructure, platform providers, and native apps inferred from network hosts and association files.",
        "confidence": confidence,
        "items": items or [{"title": "Self-hosted or masked infrastructure", "detail": "No third-party infra hosts were clearly observed.", "confidence": 50}],
    }


def infer_permissions(features: list[dict]) -> dict:
    feature_names = {f["name"] for f in features}

    # A permission model presupposes accounts. Without an authentication or
    # account-bearing surface, there is no observable basis for one.
    if not (_ACCOUNT_FEATURES & feature_names):
        return {
            "summary": "Unable to determine a permission model from the public surface.",
            "confidence": 35,
            "roles": [],
            "reasoning": "No authentication or account surface was observed, so there is no evidence of "
                         "users, roles, or access control to reason about. Asserting a role model here "
                         "would be a guess.",
        }

    multi_tenant = bool({"Team collaboration", "Projects & workspaces"} & feature_names)
    if multi_tenant:
        roles = [
            {"name": "Owner", "capabilities": ["Billing", "Manage members", "Full data access"]},
            {"name": "Admin", "capabilities": ["Manage members", "Configure workspace"]},
            {"name": "Member", "capabilities": ["Create & edit content", "Collaborate"]},
        ]
        reasoning = "Team/workspace surfaces were observed, which imply a multi-tenant role hierarchy. " \
                    "The specific role names and capabilities are conventional and not directly observed."
    else:
        roles = [{"name": "Account owner", "capabilities": ["Full access to own data", "Billing"]}]
        reasoning = "An authentication surface was observed but no team/workspace concepts, suggesting a " \
                    "single-user account model. Roles beyond the account owner are not evidenced."
    return {
        "summary": "Role model inferred from collaboration and workspace surfaces." if multi_tenant else "Single-user account model inferred.",
        "confidence": 72 if multi_tenant else 64,
        "roles": roles,
        "reasoning": reasoning,
    }


def infer_integrations(detections: list[Detection]) -> dict:
    third_party_cats = {"Analytics", "Payments", "Monitoring", "Support", "Email", "Marketing", "Search", "CMS", "Authentication", "Storage"}
    items = [
        {"name": d.name, "category": d.category, "confidence": d.confidence}
        for d in detections
        if d.category in third_party_cats
    ]
    confidence = round(sum(i["confidence"] for i in items) / len(items)) if items else 55
    return {
        "summary": "Third-party services integrated into the product, observed via network hosts and page markers.",
        "confidence": confidence,
        "items": items,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def build_document(inputs: AnalysisInputs, synthesis: Synthesis, evidence_count: int) -> tuple[dict, list[dict]]:
    detections = detect(inputs.signals)
    features = infer_features(inputs)
    architecture = infer_architecture(inputs, detections)
    flows = infer_user_flows(inputs, features)
    entities = infer_entities(inputs, features)
    api = infer_api(inputs, detections, inputs.probes)
    insights = infer_insights(inputs, detections)
    infrastructure = infer_infrastructure(detections, inputs.probes)
    permissions = infer_permissions(features)
    integrations = infer_integrations(detections)

    # Deep, evidence-grounded sections derived from the rich per-page signals,
    # enriched with host-level probes (TLS, JS bundles, robots/sitemap).
    ps = inputs.page_signals
    probes = inputs.probes or {}
    if ps:
        security = analyze_security(ps, probes)
        performance = analyze_performance(ps, probes)
        rendering = analyze_rendering(ps)
        seo = analyze_seo(ps, probes)
        privacy = analyze_privacy(ps)
        domain = analyze_domain(probes)
    else:
        security = infer_security(inputs, detections)
        performance = rendering = seo = privacy = domain = None

    tech_items = [
        {"name": d.name, "category": d.category, "confidence": d.confidence, "evidence": d.evidence}
        for d in detections
    ]
    categories = sorted({d.category for d in detections})

    section_confidences = [
        architecture["confidence"], api["confidence"],
        security["confidence"], infrastructure["confidence"],
    ]
    # Exclude "unable to determine" sections from the overall blend — honesty isn't penalized.
    if entities["items"]:
        section_confidences.append(entities["confidence"])
    if flows["flows"]:
        section_confidences.append(flows["confidence"])
    for extra in (performance, rendering, seo, privacy, domain):
        if extra:
            section_confidences.append(extra["confidence"])
    if tech_items:
        section_confidences.append(round(sum(t["confidence"] for t in tech_items) / len(tech_items)))
    overall = round(sum(section_confidences) / len(section_confidences)) if section_confidences else 60
    access_limited = bool(inputs.pages) and not any(200 <= page.status < 400 for page in inputs.pages)
    if access_limited:
        overall = min(overall, 35)

    # Surface the most eye-catching quantified signals on the overview.
    region = rendering.get("region") if rendering else None
    deep_metric_count = sum(len(s["findings"]) for s in (security, performance, seo, privacy) if s and "findings" in s)

    document = {
        "meta": {
            "product_name": inputs.product_name,
            "host": inputs.host,
            "url": inputs.url,
            "pages_explored": len(inputs.pages),
            "evidence_count": evidence_count,
            "features_count": len(features),
            "technologies_count": len(tech_items),
            "insights_count": len(insights),
            "overall_confidence": overall,
            "confidence_band": _confidence_band(overall),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_name": synthesis.model_name,
            "access_limited": access_limited,
            "access_statuses": sorted({page.status for page in inputs.pages}),
        },
        "overview": {
            "headline": synthesis.headline,
            "summary": synthesis.summary,
            "metrics": [
                {
                    "value": "N/A" if access_limited else str(len(features)),
                    "label": "Features observed",
                    "sub": "Inspection blocked" if access_limited else "Product surface",
                },
                {
                    "value": "N/A" if access_limited else str(len(entities["items"])),
                    "label": "Entities inferred",
                    "sub": "Insufficient evidence" if access_limited else "Data model",
                },
                {"value": str(len(tech_items)), "label": "Technologies", "sub": "Observed stack"},
                {"value": str(len(insights)), "label": "Engineering insights", "sub": "Evidence-backed"},
            ],
        },
        "architecture": architecture,
        "user_flows": flows,
        "features": {"summary": "Product capabilities detected from observable surfaces.", "confidence": round(sum(f["confidence"] for f in features) / len(features)) if features else 55, "items": features},
        "entities": entities,
        "permissions": permissions,
        "database": {"summary": entities["summary"], "confidence": entities["confidence"], "items": entities["items"], "relationships": entities["relationships"], "reasoning": entities.get("reasoning")},
        "api": api,
        "tech_stack": {"summary": "Technology profile assembled from network hosts, script markers, and headers.", "confidence": round(sum(t["confidence"] for t in tech_items) / len(tech_items)) if tech_items else 55, "items": tech_items, "categories": categories},
        "integrations": integrations,
        "insights": {"summary": "How the product likely works, inferred from engineering signals.", "confidence": round(sum(i["confidence"] for i in insights) / len(insights)) if insights else 60, "items": insights, "reasoning": "Each insight is tied to a specific observed signal (a detected technology, transport, or header). Items labelled 'observed' are directly evidenced; 'inferred' items are likelihoods, not facts, and carry proportionate confidence."},
        "infrastructure": infrastructure,
        "security": security,
    }
    if performance:
        document["performance"] = performance
    if rendering:
        document["rendering"] = rendering
    if seo:
        document["seo"] = seo
    if privacy:
        document["privacy"] = privacy
    if domain:
        document["domain"] = domain
    if region:
        document["meta"]["region"] = region
    document["meta"]["deep_findings"] = deep_metric_count

    # Flat claim list for the report_claims table (auditable, queryable).
    claims: list[dict] = []
    for f in features:
        claims.append({"section": "features", "claim": f["name"], "confidence": f["confidence"] / 100, "classification": f["classification"], "evidence": f["evidence"]})
    for t in tech_items:
        claims.append({"section": "tech_stack", "claim": f"{t['name']} ({t['category']})", "confidence": t["confidence"] / 100, "classification": "observed", "evidence": t["evidence"]})
    for i in insights:
        claims.append({"section": "insights", "claim": i["title"], "confidence": i["confidence"] / 100, "classification": i["classification"], "evidence": [i["detail"]]})
    # Deep, header-grounded findings are the most defensible claims (classification observed).
    for section_key, section in (("security", security), ("performance", performance), ("seo", seo), ("privacy", privacy), ("domain", domain)):
        for finding in (section or {}).get("findings", []):
            claims.append({
                "section": section_key,
                "claim": finding["title"],
                "confidence": 0.9 if finding.get("status") in {"good", "bad"} else 0.75,
                "classification": "observed",
                "evidence": [finding.get("evidence") or finding.get("detail", "")],
            })
    return document, claims


class ReportGenerator:
    def __init__(self, settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._settings = settings
        self._sessions = session_factory
        self._model = ModelAdapter(settings.openai_api_key, settings.openai_model, settings.openai_base_url)

    async def generate(self, analysis: Analysis) -> Report:
        async with self._sessions() as session:
            existing = await session.scalar(
                select(Report).where(Report.analysis_id == analysis.id, Report.version == 1)
            )
            if existing is not None:
                return existing
            evidence = list(
                (await session.scalars(select(EvidenceItem).where(EvidenceItem.analysis_id == analysis.id))).all()
            )

        inputs = extract_inputs(analysis.target_url, evidence)
        detections = detect(inputs.signals)
        context = {
            "product_name": inputs.product_name,
            "host": inputs.host,
            "url": inputs.url,
            "pages_explored": len(inputs.pages),
            "evidence_count": len(evidence),
            "technologies": [{"name": d.name, "category": d.category} for d in detections[:8]],
            "categories": sorted({d.category for d in detections}),
            "page_titles": [p.title for p in inputs.pages[:8] if p.title],
        }
        synthesis = await self._model.synthesize(context)
        document, claims = build_document(inputs, synthesis, len(evidence))
        meta = document["meta"]

        async with self._sessions() as session:
            report = Report(
                organization_id=analysis.organization_id,
                analysis_id=analysis.id,
                version=1,
                target_url=analysis.target_url,
                product_name=inputs.product_name,
                headline=synthesis.headline,
                summary=synthesis.summary,
                overall_confidence=meta["overall_confidence"],
                document=document,
                pages_explored=meta["pages_explored"],
                evidence_count=len(evidence),
                features_count=meta["features_count"],
                model_name=synthesis.model_name,
            )
            session.add(report)
            await session.flush()
            for c in claims:
                session.add(
                    ReportClaim(
                        report_id=report.id,
                        section=c["section"],
                        claim=c["claim"],
                        confidence=c["confidence"],
                        classification=c["classification"],
                        evidence=c["evidence"],
                        model_version=synthesis.model_name,
                    )
                )
            await session.commit()
            await session.refresh(report)
        logger.info("report generated", extra={"analysis_id": analysis.id, "report_id": report.id})
        return report
