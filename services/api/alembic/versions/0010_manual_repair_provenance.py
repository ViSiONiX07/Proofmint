"""Persist human-authored manual repair provenance.

Revision ID: 0010_manual_repair_provenance
Revises: 0009_auth_users_sessions
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_manual_repair_provenance"
down_revision = "0009_auth_users_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_repair_decisions_action", "repair_decisions", type_="check")
    op.create_check_constraint(
        "ck_repair_decisions_action", "repair_decisions",
        "action IN ('accept', 'edit', 'reject', 'manual')",
    )
    op.add_column("repair_decisions", sa.Column("original_text", sa.Text(), nullable=True))
    op.add_column("repair_decisions", sa.Column("revised_text", sa.Text(), nullable=True))
    op.add_column("repair_decisions", sa.Column("provenance", sa.String(length=30), server_default="evidence_backed", nullable=False))
    op.add_column("repair_decisions", sa.Column("workspace_id", sa.Uuid(), nullable=True))
    op.add_column("repair_decisions", sa.Column("reviewer_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_repair_decisions_workspace_id", "repair_decisions", "workspaces", ["workspace_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_repair_decisions_reviewer_user_id", "repair_decisions", "users", ["reviewer_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_repair_decisions_workspace_id", "repair_decisions", ["workspace_id"])
    op.create_index("ix_repair_decisions_reviewer_user_id", "repair_decisions", ["reviewer_user_id"])


def downgrade() -> None:
    op.drop_index("ix_repair_decisions_reviewer_user_id", table_name="repair_decisions")
    op.drop_index("ix_repair_decisions_workspace_id", table_name="repair_decisions")
    op.drop_constraint("fk_repair_decisions_reviewer_user_id", "repair_decisions", type_="foreignkey")
    op.drop_constraint("fk_repair_decisions_workspace_id", "repair_decisions", type_="foreignkey")
    op.drop_column("repair_decisions", "reviewer_user_id")
    op.drop_column("repair_decisions", "workspace_id")
    op.drop_column("repair_decisions", "provenance")
    op.drop_column("repair_decisions", "revised_text")
    op.drop_column("repair_decisions", "original_text")
    op.drop_constraint("ck_repair_decisions_action", "repair_decisions", type_="check")
    op.create_check_constraint("ck_repair_decisions_action", "repair_decisions", "action IN ('accept', 'edit', 'reject')")
