"""persistent workflow definitions and replay runs

Revision ID: 8d31b4a90c2e
Revises: 04fcd0700df6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d31b4a90c2e"
down_revision: Union[str, Sequence[str], None] = "04fcd0700df6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("contract_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("schedule", sa.String(length=24), nullable=False),
        sa.Column("contract", sa.JSON(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "report_id", "contract_key", name="uq_workflow_contract"),
    )
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("trigger", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("failure_step_id", sa.String(length=100), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("repair_proposal", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("workflow_runs")
    op.drop_table("workflow_definitions")
