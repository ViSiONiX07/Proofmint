"""Response models for guideline PDF extraction and metadata persistence."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SourceSpan(BaseModel):
    """A line-level text span; offsets address the page's returned text."""

    span_id: str
    page_number: int
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    text: str
    # PDF text line bounding boxes are approximate source-location metadata.
    bbox: tuple[float, float, float, float] | None = None


class ExtractedPage(BaseModel):
    page_number: int
    text: str
    spans: list[SourceSpan]


class GuidelineExtraction(BaseModel):
    filename: str
    size_bytes: int
    page_count: int
    sha256: str
    # Populated after the corresponding metadata row commits successfully.
    document_id: UUID | None = None
    created_at: datetime | None = None
    candidate_rule_count: int = Field(default=0, ge=0)
    extraction_status: str = "text_extracted"
    retention_status: Literal["retained", "restored", "already_retained"] = "retained"
    pages: list[ExtractedPage]
    declared_content_type: str | None = None


class FileOutcome(BaseModel):
    filename: str
    status: str
    extraction: GuidelineExtraction | None = None
    error_code: str | None = None
    message: str | None = None


class IngestionSummary(BaseModel):
    files_received: int
    files_succeeded: int
    files_rejected: int
    total_bytes_read: int


class GuidelineIngestionResponse(BaseModel):
    processing_mode: str = "partial_success"
    workspace_id: UUID | None = None
    summary: IngestionSummary
    results: list[FileOutcome]


class RuleSpanComparison(BaseModel):
    """One source span traced across the stored rules and a corrected re-extraction."""

    comparison: Literal["unchanged", "changed", "added", "removed"]
    source_page: int = Field(ge=1)
    source_start_offset: int = Field(ge=0)
    source_end_offset: int = Field(ge=0)
    existing_rule_id: UUID | None = None
    existing_rule_text: str | None = None
    existing_review_status: str | None = None
    extracted_rule_text: str | None = None
    extracted_category: str | None = None
    # True only when an identical rule already carries a human review decision.
    decision_carried_forward: bool = False


class ExtractionRevisionPreview(BaseModel):
    """Read-only comparison of the stored rule set with a corrected re-extraction."""

    workspace_id: UUID
    document_id: UUID
    source_filename: str
    source_sha256: str
    page_count: int = Field(ge=1)
    current_revision: int = Field(ge=1)
    next_revision: int = Field(ge=1)
    already_current: bool
    existing_rule_count: int = Field(ge=0)
    extracted_rule_count: int = Field(ge=0)
    unchanged_count: int = Field(ge=0)
    changed_count: int = Field(ge=0)
    added_count: int = Field(ge=0)
    removed_count: int = Field(ge=0)
    comparisons: list[RuleSpanComparison]
    limitations: list[str]


class ExtractionRevisionRead(BaseModel):
    """The immutable revision a refresh created, or the one already matching it."""

    workspace_id: UUID
    document_id: UUID
    supersedes_document_id: UUID | None = None
    extraction_revision: int = Field(ge=1)
    already_existed: bool
    source_filename: str
    source_sha256: str
    page_count: int = Field(ge=1)
    file_size_bytes: int = Field(gt=0)
    candidate_rule_count: int = Field(ge=0)
    approved_rule_count: int = Field(ge=0)
    pending_rule_count: int = Field(ge=0)
    rejected_rule_count: int = Field(ge=0)
    carried_forward_decisions: int = Field(ge=0)
    removed_rule_count: int = Field(ge=0)
    created_at: datetime | None = None
    limitations: list[str]
