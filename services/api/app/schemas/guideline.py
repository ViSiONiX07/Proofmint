"""Response models for guideline PDF extraction and metadata persistence."""

from datetime import datetime
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
