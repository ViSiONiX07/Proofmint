"""Snapshot exact source-document versions on historical findings.

Revision ID: 0006_audit_source_version
Revises: 0005_verification_review_reasons
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_audit_source_version"
down_revision = "0005_verification_review_reasons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_findings", sa.Column("source_document_id", sa.Uuid(), nullable=True))
    op.add_column("audit_findings", sa.Column("source_document_sha256", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        "fk_audit_findings_source_document_id_guideline_documents",
        "audit_findings", "guideline_documents", ["source_document_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("ix_audit_findings_source_document_id", "audit_findings", ["source_document_id"])
    op.execute("""
        UPDATE audit_findings AS finding
        SET source_document_id = candidate.document_id,
            source_document_sha256 = document.source_sha256
        FROM candidate_rules AS candidate
        JOIN guideline_documents AS document ON document.id = candidate.document_id
        WHERE finding.rule_id = candidate.id
    """)


def downgrade() -> None:
    op.drop_index("ix_audit_findings_source_document_id", table_name="audit_findings")
    op.drop_constraint("fk_audit_findings_source_document_id_guideline_documents", "audit_findings", type_="foreignkey")
    op.drop_column("audit_findings", "source_document_sha256")
    op.drop_column("audit_findings", "source_document_id")
