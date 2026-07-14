from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.analysis import now_utc
from app.models.base import Base, uuid_string


class Report(Base):
    """Versioned, evidence-backed projection produced from an analysis."""

    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("analysis_id", "version", name="uq_report_analysis_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, default="local")
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    overall_confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Full render-ready projection consumed by the report viewer.
    document: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    pages_explored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    features_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    model_name: Mapped[str] = mapped_column(String(64), nullable=False, default="heuristic")

    # Saved-report metadata (single-tenant "local" org for now; see DATABASE_SCHEMA saved_reports).
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc
    )


class ReportClaim(Base):
    """An individual observable or inferred statement with a confidence and evidence link."""

    __tablename__ = "report_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    section: Mapped[str] = mapped_column(String(64), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    classification: Mapped[str] = mapped_column(String(16), nullable=False, default="inferred")
    evidence: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, default="heuristic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)
