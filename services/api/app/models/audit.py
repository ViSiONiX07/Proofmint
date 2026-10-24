"""Persisted deterministic audit runs, findings, decisions, and clearances."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditRun(Base):
    __tablename__ = "audit_runs"
    __table_args__ = (
        CheckConstraint("length(content_sha256) = 64", name="ck_audit_runs_sha256_length"),
        CheckConstraint("character_count >= 0", name="ck_audit_runs_character_count"),
        CheckConstraint("review_status IN ('pending_review', 'cleared', 'blocked')", name="ck_audit_runs_review_status"),
        Index("ix_audit_runs_created_at", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True)
    document_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("guideline_documents.id", ondelete="SET NULL"))
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_rules_considered: Mapped[int] = mapped_column(Integer, nullable=False)
    supported_checks_performed: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_unevaluated: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_limitations: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review", server_default=text("'pending_review'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditFinding(Base):
    __tablename__ = "audit_findings"
    __table_args__ = (
        CheckConstraint("status IN ('pending_review', 'resolved', 'dismissed', 'flagged', 'informational')", name="ck_audit_findings_status"),
        Index("ix_audit_findings_audit_status", "audit_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    audit_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("audit_runs.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("candidate_rules.id", ondelete="SET NULL"))
    fact_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("imported_facts.id", ondelete="SET NULL"))
    term_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("imported_terms.id", ondelete="SET NULL"))
    finding_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review", server_default=text("'pending_review'"))
    matched_phrase: Mapped[str] = mapped_column(String(500), nullable=False)
    match_start: Mapped[int] = mapped_column(Integer, nullable=False)
    match_end: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_correction: Mapped[str | None] = mapped_column(String(500))
    source_filename: Mapped[str | None] = mapped_column(String(255))
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_start_offset: Mapped[int | None] = mapped_column(Integer)
    source_end_offset: Mapped[int | None] = mapped_column(Integer)
    evidence_excerpt: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FindingDecision(Base):
    __tablename__ = "finding_decisions"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    finding_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("audit_findings.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ClearanceRecord(Base):
    __tablename__ = "clearance_records"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    audit_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("audit_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    checks_performed: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
