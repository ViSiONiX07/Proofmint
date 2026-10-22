from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class HealthCheck(BaseModel):
    status: str
    service: str
    version: str
    timestamp: datetime

class EvidenceSpan(BaseModel):
    document_name: str
    page_number: Optional[int] = None
    source_sha256: str
    excerpt: str

class SuggestedRepair(BaseModel):
    original_text: str
    repaired_text: str
    semantic_distance: float
    token_delta: int

class Finding(BaseModel):
    rule_id: str
    rule_name: str
    severity: str  # e.g., "VIOLATION", "WARNING", "SUGGESTION"
    trigger_segment: str
    explanation: str
    evidence: EvidenceSpan
    repair: SuggestedRepair

class ClearanceDecision(BaseModel):
    decision_type: str  # ACCEPT_REPAIR, LEGAL_ESCALATE, OVERRIDE
    author_id: str
    timestamp: datetime
    cryptographic_token: str
