"""Track immutable extraction (rule-set) revisions of retained guideline sources.

Revision ID: 0007_extraction_revisions
Revises: 0006_audit_source_version
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_extraction_revisions"
down_revision = "0006_audit_source_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing documents are revision 1 of their own lineage. Their extracted rule set was
    # produced by the pre-revision extractor, so extraction_signature stays NULL ("unknown")
    # and the document remains eligible for a corrected re-extraction.
    op.add_column("guideline_documents", sa.Column(
        "extraction_revision", sa.Integer(), server_default=sa.text("1"), nullable=False
    ))
    op.add_column("guideline_documents", sa.Column("supersedes_document_id", sa.Uuid(), nullable=True))
    op.add_column("guideline_documents", sa.Column("extraction_signature", sa.String(length=64), nullable=True))
    op.create_check_constraint(
        "ck_guideline_documents_positive_revision", "guideline_documents", "extraction_revision >= 1"
    )
    op.create_foreign_key(
        None,
        "guideline_documents", "guideline_documents", ["supersedes_document_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("ix_guideline_documents_supersedes_document_id", "guideline_documents", ["supersedes_document_id"])
    op.create_index(
        "ix_guideline_documents_lineage", "guideline_documents", ["workspace_id", "source_sha256", "extraction_revision"]
    )


def downgrade() -> None:
    op.drop_index("ix_guideline_documents_lineage", table_name="guideline_documents")
    op.drop_index("ix_guideline_documents_supersedes_document_id", table_name="guideline_documents")
    op.drop_constraint(
        "fk_guideline_documents_supersedes_document_id_guideline_documents", "guideline_documents", type_="foreignkey"
    )
    op.drop_constraint("ck_guideline_documents_positive_revision", "guideline_documents", type_="check")
    op.drop_column("guideline_documents", "extraction_signature")
    op.drop_column("guideline_documents", "supersedes_document_id")
    op.drop_column("guideline_documents", "extraction_revision")
