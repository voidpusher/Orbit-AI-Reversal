from __future__ import annotations

import hashlib
import re
from urllib.parse import unquote, urlsplit, urlunsplit

from app.models import EvidenceItem
from app.schemas import HarEntryRequest

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27,}$", re.I)
_OPAQUE = re.compile(r"^[A-Za-z0-9_-]{18,}$")
_NUMBER = re.compile(r"^\d{3,}$")
_SAFE_RESOURCE_TYPES = {
    "document", "stylesheet", "image", "media", "font", "script", "texttrack",
    "xhr", "fetch", "eventsource", "websocket", "manifest", "other",
}


def normalize_har_path(path: str) -> str:
    """Keep route shape while removing identifiers that may contain user data."""
    segments: list[str] = []
    for raw_segment in unquote(path or "/").split("/"):
        segment = raw_segment[:100]
        if _UUID.fullmatch(segment) or _NUMBER.fullmatch(segment) or _OPAQUE.fullmatch(segment):
            segment = ":id"
        segments.append(segment)
    normalized = "/".join(segments)[:240]
    return normalized if normalized.startswith("/") else f"/{normalized}"


def sanitize_har_entry(entry: HarEntryRequest) -> tuple[str, dict[str, str | int]]:
    parsed = urlsplit(str(entry.url))
    host = (parsed.hostname or "").lower().rstrip(".")
    port = f":{parsed.port}" if parsed.port else ""
    path = normalize_har_path(parsed.path)
    source_url = urlunsplit((parsed.scheme, f"{host}{port}", path, "", ""))
    resource_type = (entry.resource_type or "other").lower()
    if resource_type not in _SAFE_RESOURCE_TYPES:
        resource_type = "other"
    metadata: dict[str, str | int] = {
        "host": host,
        "path": path,
        "method": entry.method.upper() if entry.method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"} else "OTHER",
        "status": entry.status,
        "resource_type": resource_type,
    }
    for key, value in (
        ("content_type", entry.content_type),
        ("cache_control", entry.cache_control),
        ("server", entry.server),
    ):
        if value:
            metadata[key] = value.strip()[:160]
    return source_url, metadata


def build_har_evidence(analysis_id: str, entries: list[HarEntryRequest], target_host: str) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    pages_seen: set[str] = set()
    for entry in entries:
        source_url, metadata = sanitize_har_entry(entry)
        fingerprint = f"{metadata['host']}|{metadata['path']}|{metadata['method']}|{metadata['status']}"
        evidence.append(EvidenceItem(
            analysis_id=analysis_id,
            kind="network_signal",
            source_url=source_url,
            content_hash=hashlib.sha256(fingerprint.encode()).hexdigest(),
            metadata_json=metadata,
            redaction_version="har-v1",
        ))
        if (
            metadata["resource_type"] == "document"
            and metadata["host"] == target_host
            and source_url not in pages_seen
            and len(pages_seen) < 50
        ):
            pages_seen.add(source_url)
            page_meta = {
                "title": "",
                "status_code": metadata["status"],
                "headers": {
                    key.replace("_", "-"): value
                    for key, value in metadata.items()
                    if key in {"content_type", "cache_control", "server"}
                },
                "scripts": [],
                "markers": [],
                "links": [],
                "capture_engine": "sanitized-har",
            }
            evidence.append(EvidenceItem(
                analysis_id=analysis_id,
                kind="page",
                source_url=source_url,
                content_hash=hashlib.sha256(f"page|{source_url}|{metadata['status']}".encode()).hexdigest(),
                metadata_json=page_meta,
                redaction_version="har-v1",
            ))
    return evidence
