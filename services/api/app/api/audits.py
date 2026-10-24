"""Persistent deterministic content audits and human review decisions."""

import hashlib
import json
import logging
from collections.abc import Generator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.core.database import DatabaseNotConfiguredError, get_db_session
from app.models.audit import AuditFinding, AuditRun, ClearanceRecord, FindingDecision
from app.models.guideline import CandidateRule, GuidelineDocument
from app.models.imports import ImportedFact, ImportedTerm
from app.models.workspace import Workspace
from app.schemas.audit import AuditCreate, AuditRead, ClearanceCreate, FindingDecisionCreate
from app.services.audit_engine import evaluate_copy

router = APIRouter()
logger = logging.getLogger(__name__)


def get_audit_session() -> Generator[Session, None, None]:
    try:
        yield from get_db_session()
    except DatabaseNotConfiguredError:
        raise HTTPException(status_code=503, detail="PostgreSQL is not configured for audit persistence.") from None


def _read(session: Session, audit: AuditRun) -> AuditRead:
    findings = session.scalars(select(AuditFinding).where(AuditFinding.audit_id == audit.id).order_by(AuditFinding.created_at, AuditFinding.id)).all()
    decisions = session.scalars(select(FindingDecision).join(AuditFinding).where(AuditFinding.audit_id == audit.id).order_by(FindingDecision.created_at)).all()
    clearance = session.scalar(select(ClearanceRecord).where(ClearanceRecord.audit_id == audit.id).order_by(ClearanceRecord.created_at.desc()).limit(1))
    return AuditRead(id=audit.id, workspace_id=audit.workspace_id, document_id=audit.document_id, content_sha256=audit.content_sha256,
        character_count=audit.character_count, approved_rules_considered=audit.approved_rules_considered,
        supported_checks_performed=audit.supported_checks_performed, rules_unevaluated=audit.rules_unevaluated,
        scope_limitations=json.loads(audit.scope_limitations), review_status=audit.review_status,
        created_at=audit.created_at, findings=findings, decisions=decisions, clearance=clearance)


@router.post("/audits", response_model=AuditRead, status_code=201)
def create_audit(payload: AuditCreate, session: Session = Depends(get_audit_session)):
    if not payload.content.strip():
        raise HTTPException(status_code=422, detail="Marketing copy must contain non-whitespace text.")
    try:
        with session.begin():
            workspace = session.get(Workspace, payload.workspace_id)
            if workspace is None or workspace.kind == "legacy":
                raise HTTPException(status_code=404, detail="Workspace was not found.")
            document = session.get(GuidelineDocument, payload.document_id) if payload.document_id else None
            if payload.document_id and (document is None or document.workspace_id != payload.workspace_id):
                raise HTTPException(status_code=404, detail="Guideline document was not found.")
            rule_query = select(CandidateRule).join(GuidelineDocument).options(joinedload(CandidateRule.document)).where(CandidateRule.review_status == "approved", GuidelineDocument.workspace_id == payload.workspace_id)
            if payload.document_id:
                rule_query = rule_query.where(CandidateRule.document_id == payload.document_id)
            rules = list(session.scalars(rule_query).unique().all())
            facts = list(session.scalars(select(ImportedFact).where(ImportedFact.workspace_id == payload.workspace_id, ImportedFact.review_status == "approved")).all())
            terms = list(session.scalars(select(ImportedTerm).where(ImportedTerm.workspace_id == payload.workspace_id, ImportedTerm.review_status == "approved")).all())
            findings, checks, unevaluated, limitations = evaluate_copy(payload.content, rules, facts, terms)
            run = AuditRun(workspace_id=payload.workspace_id, document_id=payload.document_id, content_sha256=hashlib.sha256(payload.content.encode("utf-8")).hexdigest(),
                character_count=len(payload.content), approved_rules_considered=len(rules), supported_checks_performed=checks,
                rules_unevaluated=unevaluated, scope_limitations=json.dumps(limitations), review_status="pending_review")
            session.add(run); session.flush()
            records = [AuditFinding(audit_id=run.id, **item) for item in findings]
            session.add_all(records); session.flush(); session.refresh(run)
        return _read(session, run)
    except SQLAlchemyError as exc:
        session.rollback(); logger.error("Audit persistence failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Audit results could not be persisted.") from None


@router.get("/audits/{audit_id}", response_model=AuditRead)
def get_audit(audit_id: UUID, workspace_id: UUID, session: Session = Depends(get_audit_session)):
    audit = session.scalar(select(AuditRun).where(AuditRun.id == audit_id, AuditRun.workspace_id == workspace_id))
    if audit is None: raise HTTPException(status_code=404, detail="Audit run was not found.")
    return _read(session, audit)


@router.post("/audits/{audit_id}/findings/{finding_id}/decisions", response_model=AuditRead)
def decide_finding(audit_id: UUID, finding_id: UUID, payload: FindingDecisionCreate, workspace_id: UUID, session: Session = Depends(get_audit_session)):
    try:
        with session.begin():
            audit = session.scalar(select(AuditRun).where(AuditRun.id == audit_id, AuditRun.workspace_id == workspace_id))
            finding = session.scalar(select(AuditFinding).where(AuditFinding.id == finding_id, AuditFinding.audit_id == audit_id).with_for_update())
            if audit is None or finding is None: raise HTTPException(status_code=404, detail="Audit finding was not found.")
            if finding.status in {"resolved", "dismissed"}: raise HTTPException(status_code=409, detail="Finding already has a final decision.")
            if finding.status == "informational": raise HTTPException(status_code=409, detail="Informational evidence matches do not accept finding decisions.")
            if payload.action == "accept_suggestion" and not finding.suggested_correction:
                raise HTTPException(status_code=409, detail="This finding has no supported suggested correction to accept.")
            finding.status = {"accept_suggestion": "resolved", "dismiss": "dismissed", "flag": "flagged"}[payload.action]
            session.add(FindingDecision(finding_id=finding.id, action=payload.action)); session.flush()
        return _read(session, audit)
    except SQLAlchemyError as exc:
        session.rollback(); logger.error("Finding decision failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Finding decision could not be persisted.") from None


@router.post("/audits/{audit_id}/clearance", response_model=AuditRead)
def decide_clearance(audit_id: UUID, payload: ClearanceCreate, workspace_id: UUID, session: Session = Depends(get_audit_session)):
    try:
        with session.begin():
            audit = session.scalar(select(AuditRun).where(AuditRun.id == audit_id, AuditRun.workspace_id == workspace_id).with_for_update())
            if audit is None: raise HTTPException(status_code=404, detail="Audit run was not found.")
            unresolved = session.scalar(select(AuditFinding.id).where(AuditFinding.audit_id == audit_id, AuditFinding.status.in_(["pending_review", "flagged"])).limit(1))
            if payload.decision == "cleared" and unresolved is not None:
                raise HTTPException(status_code=409, detail="Resolve or dismiss all actionable findings before clearance.")
            audit.review_status = "cleared" if payload.decision == "cleared" else "blocked"
            session.add(ClearanceRecord(audit_id=audit.id, decision=audit.review_status,
                checks_performed=audit.supported_checks_performed, content_sha256=audit.content_sha256))
            session.flush()
        return _read(session, audit)
    except SQLAlchemyError as exc:
        session.rollback(); logger.error("Clearance decision failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Clearance decision could not be persisted.") from None
