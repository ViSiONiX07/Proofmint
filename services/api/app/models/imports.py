"""Pending-review persistence for future approved-facts and terminology CSV imports."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ImportedFact(TimestampMixin, Base):
    __tablename__ = "imported_facts"
    __table_args__ = (
        CheckConstraint("source_row_number > 0", name="ck_imported_facts_positive_source_row"),
        CheckConstraint("length(source_sha256) = 64", name="ck_imported_facts_sha256_length"),
        CheckConstraint(
            "review_status IN ('pending_review', 'approved', 'rejected')",
            name="ck_imported_facts_review_status",
        ),
        Index("ix_imported_facts_review_status", "review_status"),
        Index("ix_imported_facts_import_source", "source_filename", "source_row_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True)
    external_fact_id: Mapped[str | None] = mapped_column(String(100))
    claim_type: Mapped[str] = mapped_column(String(100), nullable=False)
    approved_statement: Mapped[str] = mapped_column(Text, nullable=False)
    source_document: Mapped[str | None] = mapped_column(String(255))
    source_page_span: Mapped[str | None] = mapped_column(String(100))
    verified_date: Mapped[date | None] = mapped_column(Date)
    source_status: Mapped[str | None] = mapped_column(String(50))
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row_number: Mapped[int] = mapped_column(nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending_review", server_default=text("'pending_review'")
    )


class ImportedTerm(TimestampMixin, Base):
    __tablename__ = "imported_terms"
    __table_args__ = (
        CheckConstraint("source_row_number > 0", name="ck_imported_terms_positive_source_row"),
        CheckConstraint("length(source_sha256) = 64", name="ck_imported_terms_sha256_length"),
        CheckConstraint(
            "review_status IN ('pending_review', 'approved', 'rejected')",
            name="ck_imported_terms_review_status",
        ),
        Index("ix_imported_terms_review_status", "review_status"),
        Index("ix_imported_terms_import_source", "source_filename", "source_row_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True)
    term: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_form: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100))
    usage_notes: Mapped[str | None] = mapped_column(Text)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row_number: Mapped[int] = mapped_column(nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending_review", server_default=text("'pending_review'")
    )
