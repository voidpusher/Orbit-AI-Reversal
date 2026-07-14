import json
import hmac
from collections.abc import AsyncIterator
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_auth_context, get_auth_service, get_events, get_queue
from app.core.config import get_settings
from app.models import Analysis, AnalysisStatus, AuditLog, Report
from app.schemas import AnalysisOptions, AnalysisResponse, CreateAnalysisRequest, ImportHarRequest
from app.services.auth import AuthContext, AuthService, PLAN_LIMITS
from app.services.events import EventService
from app.services.har_import import build_har_evidence
from app.services.queue import AnalysisQueue
from app.services.url_policy import normalize_public_url

router = APIRouter(prefix="/analyses", tags=["analyses"])


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


def as_response(analysis: Analysis, report_id: str | None = None) -> AnalysisResponse:
    return AnalysisResponse(
        id=analysis.id,
        target_url=analysis.target_url,
        status=analysis.status,
        progress=analysis.progress,
        options=AnalysisOptions.model_validate(analysis.options),
        requested_at=analysis.requested_at,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        event_stream_url=f"/api/v1/analyses/{analysis.id}/events",
        report_id=report_id,
        error_code=analysis.error_code,
    )


async def load_analysis(factory: async_sessionmaker[AsyncSession], analysis_id: str) -> Analysis:
    async with factory() as session:
        analysis = await session.get(Analysis, analysis_id)
        if analysis is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
        return analysis


