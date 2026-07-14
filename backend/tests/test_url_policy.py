import pytest
from fastapi import HTTPException

from app.services.url_policy import normalize_public_url


def test_normalizes_fragment_and_lowercases_host() -> None:
    assert normalize_public_url("https://Linear.APP/docs#intro") == "https://linear.app/docs"


@pytest.mark.parametrize("url", ["http://localhost:3000", "https://127.0.0.1", "file:///tmp/a"])
def test_rejects_local_and_non_http_targets(url: str) -> None:
    with pytest.raises(HTTPException):
        normalize_public_url(url)
