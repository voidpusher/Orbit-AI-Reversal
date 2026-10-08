from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.analysis import now_utc
from app.models.base import Base, uuid_string


class WorkflowStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class WorkflowRunStatus(StrEnum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


class WorkflowDefinition(Base):
    """A versioned executable contract compiled from report evidence."""

    __tablename__ = "workflow_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "report_id", "contract_key", name="uq_workflow_contract"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    contract_key: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=WorkflowStatus.ACTIVE)
    schedule: Mapped[str] = mapped_column(String(24), nullable=False, default="manual")
    contract: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc
    )


class WorkflowRun(Base):
    """Immutable, redacted result of one workflow replay."""

    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=WorkflowRunStatus.RUNNING)
    trigger: Mapped[str] = mapped_column(String(24), nullable=False, default="manual")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_step_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    repair_proposal: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class WorkflowSecret(Base):
    """Write-only AES-GCM vault entry scoped to one tenant and workflow."""

    __tablename__ = "workflow_secrets"
    __table_args__ = (
        UniqueConstraint("organization_id", "workflow_id", "name", name="uq_workflow_secret_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    key_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc
    )
