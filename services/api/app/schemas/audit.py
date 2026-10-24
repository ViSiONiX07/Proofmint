"""Validated audit, finding decision, and clearance API contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditCreate(BaseModel):
    workspace_id: UUID
    content: str = Field(min_length=1, max_length=200_000)
    document_id: UUID | None = None


class FindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    audit_id: UUID
    rule_id: UUID | None
    fact_id: UUID | None
    term_id: UUID | None
    finding_type: str
    status: str
    matched_phrase: str
    match_start: int
    match_end: int
    explanation: str
    suggested_correction: str | None
    source_filename: str | None
    source_page: int | None
    source_start_offset: int | None
    source_end_offset: int | None
    evidence_excerpt: str | None
    created_at: datetime


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    finding_id: UUID
    action: str
    created_at: datetime


class ClearanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    audit_id: UUID
    decision: str
    checks_performed: int
    content_sha256: str
    created_at: datetime


class AuditRead(BaseModel):
    id: UUID
    workspace_id: UUID
    document_id: UUID | None
    content_sha256: str
    character_count: int
    approved_rules_considered: int
    supported_checks_performed: int
    rules_unevaluated: int
    scope_limitations: list[str]
    review_status: str
    created_at: datetime
    findings: list[FindingRead]
    decisions: list[DecisionRead]
    clearance: ClearanceRead | None


class FindingDecisionCreate(BaseModel):
    action: Literal["accept_suggestion", "dismiss", "flag"]


class ClearanceCreate(BaseModel):
    decision: Literal["cleared", "hold"]
