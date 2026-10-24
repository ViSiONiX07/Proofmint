"""Persisted guideline provenance and human-reviewed candidate rules."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class GuidelineDocument(TimestampMixin, Base):
    __tablename__ = "guideline_documents"
    __table_args__ = (
        CheckConstraint("file_size_bytes > 0", name="ck_guideline_documents_positive_size"),
        CheckConstraint("page_count > 0", name="ck_guideline_documents_positive_pages"),
        CheckConstraint("length(source_sha256) = 64", name="ck_guideline_documents_sha256_length"),
        Index("ix_guideline_documents_source_sha256", "source_sha256"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(nullable=False)
    page_count: Mapped[int] = mapped_column(nullable=False)

    candidate_rules: Mapped[list["CandidateRule"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class CandidateRule(TimestampMixin, Base):
    __tablename__ = "candidate_rules"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('pending_review', 'approved', 'rejected')",
            name="ck_candidate_rules_review_status",
        ),
        CheckConstraint("source_page > 0", name="ck_candidate_rules_positive_page"),
        CheckConstraint("source_start_offset >= 0", name="ck_candidate_rules_nonnegative_start"),
        CheckConstraint("source_end_offset > source_start_offset", name="ck_candidate_rules_valid_offsets"),
        Index("ix_candidate_rules_document_status", "document_id", "review_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("guideline_documents.id", ondelete="CASCADE"), nullable=False
    )
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    source_page: Mapped[int] = mapped_column(nullable=False)
    source_start_offset: Mapped[int] = mapped_column(nullable=False)
    source_end_offset: Mapped[int] = mapped_column(nullable=False)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending_review", server_default=text("'pending_review'")
    )

    document: Mapped[GuidelineDocument] = relationship(back_populates="candidate_rules")
