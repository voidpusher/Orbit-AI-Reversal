"""Managed-Postgres URLs must survive the trip to asyncpg.

Providers hand out libpq-style URLs (`postgres://…?sslmode=require`). The engine uses
asyncpg, which rejects both the bare scheme and libpq-only query keywords — pasting a
Neon/Supabase URL verbatim used to crash the app on boot.
"""

import pytest

from app.core.config import Settings


def _url(value: str) -> str:
    return Settings(database_url=value).database_url


@pytest.mark.parametrize("scheme", ["postgres", "postgresql"])
def test_sync_schemes_are_rewritten_to_asyncpg(scheme: str) -> None:
    assert _url(f"{scheme}://u:p@host:5432/db") == "postgresql+asyncpg://u:p@host:5432/db"


def test_neon_url_sslmode_and_channel_binding() -> None:
    # Exactly what Neon's dashboard gives you.
    result = _url("postgresql://u:p@ep-x.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
    assert result.startswith("postgresql+asyncpg://u:p@ep-x.aws.neon.tech/neondb")
    assert "sslmode" not in result  # asyncpg would raise on this keyword
    assert "channel_binding" not in result
    assert "ssl=require" in result  # TLS is still enforced, via asyncpg's own argument


def test_supabase_pooler_url_drops_pgbouncer_flag() -> None:
    result = _url("postgres://u:p@aws.pooler.supabase.com:6543/postgres?pgbouncer=true&sslmode=require")
    assert "pgbouncer" not in result
    assert "ssl=require" in result


def test_sslmode_disable_does_not_force_tls() -> None:
    assert _url("postgresql://u:p@localhost/db?sslmode=disable") == "postgresql+asyncpg://u:p@localhost/db"


def test_unknown_params_are_preserved() -> None:
    assert "application_name=orbit" in _url("postgresql://u:p@h/db?application_name=orbit")


def test_sqlite_url_is_untouched() -> None:
    assert _url("sqlite+aiosqlite:///./orbit.db") == "sqlite+aiosqlite:///./orbit.db"
