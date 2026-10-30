"""Store machine-readable verification outcomes and human review reasons.

Revision ID: 0005_verification_and_review_reasons
Revises: 0004_evidence_locked_findings
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_verification_review_reasons"
down_revision = "0004_evidence_locked_findings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_findings", sa.Column("verification_explanation", sa.Text(), nullable=True))
    op.add_column("finding_decisions", sa.Column("review_reason", sa.String(500), nullable=True))
    op.execute("UPDATE audit_findings SET verification_status = 'uncertain' WHERE verification_status NOT IN ('verified', 'uncertain', 'rejected')")
    op.alter_column("audit_findings", "verification_status", server_default=sa.text("'uncertain'"))
    op.create_check_constraint(
        "ck_audit_findings_verification_status", "audit_findings",
        "verification_status IN ('verified', 'uncertain', 'rejected')",
    )
    op.create_index("ix_audit_findings_rule_id", "audit_findings", ["rule_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_findings_rule_id", table_name="audit_findings")
    op.drop_constraint("ck_audit_findings_verification_status", "audit_findings", type_="check")
    op.alter_column("audit_findings", "verification_status", server_default=sa.text("'unverified'"))
    op.drop_column("finding_decisions", "review_reason")
    op.drop_column("audit_findings", "verification_explanation")
