from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("ORBIT_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setenv("ORBIT_AUTH_DISABLED", "false")  # auth must be enforced in these tests
    # Import inside the fixture so the env var is applied before settings are cached.
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.main import app

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    get_settings.cache_clear()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_requires_authentication(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/me")).status_code == 401
    assert (await client.get("/api/v1/reports")).status_code == 401


@pytest.mark.asyncio
async def test_signup_login_and_me(client: httpx.AsyncClient) -> None:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "Ada@Example.com", "name": "Ada Lovelace", "password": "supersecret"},
    )
    assert signup.status_code == 201, signup.text
    token = signup.json()["token"]
    assert signup.json()["role"] == "owner"

    me = await client.get("/api/v1/me", headers=_auth_header(token))
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "ada@example.com"
    assert body["plan"] == "free"
    assert body["usage"]["monthly_limit"] == 25

    # Duplicate signup is rejected.
    dup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "ada@example.com", "name": "Ada", "password": "supersecret"},
    )
    assert dup.status_code == 409

    # Login issues a working token; bad password is rejected.
    good = await client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "supersecret"})
    assert good.status_code == 200
    bad = await client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "nope"})
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_tenant_isolation(client: httpx.AsyncClient) -> None:
    a = (await client.post("/api/v1/auth/signup", json={"email": "a@x.com", "name": "Alice", "password": "password1"})).json()["token"]
    b = (await client.post("/api/v1/auth/signup", json={"email": "b@x.com", "name": "Bob", "password": "password1"})).json()["token"]

    created = await client.post(
        "/api/v1/analyses",
        headers={**_auth_header(a), "Idempotency-Key": "iso-key-123456"},
        json={"target_url": "https://example.com", "options": {"max_pages": 1}},
    )
    assert created.status_code == 202
    analysis_id = created.json()["id"]

    # Owner can read it; the other tenant gets a 404.
    assert (await client.get(f"/api/v1/analyses/{analysis_id}", headers=_auth_header(a))).status_code == 200
    assert (await client.get(f"/api/v1/analyses/{analysis_id}", headers=_auth_header(b))).status_code == 404

    # Bob's report list is empty regardless of Alice's activity.
    assert (await client.get("/api/v1/reports", headers=_auth_header(b))).json()["items"] == []
