"""Persist audit runs, findings, decisions and clearances.

Revision ID: 0002_persisted_audits
Revises: 0001_postgresql_persistence
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_persisted_audits"
down_revision = "0001_postgresql_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("approved_rules_considered", sa.Integer(), nullable=False),
        sa.Column("supported_checks_performed", sa.Integer(), nullable=False),
        sa.Column("rules_unevaluated", sa.Integer(), nullable=False),
        sa.Column("scope_limitations", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(20), server_default=sa.text("'pending_review'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(content_sha256) = 64", name="ck_audit_runs_sha256_length"),
        sa.CheckConstraint("character_count >= 0", name="ck_audit_runs_character_count"),
        sa.CheckConstraint("review_status IN ('pending_review', 'cleared', 'blocked')", name="ck_audit_runs_review_status"),
        sa.ForeignKeyConstraint(["document_id"], ["guideline_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_runs_created_at", "audit_runs", ["created_at"])
    op.create_table(
        "audit_findings",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("audit_id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=True), sa.Column("fact_id", sa.Uuid(), nullable=True),
        sa.Column("term_id", sa.Uuid(), nullable=True), sa.Column("finding_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending_review'"), nullable=False),
        sa.Column("matched_phrase", sa.String(500), nullable=False), sa.Column("match_start", sa.Integer(), nullable=False),
        sa.Column("match_end", sa.Integer(), nullable=False), sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("suggested_correction", sa.String(500), nullable=True), sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True), sa.Column("source_start_offset", sa.Integer(), nullable=True),
        sa.Column("source_end_offset", sa.Integer(), nullable=True), sa.Column("evidence_excerpt", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending_review', 'resolved', 'dismissed', 'flagged', 'informational')", name="ck_audit_findings_status"),
        sa.ForeignKeyConstraint(["audit_id"], ["audit_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["candidate_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["fact_id"], ["imported_facts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["term_id"], ["imported_terms.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_findings_audit_status", "audit_findings", ["audit_id", "status"])
    op.create_table("finding_decisions", sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False), sa.Column("action", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["finding_id"], ["audit_findings.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_finding_decisions_finding_id", "finding_decisions", ["finding_id"])
    op.create_table("clearance_records", sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("audit_id", sa.Uuid(), nullable=False), sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("checks_performed", sa.Integer(), nullable=False), sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["audit_runs.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_clearance_records_audit_id", "clearance_records", ["audit_id"])


def downgrade() -> None:
    op.drop_index("ix_clearance_records_audit_id", table_name="clearance_records")
    op.drop_table("clearance_records")
    op.drop_index("ix_finding_decisions_finding_id", table_name="finding_decisions")
    op.drop_table("finding_decisions")
    op.drop_index("ix_audit_findings_audit_status", table_name="audit_findings")
    op.drop_table("audit_findings")
    op.drop_index("ix_audit_runs_created_at", table_name="audit_runs")
    op.drop_table("audit_runs")
