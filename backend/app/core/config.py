from functools import lru_cache
import os
from urllib.parse import parse_qsl, urlencode

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# libpq keywords that managed-Postgres URLs carry but asyncpg does not accept.
_LIBPQ_ONLY_PARAMS = {"channel_binding", "pgbouncer", "options", "target_session_attrs", "connect_timeout"}


def _default_database_url() -> str:
    marketplace_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if marketplace_url:
        for prefix in ("postgres://", "postgresql://"):
            if marketplace_url.startswith(prefix):
                return _clean_asyncpg_query("postgresql+asyncpg://" + marketplace_url[len(prefix):])
        return marketplace_url
    if os.getenv("VERCEL"):
        return "sqlite+aiosqlite:////tmp/orbit.db"
    return "sqlite+aiosqlite:///./orbit.db"


def _default_artifact_root() -> str:
    # Serverless filesystems are read-only apart from /tmp.
    if os.getenv("VERCEL"):
        return "/tmp/orbit-artifacts"
    return ".artifacts"


def _clean_asyncpg_query(url: str) -> str:
    """Drop libpq-only query params that asyncpg rejects.

    Neon/Supabase URLs carry `?sslmode=require&channel_binding=require`, which are
    libpq keywords. asyncpg raises `connect() got an unexpected keyword argument
    'sslmode'`, so translate sslmode into the `ssl` argument asyncpg understands and
    drop the rest.
    """
    base, separator, query = url.partition("?")
    if not separator:
        return url

    kept: list[tuple[str, str]] = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        lowered = key.lower()
        if lowered == "sslmode":
            # disable/allow/prefer → no TLS requirement; anything stricter → require TLS.
            if value.lower() not in {"disable", "allow", "prefer"}:
                kept.append(("ssl", "require"))
            continue
        if lowered in _LIBPQ_ONLY_PARAMS:
            continue
        kept.append((key, value))

    if not kept:
        return base
    return f"{base}?{urlencode(kept)}"


def _default_browser_exploration() -> bool:
    # Serverless hosts ship no chromium binary, and Playwright spends ~100s failing
    # to launch one before giving up. Skip straight to the HTTP explorer there.
    return not os.getenv("VERCEL")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ORBIT_", extra="ignore")

    environment: str = "development"
    database_url: str = Field(default_factory=_default_database_url)
    artifact_root: str = Field(default_factory=_default_artifact_root)
    # Attempt real browser (Playwright) exploration. When false, the HTTP explorer
    # is used directly. Set ORBIT_BROWSER_EXPLORATION=true on a host where you have
    # run `playwright install chromium`.
    browser_exploration: bool = Field(default_factory=_default_browser_exploration)
    # Optional serverless Chromium capture endpoint. This lets the Python API use
    # a real browser on Vercel while preserving the HTTP crawler as a fallback.
    browser_capture_url: str | None = None
    capture_secret: str | None = None
    redis_url: str | None = None
    queue_driver: str = "in_process"
    # Internal Next.js producer used by the Python API when Vercel Queues is enabled.
    queue_enqueue_url: str | None = None
    # Auth is disabled by default: all endpoints run as a single shared workspace
    # with no token required. Re-enable the full auth/OAuth/RBAC system (kept intact
    # in the codebase) by setting ORBIT_AUTH_DISABLED=false.
    auth_disabled: bool = True
    # When true, the app runs `alembic upgrade head` on startup (the production
    # path). When false it falls back to create_all for fast local dev and tests.
    run_migrations_on_startup: bool = False

    # Optional Sentry error tracking; activates only when a DSN is provided and
    # the sentry-sdk package is installed.
    sentry_dsn: str | None = None
    max_pages: int = Field(default=20, ge=1, le=100)
    max_analysis_seconds: int = Field(default=120, ge=15, le=600)
    allowed_analysis_hosts: tuple[str, ...] = ()

    # Optional model provider for narrative synthesis. With no key the analyzer
    # falls back to deterministic prose, so the pipeline works offline.
    openai_api_key: str | None = None
    openai_model: str = "gpt-5"
    openai_base_url: str = "https://api.openai.com/v1"

    # OAuth social sign-in. Each provider activates only when its client id and
    # secret are present. `public_base_url` is this API's externally reachable
    # base (used to build the OAuth redirect_uri); `frontend_base_url` is where
    # the user is sent back after a successful sign-in.
    public_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        return list({self.frontend_base_url, "http://localhost:3000"})

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Managed Postgres providers (Neon, Supabase, Render, Heroku, Railway) hand out
        # sync-driver URLs; rewrite them to the async driver the engine actually uses.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                value = "postgresql+asyncpg://" + value[len(prefix):]
                break
        else:
            return value
        return _clean_asyncpg_query(value)

    @field_validator("queue_driver")
    @classmethod
    def validate_queue_driver(cls, value: str) -> str:
        if value not in {"in_process", "redis", "vercel"}:
            raise ValueError("queue_driver must be 'in_process', 'redis', or 'vercel'")
        return value

    @field_validator("allowed_analysis_hosts", mode="before")
    @classmethod
    def split_hosts(cls, value: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
        if isinstance(value, str):
            return tuple(host.strip().lower() for host in value.split(",") if host.strip())
        return tuple(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
