import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory, initialize_database
from app.services.events import EventBus, EventService
from app.services.explorer import AnalysisExplorer
from app.services.queue import RedisAnalysisQueue


async def run() -> None:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("ORBIT_REDIS_URL is required for the worker")
    engine = create_engine(settings.database_url)
    await initialize_database(engine)
    sessions = create_session_factory(engine)
    events = EventService(sessions, EventBus())
    explorer = AnalysisExplorer(settings, sessions, events, artifact_root=Path(settings.artifact_root))
    queue = RedisAnalysisQueue(settings.redis_url)
    try:
        await queue.run_worker(explorer.process)
    finally:
        await queue.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
