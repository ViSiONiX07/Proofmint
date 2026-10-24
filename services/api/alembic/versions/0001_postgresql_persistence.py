"""Initial guideline and CSV-import persistence schema.

Revision ID: 0001_postgresql_persistence
Revises:
Create Date: 2026-10-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_postgresql_persistence"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guideline_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("file_size_bytes > 0", name="ck_guideline_documents_positive_size"),
        sa.CheckConstraint("length(source_sha256) = 64", name="ck_guideline_documents_sha256_length"),
        sa.CheckConstraint("page_count > 0", name="ck_guideline_documents_positive_pages"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_guideline_documents_source_sha256", "guideline_documents", ["source_sha256"])

    op.create_table(
        "candidate_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=False),
        sa.Column("source_start_offset", sa.Integer(), nullable=False),
        sa.Column("source_end_offset", sa.Integer(), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=20), server_default=sa.text("'pending_review'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "review_status IN ('pending_review', 'approved', 'rejected')",
            name="ck_candidate_rules_review_status",
        ),
        sa.CheckConstraint("source_end_offset > source_start_offset", name="ck_candidate_rules_valid_offsets"),
        sa.CheckConstraint("source_page > 0", name="ck_candidate_rules_positive_page"),
        sa.CheckConstraint("source_start_offset >= 0", name="ck_candidate_rules_nonnegative_start"),
        sa.ForeignKeyConstraint(["document_id"], ["guideline_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidate_rules_document_status", "candidate_rules", ["document_id", "review_status"])

    op.create_table(
        "imported_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_fact_id", sa.String(length=100), nullable=True),
        sa.Column("claim_type", sa.String(length=100), nullable=False),
        sa.Column("approved_statement", sa.Text(), nullable=False),
        sa.Column("source_document", sa.String(length=255), nullable=True),
        sa.Column("source_page_span", sa.String(length=100), nullable=True),
        sa.Column("verified_date", sa.Date(), nullable=True),
        sa.Column("source_status", sa.String(length=50), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("review_status", sa.String(length=20), server_default=sa.text("'pending_review'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(source_sha256) = 64", name="ck_imported_facts_sha256_length"),
        sa.CheckConstraint("source_row_number > 0", name="ck_imported_facts_positive_source_row"),
        sa.CheckConstraint(
            "review_status IN ('pending_review', 'approved', 'rejected')",
            name="ck_imported_facts_review_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_imported_facts_import_source", "imported_facts", ["source_filename", "source_row_number"])
    op.create_index("ix_imported_facts_review_status", "imported_facts", ["review_status"])

    op.create_table(
        "imported_terms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("term", sa.String(length=255), nullable=False),
        sa.Column("preferred_form", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("usage_notes", sa.Text(), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("review_status", sa.String(length=20), server_default=sa.text("'pending_review'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(source_sha256) = 64", name="ck_imported_terms_sha256_length"),
        sa.CheckConstraint("source_row_number > 0", name="ck_imported_terms_positive_source_row"),
        sa.CheckConstraint(
            "review_status IN ('pending_review', 'approved', 'rejected')",
            name="ck_imported_terms_review_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_imported_terms_import_source", "imported_terms", ["source_filename", "source_row_number"])
    op.create_index("ix_imported_terms_review_status", "imported_terms", ["review_status"])


def downgrade() -> None:
    op.drop_index("ix_imported_terms_review_status", table_name="imported_terms")
    op.drop_index("ix_imported_terms_import_source", table_name="imported_terms")
    op.drop_table("imported_terms")
    op.drop_index("ix_imported_facts_review_status", table_name="imported_facts")
    op.drop_index("ix_imported_facts_import_source", table_name="imported_facts")
    op.drop_table("imported_facts")
    op.drop_index("ix_candidate_rules_document_status", table_name="candidate_rules")
    op.drop_table("candidate_rules")
    op.drop_index("ix_guideline_documents_source_sha256", table_name="guideline_documents")
    op.drop_table("guideline_documents")
