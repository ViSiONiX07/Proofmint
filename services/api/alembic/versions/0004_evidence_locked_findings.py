"""Add verification metadata to audit findings.

Revision ID: 0004_evidence_locked_findings
Revises: 0003_session_workspaces
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_evidence_locked_findings"
down_revision = "0003_session_workspaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_findings", sa.Column(
        "verification_status", sa.String(20), server_default=sa.text("'unverified'"), nullable=False
    ))
    op.add_column("audit_findings", sa.Column("verification_reason", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_findings", "verification_reason")
    op.drop_column("audit_findings", "verification_status")
