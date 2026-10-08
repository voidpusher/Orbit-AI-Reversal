"""encrypted workflow secret vault

Revision ID: c72e04dfb9a1
Revises: 8d31b4a90c2e
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c72e04dfb9a1"
down_revision: Union[str, Sequence[str], None] = "8d31b4a90c2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_secrets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("key_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "workflow_id", "name", name="uq_workflow_secret_name"),
    )


def downgrade() -> None:
    op.drop_table("workflow_secrets")
