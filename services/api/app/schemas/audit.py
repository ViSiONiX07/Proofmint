"""Validated audit, finding decision, and clearance API contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuditCreate(BaseModel):
    workspace_id: UUID
    content: str = Field(min_length=1, max_length=200_000)
    document_id: UUID | None = None


class FindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    audit_id: UUID
    rule_id: UUID | None
    source_document_id: UUID | None
    source_document_sha256: str | None
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
    verification_status: Literal["verified", "uncertain", "rejected"]
    verification_reason: str | None
    verification_explanation: str | None
    created_at: datetime


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    finding_id: UUID
    action: str
    review_reason: str | None
    created_at: datetime


class RepairDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    finding_id: UUID
    action: Literal["accept", "edit", "reject", "manual"]
    proposed_replacement: str | None
    original_text: str | None
    revised_text: str | None
    provenance: str
    workspace_id: UUID | None
    reviewer_user_id: UUID | None
    review_reason: str | None
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
    repair_decisions: list[RepairDecisionRead]
    clearance: ClearanceRead | None


class FindingDecisionCreate(BaseModel):
    action: Literal["accept_suggestion", "dismiss", "flag"]
    reason: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, min_length=1, max_length=200_000)

    @model_validator(mode="after")
    def require_content_for_acceptance(self):
        if self.action == "accept_suggestion" and self.content is None:
            raise ValueError("Original submitted content is required to accept a suggestion safely.")
        return self


class ClearanceCreate(BaseModel):
    decision: Literal["cleared", "hold"]


class AuditReportRequest(BaseModel):
    """Supported document format; exports always carry both mandatory watermarks."""

    model_config = ConfigDict(extra="forbid")
    format: Literal["pdf", "docx"]


class RepairRequest(BaseModel):
    content: str = Field(min_length=1, max_length=200_000)


class RepairDecisionCreate(BaseModel):
    action: Literal["accept", "edit", "reject", "manual"]
    content: str = Field(min_length=1, max_length=200_000)
    replacement: str | None = Field(default=None, max_length=500)
    revised_content: str | None = Field(default=None, max_length=200_000)
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_replacement(self):
        if self.action == "manual":
            if not self.revised_content or not self.revised_content.strip():
                raise ValueError("Manual decisions require revised content.")
            return self
        if self.action in {"accept", "edit"} and not (self.replacement or "").strip():
            raise ValueError("Accept and edit decisions require replacement text.")
        if self.action == "reject" and self.replacement is not None:
            raise ValueError("Reject decisions cannot include replacement text.")
        return self


class SourceEvidenceRecheckCreate(BaseModel):
    content: str = Field(min_length=1, max_length=200_000)


class RepairRead(BaseModel):
    audit_id: UUID
    original_sha256: str
    status: Literal["no_findings", "no_open_findings", "review_required", "no_supported_repairs", "preview_available"]
    findings_reviewed: int
    repaired_content: str
    replacements: list["RepairReplacement"]
    checks_before: int
    checks_after: int
    findings_before: int
    findings_after: int
    limitations: list[str]


class RepairReplacement(BaseModel):
    finding_id: UUID
    start: int
    end: int
    original: str
    replacement: str
    source_filename: str
    source_label: str
    reason: str


class RuleAmbiguityRead(BaseModel):
    rule_id: UUID
    rule_text: str
    source_filename: str
    source_page: int
    decision_count: int
    dismissals: int
    flags: int
    accepted_suggestions: int
    review_reasons: list[str]
    dismissal_rate: float
    ambiguity_score: float | None
    signal: Literal["insufficient_data", "no_repeated_signal", "repeated_review_signal"]


class AmbiguityRadarRead(BaseModel):
    workspace_id: UUID
    minimum_decisions: int
    rules: list[RuleAmbiguityRead]
    limitations: list[str]
