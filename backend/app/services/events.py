import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AnalysisEvent
from app.schemas import AnalysisEventResponse


class EventBus:
    """Process-local notification bus; durable events always live in PostgreSQL."""

    def __init__(self) -> None:
        self._conditions: defaultdict[str, asyncio.Condition] = defaultdict(asyncio.Condition)

    async def notify(self, analysis_id: str) -> None:
        condition = self._conditions[analysis_id]
        async with condition:
            condition.notify_all()

    async def wait(self, analysis_id: str, timeout: float = 20) -> None:
        condition = self._conditions[analysis_id]
        async with condition:
            try:
                await asyncio.wait_for(condition.wait(), timeout=timeout)
            except TimeoutError:
                return


class EventService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], event_bus: EventBus) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus

    async def append(
        self, analysis_id: str, kind: str, message: str, payload: dict[str, Any] | None = None
    ) -> AnalysisEvent:
        async with self._session_factory() as session:
            current = await session.scalar(
                select(func.coalesce(func.max(AnalysisEvent.sequence), 0)).where(AnalysisEvent.analysis_id == analysis_id)
            )
            event = AnalysisEvent(
                analysis_id=analysis_id,
                sequence=int(current) + 1,
                kind=kind,
                message=message,
                payload=payload or {},
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
        await self._event_bus.notify(analysis_id)
        return event

    async def after(self, analysis_id: str, sequence: int) -> list[AnalysisEventResponse]:
        async with self._session_factory() as session:
            events = (await session.scalars(
                select(AnalysisEvent)
                .where(AnalysisEvent.analysis_id == analysis_id, AnalysisEvent.sequence > sequence)
                .order_by(AnalysisEvent.sequence)
            )).all()
        return [self.as_response(event) for event in events]

    @staticmethod
    def as_response(event: AnalysisEvent) -> AnalysisEventResponse:
        return AnalysisEventResponse(
            sequence=event.sequence,
            kind=event.kind,
            message=event.message,
            payload=event.payload,
            occurred_at=event.occurred_at,
        )

    async def stream(self, analysis_id: str, after_sequence: int = 0) -> AsyncIterator[AnalysisEventResponse | None]:
        cursor = after_sequence
        while True:
            events = await self.after(analysis_id, cursor)
            if events:
                for event in events:
                    cursor = event.sequence
                    yield event
                continue
            await self._event_bus.wait(analysis_id)
            yield None
