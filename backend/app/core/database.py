import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base

# backend/ project root, where alembic.ini lives.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, future=True, pool_pre_ping=True)


def _run_alembic_upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    command.upgrade(config, "head")


async def run_migrations() -> None:
    """Apply migrations to head. Runs Alembic (which manages its own event loop)
    in a worker thread so it is safe to call from inside the app's async lifespan."""
    await asyncio.get_running_loop().run_in_executor(None, _run_alembic_upgrade)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def initialize_database(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session
