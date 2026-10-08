from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.core.database import create_engine, create_session_factory, initialize_database
from app.services.auth import AuthService


@pytest_asyncio.fixture
async def auth_service() -> AsyncIterator[AuthService]:
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await initialize_database(engine)
    yield AuthService(create_session_factory(engine))
    await engine.dispose()


@pytest.mark.asyncio
async def test_oauth_login_matches_provider_subject_and_refreshes_profile(auth_service: AuthService) -> None:
    _, _, original, _, _ = await auth_service.oauth_upsert(
        "google", "subject-42", "person@example.com", "Old profile", None,
    )
    _, _, refreshed, _, _ = await auth_service.oauth_upsert(
        "google", "subject-42", "person@example.com", "Current Google Profile", "https://example.com/avatar.png",
    )

    assert refreshed.id == original.id
    assert refreshed.name == "Current Google Profile"
    assert refreshed.avatar_url == "https://example.com/avatar.png"


@pytest.mark.asyncio
async def test_oauth_rejects_different_subject_for_linked_email(auth_service: AuthService) -> None:
    await auth_service.oauth_upsert(
        "google", "subject-42", "person@example.com", "First Identity", None,
    )

    with pytest.raises(HTTPException) as error:
        await auth_service.oauth_upsert(
            "google", "subject-99", "person@example.com", "Different Identity", None,
        )

    assert error.value.status_code == 409
