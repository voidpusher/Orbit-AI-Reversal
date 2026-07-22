import base64
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_auth_context
from app.models import Analysis, AuditLog, Report, Role
from app.schemas import (
    ComparisonResponse,
    ExportRequest,
    ExportResponse,
    ReportDetail,
    ReportListItem,
    ReportListResponse,
    StatsResponse,
    UpdateReportRequest,
)
from app.services.auth import AuthContext
from app.services.compare import build_comparison
from app.services.export import render_markdown

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
