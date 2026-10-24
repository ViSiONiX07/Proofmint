"""Schemas for CSV fact and terminology imports."""

from typing import Literal

from pydantic import BaseModel, Field


class ImportRowError(BaseModel):
    row_number: int = Field(ge=2)
    errors: dict[str, str]


class ImportSummary(BaseModel):
    rows_read: int
    rows_imported: int
    rows_skipped: int = 0
    rows_rejected: int


class CsvImportResponse(BaseModel):
    processing_mode: Literal["partial_success"] = "partial_success"
    review_status: Literal["pending_review"] = "pending_review"
    summary: ImportSummary
    errors: list[ImportRowError]
