import base64
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_auth_context
from app.models import (
    Analysis,
    AuditLog,
    Report,
    Role,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowRunStatus,
)
from app.schemas import (
    AskReportRequest,
    AskReportResponse,
    CompileWorkflowRequest,
    CompileWorkflowResponse,
    ComparisonResponse,
    ExportRequest,
    ExportResponse,
    ReportDetail,
    ReportListItem,
    ReportListResponse,
    RunWorkflowRequest,
    SaveWorkflowRequest,
    SavedWorkflowListResponse,
    StatsResponse,
    UpdateReportRequest,
    WorkflowListResponse,
    WorkflowDefinitionResponse,
    WorkflowRunListResponse,
    WorkflowRunResponse,
)
from app.services.auth import AuthContext
from app.services.compare import build_comparison
from app.services.copilot import answer_report_question
from app.services.export import render_markdown
from app.services.workflow_compiler import available_workflows, compile_workflow
from app.services.workflow_runner import WorkflowRunner, blocked_result_from_exception, validate_workflow_contract

router = APIRouter(prefix="/reports", tags=["reports"])


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


def as_list_item(report: Report) -> ReportListItem:
    return ReportListItem(
        id=report.id,
        analysis_id=report.analysis_id,
        target_url=report.target_url,
        product_name=report.product_name,
        headline=report.headline,
        overall_confidence=report.overall_confidence,
        pages_explored=report.pages_explored,
        features_count=report.features_count,
        is_favorite=report.is_favorite,
        label=report.label,
        model_name=report.model_name,
        published_at=report.published_at,
    )


