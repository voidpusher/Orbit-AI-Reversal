import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.analyses import router as analyses_router
from app.api.v1.auth import router as auth_router
from app.api.v1.oauth import router as oauth_router
from app.api.v1.reports import router as reports_router
from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory, initialize_database, run_migrations
from app.core.observability import init_observability
from app.services.auth import AuthService
from app.services.events import EventBus, EventService
from app.services.explorer import AnalysisExplorer
from app.services.oauth import OAuthService
from app.services.queue import InProcessAnalysisQueue, RedisAnalysisQueue, VercelAnalysisQueue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_observability(settings)
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    if settings.run_migrations_on_startup:
        await run_migrations()
    else:
        await initialize_database(engine)
    events = EventService(session_factory, EventBus())
    explorer = AnalysisExplorer(settings, session_factory, events, Path(settings.artifact_root))
    if settings.queue_driver == "redis":
        if not settings.redis_url:
            raise RuntimeError("ORBIT_REDIS_URL is required when ORBIT_QUEUE_DRIVER=redis")
        queue = RedisAnalysisQueue(settings.redis_url)
    elif settings.queue_driver == "vercel":
        if settings.database_url.startswith("sqlite"):
            raise RuntimeError("Vercel Queues requires a persistent Postgres database; ephemeral SQLite cannot share jobs")
        if not settings.queue_enqueue_url or not settings.capture_secret:
            raise RuntimeError("ORBIT_QUEUE_ENQUEUE_URL and ORBIT_CAPTURE_SECRET are required for Vercel Queues")
        queue = VercelAnalysisQueue(settings.queue_enqueue_url, settings.capture_secret)
    else:
        queue = InProcessAnalysisQueue(explorer.process, await_completion=bool(os.getenv("VERCEL")))
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.events = events
    app.state.queue = queue
    app.state.explorer = explorer
    app.state.auth = AuthService(session_factory)
    app.state.oauth = OAuthService(settings)
    yield
    if isinstance(queue, RedisAnalysisQueue):
        await queue.close()
    await engine.dispose()


app = FastAPI(title="Orbit API", version="0.1.0", lifespan=lifespan)
API_PREFIX = "/api/v1"
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Idempotency-Key", "Authorization"],
)
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(oauth_router, prefix=API_PREFIX)
app.include_router(analyses_router, prefix=API_PREFIX)
app.include_router(reports_router, prefix=API_PREFIX)


@app.get("/healthz", tags=["operations"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get(f"{API_PREFIX}/healthz", tags=["operations"], include_in_schema=False)
async def api_health_check() -> dict[str, str]:
    """Health endpoint exposed through the Vercel /api/v1 rewrite."""
    return {"status": "ok"}
