from app.schemas import HarEntryRequest
from app.services.har_import import build_har_evidence, normalize_har_path, sanitize_har_entry


def test_normalize_har_path_removes_identifiers() -> None:
    assert normalize_har_path("/api/chats/123456/messages/550e8400-e29b-41d4-a716-446655440000") == (
        "/api/chats/:id/messages/:id"
    )
    assert normalize_har_path("/api/v1/models") == "/api/v1/models"


def test_sanitize_har_entry_drops_query_and_limits_metadata() -> None:
    source_url, metadata = sanitize_har_entry(HarEntryRequest(
        url="https://api.example.com/v1/users/123456?token=secret#private",
        method="POST",
        status=200,
        resource_type="xhr",
        content_type="application/json",
        server="cloudflare",
    ))
    assert source_url == "https://api.example.com/v1/users/:id"
    assert "secret" not in source_url
    assert metadata == {
        "host": "api.example.com",
        "path": "/v1/users/:id",
        "method": "POST",
        "status": 200,
        "resource_type": "xhr",
        "content_type": "application/json",
        "server": "cloudflare",
    }


def test_build_har_evidence_adds_pages_without_sensitive_payloads() -> None:
    entries = [
        HarEntryRequest(url="https://example.com/app?session=private", status=200, resource_type="document"),
        HarEntryRequest(url="https://api.example.com/v1/projects/987654", status=200, resource_type="fetch"),
    ]
    evidence = build_har_evidence("analysis-1", entries, "example.com")
    assert [item.kind for item in evidence] == ["network_signal", "page", "network_signal"]
    assert all("private" not in item.source_url for item in evidence)
    assert evidence[1].metadata_json["capture_engine"] == "sanitized-har"
    assert all(item.redaction_version == "har-v1" for item in evidence)
