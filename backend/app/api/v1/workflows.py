"""Internal scheduled workflow replay endpoint.

Vercel Cron invokes this route once daily. It is intentionally separate from
user authentication and requires CRON_SECRET via a bearer token.
"""

from __future__ import annotations

import hmac
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.models import AuditLog, WorkflowDefinition, WorkflowRun, WorkflowRunStatus
from app.services.vault import WorkflowVault, load_secrets
from app.services.workflow_notifications import WorkflowNotifier
from app.services.workflow_runner import WorkflowRunner, blocked_result_from_exception

router = APIRouter(prefix="/workflows", tags=["workflow operations"])


def _advance(schedule: str, now: datetime) -> datetime | None:
    if schedule == "daily":
        return now + timedelta(days=1)
    if schedule == "weekly":
        return now + timedelta(days=7)
    return None


@router.get("/run-due")
async def run_due_workflows(request: Request, authorization: str | None = Header(default=None)) -> dict:
    settings = request.app.state.settings
    expected = settings.cron_secret
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Scheduled replay is not configured")
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid cron credential")

    now = datetime.now(timezone.utc)
    factory = request.app.state.session_factory
    async with factory() as session:
        due = list((await session.scalars(
            select(WorkflowDefinition).where(
                WorkflowDefinition.status == "active",
                WorkflowDefinition.schedule.in_(("daily", "weekly")),
                WorkflowDefinition.next_run_at.is_not(None),
                WorkflowDefinition.next_run_at <= now,
            ).order_by(WorkflowDefinition.next_run_at).limit(3)
        )).all())
        due_payload = [
            (
                item.id, item.organization_id, item.report_id, item.name,
                dict(item.contract), item.schedule,
            )
            for item in due
        ]

    completed = 0
    blocked = 0
    for workflow_id, organization_id, report_id, workflow_name, contract, schedule in due_payload:
        async with factory() as session:
            saved_inputs: dict[str, str] = {}
            try:
                vault = WorkflowVault(settings)
                secret_values = await load_secrets(
                    session, vault, organization_id=organization_id, workflow_id=workflow_id
                )
                saved_inputs = {
                    key.removeprefix("input."): value
                    for key, value in secret_values.items()
                    if key.startswith("input.")
                }
            except RuntimeError:
                pass
            run = WorkflowRun(
                organization_id=organization_id, workflow_id=workflow_id,
                status=WorkflowRunStatus.RUNNING, trigger="scheduled", result={},
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            run_id = run.id

        started = time.perf_counter()
        try:
            outcome = await WorkflowRunner(settings).run(contract, saved_inputs)
        except Exception as error:
            outcome = blocked_result_from_exception(error)
        deliveries = await WorkflowNotifier(settings, factory).notify_failure(
            workflow_id=workflow_id,
            organization_id=organization_id,
            workflow_name=workflow_name,
            report_id=report_id,
            outcome=outcome,
        )
        if deliveries:
            outcome["notifications"] = deliveries
        finished = datetime.now(timezone.utc)

        async with factory() as session:
            run = await session.get(WorkflowRun, run_id)
            workflow = await session.get(WorkflowDefinition, workflow_id)
            if run is None or workflow is None:
                continue
            run.status = str(outcome.get("status") or WorkflowRunStatus.BLOCKED)
            run.completed_at = finished
            run.duration_ms = int(outcome.get("duration_ms") or round((time.perf_counter() - started) * 1000))
            run.failure_step_id = outcome.get("failure_step_id")
            run.error_code = outcome.get("error_code")
            run.repair_proposal = outcome.get("repair_proposal")
            run.result = {key: value for key, value in outcome.items() if key != "repair_proposal"}
            workflow.last_run_at = finished
            workflow.next_run_at = _advance(schedule, finished)
            session.add(AuditLog(
                organization_id=organization_id, actor_id=None, action="workflow.run.scheduled",
                target_type="workflow_run", target_id=run.id,
                metadata_json={"workflow_id": workflow_id, "status": run.status},
            ))
            await session.commit()
            completed += 1
            blocked += int(run.status == WorkflowRunStatus.BLOCKED)

    return {"processed": completed, "blocked": blocked, "checked_at": now.isoformat()}