def _encode_cursor(published_at: str, report_id: str) -> str:
    return base64.urlsafe_b64encode(f"{published_at}|{report_id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, str]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    published_at, report_id = raw.split("|", 1)
    return published_at, report_id


async def _load(session: AsyncSession, report_id: str, org_id: str) -> Report:
    report = await session.get(Report, report_id)
    if report is None or report.is_deleted or report.organization_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return report


async def _load_workflow(
    session: AsyncSession, report_id: str, workflow_id: str, org_id: str
) -> WorkflowDefinition:
    workflow = await session.get(WorkflowDefinition, workflow_id)
    if workflow is None or workflow.report_id != report_id or workflow.organization_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    return workflow


def _workflow_response(workflow: WorkflowDefinition) -> WorkflowDefinitionResponse:
    return WorkflowDefinitionResponse(
        id=workflow.id, report_id=workflow.report_id, name=workflow.name,
        target_url=workflow.target_url, version=workflow.version, status=workflow.status,
        schedule=workflow.schedule, contract=workflow.contract,
        created_at=workflow.created_at, updated_at=workflow.updated_at,
        last_run_at=workflow.last_run_at, next_run_at=workflow.next_run_at,
    )


def _next_run(schedule: str, now: datetime | None = None) -> datetime | None:
    current = now or datetime.now(timezone.utc)
    if schedule == "daily":
        return current + timedelta(days=1)
    if schedule == "weekly":
        return current + timedelta(days=7)
    return None


def _run_response(run: WorkflowRun) -> WorkflowRunResponse:
    return WorkflowRunResponse(
        id=run.id, workflow_id=run.workflow_id, status=run.status, trigger=run.trigger,
        started_at=run.started_at, completed_at=run.completed_at, duration_ms=run.duration_ms,
        failure_step_id=run.failure_step_id, error_code=run.error_code,
        result=run.result, repair_proposal=run.repair_proposal,
    )


@router.get("", response_model=ReportListResponse)
async def list_reports(
    q: str | None = Query(default=None, max_length=200),
    favorite: bool = False,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> ReportListResponse:
    org_id = ctx.organization.id
    async with factory() as session:
        query = select(Report).where(Report.organization_id == org_id, Report.is_deleted.is_(False))
        if favorite:
            query = query.where(Report.is_favorite.is_(True))
        if q:
            pattern = f"%{q.lower()}%"
            query = query.where(
                or_(
                    func.lower(Report.product_name).like(pattern),
                    func.lower(Report.headline).like(pattern),
                    func.lower(Report.target_url).like(pattern),
                )
            )
        if cursor:
            published_at, report_id = _decode_cursor(cursor)
            query = query.where(
                or_(
                    Report.published_at < published_at,
                    (Report.published_at == published_at) & (Report.id < report_id),
                )
            )
        query = query.order_by(Report.published_at.desc(), Report.id.desc()).limit(limit + 1)
        rows = list((await session.scalars(query)).all())

    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.published_at.isoformat(), last.id)
        rows = rows[:limit]
    return ReportListResponse(items=[as_list_item(r) for r in rows], next_cursor=next_cursor)


@router.get("/stats", response_model=StatsResponse)
async def report_stats(
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> StatsResponse:
    org_id = ctx.organization.id
    async with factory() as session:
        total_analyses = await session.scalar(
            select(func.count()).select_from(Analysis).where(Analysis.organization_id == org_id)
        )
        completed = await session.scalar(
            select(func.count()).select_from(Report).where(
                Report.organization_id == org_id, Report.is_deleted.is_(False)
            )
        )
        favorites = await session.scalar(
            select(func.count()).select_from(Report).where(
                Report.organization_id == org_id, Report.is_deleted.is_(False), Report.is_favorite.is_(True)
            )
        )
        avg_conf = await session.scalar(
            select(func.avg(Report.overall_confidence)).where(
                Report.organization_id == org_id, Report.is_deleted.is_(False)
            )
        )
    return StatsResponse(
        total_analyses=int(total_analyses or 0),
        completed_reports=int(completed or 0),
        favorites=int(favorites or 0),
        average_confidence=round(float(avg_conf or 0)),
    )


@router.get("/compare", response_model=ComparisonResponse)
async def compare_reports(
    a: str,
    b: str,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> ComparisonResponse:
    if a == b:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose two different reports to compare")
    async with factory() as session:
        report_a = await _load(session, a, ctx.organization.id)
        report_b = await _load(session, b, ctx.organization.id)
        return ComparisonResponse.model_validate(build_comparison(report_a, report_b))


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: str,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> ReportDetail:
    async with factory() as session:
        report = await _load(session, report_id, ctx.organization.id)
        return ReportDetail(
            **as_list_item(report).model_dump(),
            summary=report.summary,
            evidence_count=report.evidence_count,
            document=report.document,
        )


@router.patch("/{report_id}", response_model=ReportListItem)
async def update_report(
    report_id: str,
    payload: UpdateReportRequest,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> ReportListItem:
    async with factory() as session:
        report = await _load(session, report_id, ctx.organization.id)
        if payload.is_favorite is not None:
            report.is_favorite = payload.is_favorite
        if payload.label is not None:
            report.label = payload.label or None
        await session.commit()
        await session.refresh(report)
        return as_list_item(report)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: str,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> None:
    if ctx.role not in {Role.OWNER, Role.ADMIN}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins can delete reports")
    async with factory() as session:
        report = await _load(session, report_id, ctx.organization.id)
        report.is_deleted = True
        session.add(AuditLog(
            organization_id=ctx.organization.id, actor_id=ctx.user.id, action="report.deleted",
            target_type="report", target_id=report.id,
        ))
        await session.commit()


@router.post("/{report_id}/exports", response_model=ExportResponse)
async def export_report(
    report_id: str,
    payload: ExportRequest,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> ExportResponse:
    if payload.format not in {"json", "markdown"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unsupported export format")
    async with factory() as session:
        report = await _load(session, report_id, ctx.organization.id)
        slug = (report.product_name or "report").lower().replace(" ", "-")
        if payload.format == "markdown":
            content = render_markdown(report)
            return ExportResponse(format="markdown", filename=f"orbit-{slug}.md", content=content)
        content = json.dumps(
            {
                "product_name": report.product_name,
                "target_url": report.target_url,
                "overall_confidence": report.overall_confidence,
                "generated_at": report.published_at.isoformat(),
                "document": report.document,
            },
            indent=2,
            ensure_ascii=False,
        )
        return ExportResponse(format="json", filename=f"orbit-{slug}.json", content=content)


@router.post("/{report_id}/ask", response_model=AskReportResponse)
async def ask_report(
    report_id: str,
    payload: AskReportRequest,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> AskReportResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Question is required")
    if len(question) > 600:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Question must be 600 characters or fewer")
    async with factory() as session:
        report = await _load(session, report_id, ctx.organization.id)
        return AskReportResponse.model_validate(answer_report_question(report.document or {}, question))


@router.get("/{report_id}/workflows", response_model=WorkflowListResponse)
async def list_report_workflows(
    report_id: str,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> WorkflowListResponse:
    async with factory() as session:
        report = await _load(session, report_id, ctx.organization.id)
        return WorkflowListResponse(items=available_workflows(report.document or {}))


@router.post("/{report_id}/workflows/compile", response_model=CompileWorkflowResponse)
async def compile_report_workflow(
    report_id: str,
    payload: CompileWorkflowRequest,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> CompileWorkflowResponse:
    flow_name = payload.flow_name.strip()
    if not flow_name or len(flow_name) > 160:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A valid workflow name is required")
    async with factory() as session:
        report = await _load(session, report_id, ctx.organization.id)
        try:
            result = compile_workflow(report.document or {}, flow_name)
        except ValueError as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
        return CompileWorkflowResponse.model_validate(result)


@router.post("/{report_id}/workflows", response_model=WorkflowDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def save_report_workflow(
    report_id: str,
    payload: SaveWorkflowRequest,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> WorkflowDefinitionResponse:
    try:
        validate_workflow_contract(payload.contract)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    if payload.schedule not in {"manual", "daily", "weekly"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Schedule must be manual, daily, or weekly")

    async with factory() as session:
        report = await _load(session, report_id, ctx.organization.id)
        target_url = str(payload.contract.get("target_url") or "")
        if urlsplit(target_url).hostname != urlsplit(report.target_url).hostname:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Workflow target must match its report host")
        contract_key = str(payload.contract["id"])[:255]
        workflow = await session.scalar(select(WorkflowDefinition).where(
            WorkflowDefinition.organization_id == ctx.organization.id,
            WorkflowDefinition.report_id == report_id,
            WorkflowDefinition.contract_key == contract_key,
        ))
        if workflow is None:
            workflow = WorkflowDefinition(
                organization_id=ctx.organization.id, report_id=report_id, contract_key=contract_key,
                name=str(payload.contract["name"])[:200], target_url=target_url,
                contract=payload.contract, schedule=payload.schedule,
                next_run_at=_next_run(payload.schedule),
            )
            session.add(workflow)
            audit_action = "workflow.created"
        else:
            workflow.name = str(payload.contract["name"])[:200]
            workflow.target_url = target_url
            workflow.contract = payload.contract
            workflow.schedule = payload.schedule
            workflow.next_run_at = _next_run(payload.schedule)
            workflow.version += 1
            workflow.updated_at = datetime.now(timezone.utc)
            audit_action = "workflow.updated"
        await session.flush()
        session.add(AuditLog(
            organization_id=ctx.organization.id, actor_id=ctx.user.id, action=audit_action,
            target_type="workflow", target_id=workflow.id,
            metadata_json={"version": workflow.version, "schedule": workflow.schedule},
        ))
        await session.commit()
        await session.refresh(workflow)
        return _workflow_response(workflow)


@router.get("/{report_id}/workflows/saved", response_model=SavedWorkflowListResponse)
async def list_saved_workflows(
    report_id: str,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> SavedWorkflowListResponse:
    async with factory() as session:
        await _load(session, report_id, ctx.organization.id)
        rows = list((await session.scalars(
            select(WorkflowDefinition).where(
                WorkflowDefinition.report_id == report_id,
                WorkflowDefinition.organization_id == ctx.organization.id,
            ).order_by(WorkflowDefinition.updated_at.desc())
        )).all())
        return SavedWorkflowListResponse(items=[_workflow_response(item) for item in rows])


@router.post("/{report_id}/workflows/{workflow_id}/runs", response_model=WorkflowRunResponse)
async def run_saved_workflow(
    report_id: str,
    workflow_id: str,
    payload: RunWorkflowRequest,
    request: Request,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> WorkflowRunResponse:
    async with factory() as session:
        workflow = await _load_workflow(session, report_id, workflow_id, ctx.organization.id)
        if workflow.status != "active":
            raise HTTPException(status.HTTP_409_CONFLICT, "Workflow is paused")
        contract = dict(workflow.contract)
        run = WorkflowRun(
            organization_id=ctx.organization.id, workflow_id=workflow.id,
            status=WorkflowRunStatus.RUNNING, trigger="manual", result={},
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        run_id = run.id

    started = time.perf_counter()
    try:
        outcome = await WorkflowRunner(request.app.state.settings).run(contract, payload.inputs)
    except Exception as error:
        outcome = blocked_result_from_exception(error)
    duration_ms = int(outcome.get("duration_ms") or round((time.perf_counter() - started) * 1000))

    async with factory() as session:
        run = await session.get(WorkflowRun, run_id)
        if run is None:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Workflow run was not persisted")
        run.status = str(outcome.get("status") or WorkflowRunStatus.BLOCKED)
        run.completed_at = datetime.now(timezone.utc)
        run.duration_ms = duration_ms
        run.failure_step_id = outcome.get("failure_step_id")
        run.error_code = outcome.get("error_code")
        run.repair_proposal = outcome.get("repair_proposal")
        # Runtime inputs are deliberately absent from outcome and never persisted.
        run.result = {key: value for key, value in outcome.items() if key != "repair_proposal"}
        workflow = await session.get(WorkflowDefinition, workflow_id)
        if workflow is not None:
            workflow.last_run_at = run.completed_at
        session.add(AuditLog(
            organization_id=ctx.organization.id, actor_id=ctx.user.id, action="workflow.run.completed",
            target_type="workflow_run", target_id=run.id,
            metadata_json={"workflow_id": workflow_id, "status": run.status},
        ))
        await session.commit()
        await session.refresh(run)
        return _run_response(run)


@router.get("/{report_id}/workflows/{workflow_id}/runs", response_model=WorkflowRunListResponse)
async def list_workflow_runs(
    report_id: str,
    workflow_id: str,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> WorkflowRunListResponse:
    async with factory() as session:
        await _load_workflow(session, report_id, workflow_id, ctx.organization.id)
        rows = list((await session.scalars(
            select(WorkflowRun).where(
                WorkflowRun.workflow_id == workflow_id,
                WorkflowRun.organization_id == ctx.organization.id,
            ).order_by(WorkflowRun.started_at.desc()).limit(20)
        )).all())
        return WorkflowRunListResponse(items=[_run_response(item) for item in rows])
