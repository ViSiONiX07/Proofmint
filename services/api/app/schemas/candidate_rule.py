"""API schemas for candidate-rule review."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ReviewStatus = Literal["pending_review", "approved", "rejected"]


class CandidateRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    rule_text: str
    category: str | None
    source_page: int
    source_start_offset: int
    source_end_offset: int
    source_excerpt: str
    review_status: ReviewStatus
    created_at: datetime
    updated_at: datetime
    source_filename: str
    source_sha256: str


class CandidateRuleList(BaseModel):
    items: list[CandidateRuleRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
