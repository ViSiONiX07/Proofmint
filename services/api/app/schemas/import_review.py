"""Response schemas for human review of imported facts and terminology."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.candidate_rule import ReviewStatus


class ImportedFactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_fact_id: str | None
    claim_type: str
    approved_statement: str
    source_document: str | None
    source_page_span: str | None
    verified_date: date | None
    source_status: str | None
    source_filename: str
    source_row_number: int
    source_sha256: str
    imported_at: datetime
    review_status: ReviewStatus
    created_at: datetime
    updated_at: datetime


class ImportedTermRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    term: str
    preferred_form: str | None
    category: str | None
    usage_notes: str | None
    source_filename: str
    source_row_number: int
    source_sha256: str
    imported_at: datetime
    review_status: ReviewStatus
    created_at: datetime
    updated_at: datetime


class ImportedFactList(BaseModel):
    items: list[ImportedFactRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class ImportedTermList(BaseModel):
    items: list[ImportedTermRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
