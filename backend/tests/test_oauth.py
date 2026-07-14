from collections.abc import AsyncIterator
from urllib.parse import urlsplit

import httpx
import pytest
import pytest_asyncio

from app.services.oauth import OAuthProfile


@pytest_asyncio.fixture
async def app_and_client(tmp_path, monkeypatch) -> AsyncIterator[tuple[object, httpx.AsyncClient]]:
    monkeypatch.setenv("ORBIT_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'oauth.db'}")
    monkeypatch.setenv("ORBIT_AUTH_DISABLED", "false")
    monkeypatch.setenv("ORBIT_GITHUB_CLIENT_ID", "gh-id")
    monkeypatch.setenv("ORBIT_GITHUB_CLIENT_SECRET", "gh-secret")
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.main import app

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as c:
            yield app, c
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_providers_reflect_configuration(app_and_client) -> None:
    _, client = app_and_client
    providers = (await client.get("/api/v1/auth/oauth/providers")).json()
    assert providers == {"google": False, "github": True}


@pytest.mark.asyncio
async def test_start_redirects_to_provider(app_and_client) -> None:
    _, client = app_and_client
    resp = await client.get("/api/v1/auth/oauth/github/start")
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://github.com/login/oauth/authorize")
    assert "client_id=gh-id" in location and "state=" in location


@pytest.mark.asyncio
async def test_unconfigured_provider_redirects_with_error(app_and_client) -> None:
    _, client = app_and_client
    resp = await client.get("/api/v1/auth/oauth/google/start")
    assert resp.status_code == 302
    assert "error=google_unconfigured" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_creates_user_and_session(app_and_client, monkeypatch) -> None:
    app, client = app_and_client

    async def fake_exchange(provider: str, code: str) -> OAuthProfile:
        assert provider == "github" and code == "auth-code"
        return OAuthProfile(
            provider="github", subject="42", email="Octo@example.com",
            name="Octo Cat", avatar_url="https://avatars.example/octo.png",
        )

    monkeypatch.setattr(app.state.oauth, "exchange", fake_exchange)
    state = app.state.oauth.issue_state()

    resp = await client.get(f"/api/v1/auth/oauth/github/callback?code=auth-code&state={state}")
    assert resp.status_code == 302
    fragment = urlsplit(resp.headers["location"]).fragment
    assert fragment.startswith("token=")
    token = fragment.removeprefix("token=")

    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "octo@example.com"
    assert me.json()["role"] == "owner"


@pytest.mark.asyncio
async def test_callback_rejects_bad_state(app_and_client) -> None:
    _, client = app_and_client
    resp = await client.get("/api/v1/auth/oauth/github/callback?code=x&state=forged")
    assert resp.status_code == 302
    assert "error=invalid_oauth_state" in resp.headers["location"]