async def create_analysis_record(
    *,
    factory: async_sessionmaker[AsyncSession],
    auth: AuthService,
    ctx: AuthContext,
    target_url: str,
    options: AnalysisOptions,
    idempotency_key: str,
) -> tuple[Analysis, bool]:
    org_id = ctx.organization.id
    async with factory() as session:
        existing = await session.scalar(
            select(Analysis).where(Analysis.organization_id == org_id, Analysis.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing, False

        limit = PLAN_LIMITS.get(ctx.organization.plan)
        if limit is not None:
            used = await auth.usage_this_month(org_id)
            if used >= limit:
                raise HTTPException(
                    status.HTTP_402_PAYMENT_REQUIRED,
                    f"Monthly analysis limit reached for the {ctx.organization.plan} plan ({limit}). Upgrade to continue.",
                )

        analysis = Analysis(
            organization_id=org_id,
            target_url=target_url,
            options=options.model_dump(),
            idempotency_key=idempotency_key,
        )
        session.add(analysis)
        session.add(AuditLog(
            organization_id=org_id, actor_id=ctx.user.id, action="analysis.created",
            target_type="analysis", target_id=analysis.id,
            metadata_json={"target_url": target_url, "evidence_mode": options.evidence_mode},
        ))
        await session.commit()
        await session.refresh(analysis)
        return analysis, True


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(
    payload: CreateAnalysisRequest,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=255),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    events: EventService = Depends(get_events),
    queue: AnalysisQueue = Depends(get_queue),
    ctx: AuthContext = Depends(get_auth_context),
    auth: AuthService = Depends(get_auth_service),
) -> AnalysisResponse:
    settings = get_settings()
    target_url = normalize_public_url(str(payload.target_url), settings.allowed_analysis_hosts)
    target_parts = urlsplit(target_url)
    target_url = urlunsplit((target_parts.scheme, target_parts.netloc, target_parts.path or "/", "", ""))
    options = payload.options.model_copy(update={"evidence_mode": "crawl"})
    analysis, created = await create_analysis_record(
        factory=factory, auth=auth, ctx=ctx, target_url=target_url,
        options=options, idempotency_key=idempotency_key,
    )
    if not created:
        return as_response(analysis)
    await events.append(analysis.id, "analysis.queued", "Analysis queued for exploration", {"idempotency_key": idempotency_key})
    await queue.enqueue(analysis.id)
    # Inline serverless queues complete before returning; background queues still
    # return the latest state available at this point.
    analysis = await load_analysis(factory, analysis.id)
    async with factory() as session:
        report_id = await session.scalar(
            select(Report.id).where(Report.analysis_id == analysis.id, Report.is_deleted.is_(False))
        )
    return as_response(analysis, report_id)


@router.post("/har", response_model=AnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_har_analysis(
    payload: ImportHarRequest,
    idempotency_key: str = Header(min_length=8, max_length=255),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    events: EventService = Depends(get_events),
    queue: AnalysisQueue = Depends(get_queue),
    ctx: AuthContext = Depends(get_auth_context),
    auth: AuthService = Depends(get_auth_service),
) -> AnalysisResponse:
    settings = get_settings()
    target_url = normalize_public_url(str(payload.target_url), settings.allowed_analysis_hosts)
    target_parts = urlsplit(target_url)
    target_url = urlunsplit((target_parts.scheme, target_parts.netloc, target_parts.path or "/", "", ""))
    options = AnalysisOptions(
        deep_crawl=False,
        max_pages=min(50, len(payload.entries)),
        capture_network_requests=True,
        evidence_mode="har",
    )
    analysis, created = await create_analysis_record(
        factory=factory, auth=auth, ctx=ctx, target_url=target_url,
        options=options, idempotency_key=idempotency_key,
    )
    if not created:
        return as_response(analysis)

    target_host = (urlsplit(target_url).hostname or "").lower()
    evidence = build_har_evidence(analysis.id, payload.entries, target_host)
    async with factory() as session:
        session.add_all(evidence)
        await session.commit()
    await events.append(
        analysis.id,
        "har.imported",
        "Sanitized browser session imported",
        {"network_entries": len(payload.entries), "evidence_items": len(evidence), "redaction_version": "har-v1"},
    )
    await events.append(analysis.id, "analysis.queued", "Analysis queued from imported browser evidence")
    await queue.enqueue(analysis.id)
    analysis = await load_analysis(factory, analysis.id)
    async with factory() as session:
        report_id = await session.scalar(
            select(Report.id).where(Report.analysis_id == analysis.id, Report.is_deleted.is_(False))
        )
    return as_response(analysis, report_id)


@router.post("/internal/process", include_in_schema=False)
async def process_queued_analysis(
    analysis_id: str,
    request: Request,
    capture_secret: str | None = Header(default=None, alias="X-Orbit-Capture-Secret"),
) -> dict[str, str]:
    expected = get_settings().capture_secret
    if not expected or not capture_secret or not hmac.compare_digest(capture_secret, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid worker secret")
    await request.app.state.explorer.process(analysis_id, raise_on_failure=True)
    return {"status": "processed", "analysis_id": analysis_id}


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: str,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    ctx: AuthContext = Depends(get_auth_context),
) -> AnalysisResponse:
    async with factory() as session:
        analysis = await session.get(Analysis, analysis_id)
        if analysis is None or analysis.organization_id != ctx.organization.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
        report_id = await session.scalar(
            select(Report.id).where(Report.analysis_id == analysis_id, Report.is_deleted.is_(False))
        )
    return as_response(analysis, report_id)


@router.post("/{analysis_id}/cancel", response_model=AnalysisResponse)
async def cancel_analysis(
    analysis_id: str,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    events: EventService = Depends(get_events),
    ctx: AuthContext = Depends(get_auth_context),
) -> AnalysisResponse:
    async with factory() as session:
        analysis = await session.get(Analysis, analysis_id)
        if analysis is None or analysis.organization_id != ctx.organization.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
        if analysis.status in {AnalysisStatus.COMPLETED, AnalysisStatus.FAILED}:
            raise HTTPException(status.HTTP_409_CONFLICT, "This analysis has already reached a terminal state")
        analysis.status = AnalysisStatus.CANCELLED
        analysis.progress = min(analysis.progress, 99)
        await session.commit()
        await session.refresh(analysis)
    await events.append(analysis_id, "analysis.cancelled", "Cancellation requested")
    return as_response(analysis)


@router.get("/{analysis_id}/events")
async def stream_analysis_events(
    analysis_id: str,
    request: Request,
    after: int = 0,
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    events: EventService = Depends(get_events),
) -> StreamingResponse:
    await load_analysis(factory, analysis_id)

    async def event_stream() -> AsyncIterator[str]:
        async for event in events.stream(analysis_id, after):
            if await request.is_disconnected():
                return
            if event is None:
                yield ": keepalive\n\n"
            else:
                yield f"id: {event.sequence}\nevent: {event.kind}\ndata: {json.dumps(event.model_dump(mode='json'))}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
