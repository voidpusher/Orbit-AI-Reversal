import pytest

from app.services.queue import InProcessAnalysisQueue


@pytest.mark.asyncio
async def test_inline_queue_waits_for_serverless_analysis() -> None:
    completed: list[str] = []

    async def handler(analysis_id: str) -> None:
        completed.append(analysis_id)

    queue = InProcessAnalysisQueue(handler, await_completion=True)
    await queue.enqueue("analysis-1")

    assert completed == ["analysis-1"]
