from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from app.models import Analysis, Report


@pytest_asyncio.fixture
async def workflow_client(tmp_path, monkeypatch) -> AsyncIterator[tuple[httpx.AsyncClient, str]]:
    monkeypatch.setenv("ORBIT_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'workflows.db'}")
    monkeypatch.setenv("ORBIT_AUTH_DISABLED", "true")
    monkeypatch.setenv("ORBIT_BROWSER_EXPLORATION", "false")
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.main import app

    async with app.router.lifespan_context(app):
        ctx = await app.state.auth.dev_context()
        async with app.state.session_factory() as session:
            analysis = Analysis(
                organization_id=ctx.organization.id,
                idempotency_key="workflow-api-test",
                target_url="https://acme.example/app",
                options={},
            )
            session.add(analysis)
            await session.flush()
            report = Report(
                organization_id=ctx.organization.id,
                analysis_id=analysis.id,
                target_url=analysis.target_url,
                product_name="Acme",
                headline="Acme report",
                document={},
            )
            session.add(report)
            await session.commit()
            report_id = report.id
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, report_id
    get_settings.cache_clear()


def _contract() -> dict:
    return {
        "version": "orbit.workflow.v1",
        "id": "acme.public-smoke",
        "name": "Public smoke test",
        "target_url": "https://acme.example/app",
        "status": "ready",
        "steps": [{"id": "step-1", "kind": "navigate", "action": "Open app"}],
    }


@pytest.mark.asyncio
async def test_save_version_list_and_redacted_run(workflow_client, monkeypatch) -> None:
    client, report_id = workflow_client
    created = await client.post(
        f"/api/v1/reports/{report_id}/workflows",
        json={"contract": _contract(), "schedule": "daily"},
    )
    assert created.status_code == 201, created.text
    workflow = created.json()
    assert workflow["version"] == 1
    assert workflow["schedule"] == "daily"

    updated = await client.post(
        f"/api/v1/reports/{report_id}/workflows",
        json={"contract": _contract(), "schedule": "weekly"},
    )
    assert updated.status_code == 201
    assert updated.json()["version"] == 2

    listed = await client.get(f"/api/v1/reports/{report_id}/workflows/saved")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    async def fake_run(self, contract, inputs):
        assert inputs == {"email": "secret@example.com"}
        return {
            "status": "passed", "error_code": None, "failure_step_id": None,
            "duration_ms": 25,
            "steps": [{"step_id": "step-1", "action": "Open app", "status": "passed", "duration_ms": 25}],
            "repair_proposal": None, "message": "Replay completed",
        }

    monkeypatch.setattr("app.api.v1.reports.WorkflowRunner.run", fake_run)
    run = await client.post(
        f"/api/v1/reports/{report_id}/workflows/{workflow['id']}/runs",
        json={"inputs": {"email": "secret@example.com"}},
    )
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "passed"
    assert "secret@example.com" not in run.text

    history = await client.get(f"/api/v1/reports/{report_id}/workflows/{workflow['id']}/runs")
    assert history.status_code == 200
    assert history.json()["items"][0]["status"] == "passed"
