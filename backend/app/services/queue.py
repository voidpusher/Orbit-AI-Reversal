import asyncio
from collections.abc import Awaitable, Callable

import httpx
from redis.asyncio import Redis


AnalysisHandler = Callable[[str], Awaitable[None]]


class AnalysisQueue:
    async def enqueue(self, analysis_id: str) -> None:  # pragma: no cover - protocol method
        raise NotImplementedError


class InProcessAnalysisQueue(AnalysisQueue):
    def __init__(self, handler: AnalysisHandler, await_completion: bool = False) -> None:
        self._handler = handler
        self._await_completion = await_completion
        self._tasks: set[asyncio.Task[None]] = set()

    async def enqueue(self, analysis_id: str) -> None:
        if self._await_completion:
            # Serverless runtimes freeze work as soon as the request returns.
            # Keep the invocation alive until the report has been persisted.
            await self._handler(analysis_id)
            return
        task = asyncio.create_task(self._handler(analysis_id), name=f"analysis-{analysis_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


class RedisAnalysisQueue(AnalysisQueue):
    queue_name = "orbit:analysis-jobs"

    def __init__(self, redis_url: str) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    async def enqueue(self, analysis_id: str) -> None:
        await self._redis.lpush(self.queue_name, analysis_id)

    async def run_worker(self, handler: AnalysisHandler) -> None:
        while True:
            item = await self._redis.brpop(self.queue_name, timeout=5)
            if item is None:
                continue
            _, analysis_id = item
            await handler(analysis_id)

    async def close(self) -> None:
        await self._redis.aclose()


class VercelAnalysisQueue(AnalysisQueue):
    """Publish lightweight job references to Vercel's durable queue service."""

    def __init__(self, enqueue_url: str, secret: str) -> None:
        self._enqueue_url = enqueue_url
        self._secret = secret

    async def enqueue(self, analysis_id: str) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                self._enqueue_url,
                headers={"X-Orbit-Capture-Secret": self._secret},
                json={"analysisId": analysis_id},
            )
            response.raise_for_status()
