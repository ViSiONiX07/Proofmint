"""Persist append-only reviewer decisions for supported repair proposals.

Revision ID: 0008_persisted_repair_decisions
Revises: 0007_extraction_revisions
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_persisted_repair_decisions"
down_revision = "0007_extraction_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repair_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("proposed_replacement", sa.String(length=500), nullable=True),
        sa.Column("review_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["finding_id"], ["audit_findings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("action IN ('accept', 'edit', 'reject')", name="ck_repair_decisions_action"),
    )
    op.create_index("ix_repair_decisions_finding_id", "repair_decisions", ["finding_id"])


def downgrade() -> None:
    op.drop_index("ix_repair_decisions_finding_id", table_name="repair_decisions")
    op.drop_table("repair_decisions")
