"""Persistent deterministic content audits and human review decisions."""

import hashlib
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
from collections.abc import Generator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.core.database import DatabaseNotConfiguredError, get_db_session
from app.models.audit import AuditFinding, AuditRun, ClearanceRecord, FindingDecision, RepairDecision
from app.models.guideline import CandidateRule, GuidelineDocument
from app.models.imports import ImportedFact, ImportedTerm
from app.models.workspace import Workspace
from app.schemas.audit import AmbiguityRadarRead, AuditCreate, AuditRead, AuditReportRequest, ClearanceCreate, FindingDecisionCreate, RepairDecisionCreate, RepairRead, RepairRequest, SourceEvidenceRecheckCreate
from app.services.audit_engine import evaluate_copy
from app.services.ambiguity_radar import get_workspace_ambiguity
from app.services.evidence_verification import verify_finding
from app.services.evaluation import run_evaluation
from app.services.repair_engine import build_repair_preview

router = APIRouter()
logger = logging.getLogger(__name__)


def get_audit_session() -> Generator[Session, None, None]:
    try:
        yield from get_db_session()
    except DatabaseNotConfiguredError:
        raise HTTPException(status_code=503, detail="PostgreSQL is not configured for audit persistence.") from None


@router.get("/ambiguity-radar", response_model=AmbiguityRadarRead)
def ambiguity_radar(workspace_id: UUID, session: Session = Depends(get_audit_session)):
    workspace = session.get(Workspace, workspace_id)
    if workspace is None or workspace.kind == "legacy":
        raise HTTPException(status_code=404, detail="Workspace was not found.")
    return get_workspace_ambiguity(session, workspace_id)


@router.get("/evaluation")
def labelled_evaluation():
    """Run the checked-in synthetic benchmark in an isolated in-memory database."""
    try:
        return run_evaluation()
    except Exception as exc:
        logger.error("Labelled evaluation failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Labelled evaluation could not be completed.") from None


def _read(session: Session, audit: AuditRun) -> AuditRead:
    findings = session.scalars(select(AuditFinding).where(AuditFinding.audit_id == audit.id).order_by(AuditFinding.created_at, AuditFinding.id)).all()
    decisions = session.scalars(select(FindingDecision).join(AuditFinding).where(AuditFinding.audit_id == audit.id).order_by(FindingDecision.created_at)).all()
    repair_decisions = session.scalars(select(RepairDecision).join(AuditFinding).where(AuditFinding.audit_id == audit.id).order_by(RepairDecision.created_at, RepairDecision.id)).all()
    clearance = session.scalar(select(ClearanceRecord).where(ClearanceRecord.audit_id == audit.id).order_by(ClearanceRecord.created_at.desc()).limit(1))
    return AuditRead(id=audit.id, workspace_id=audit.workspace_id, document_id=audit.document_id, content_sha256=audit.content_sha256,
        character_count=audit.character_count, approved_rules_considered=audit.approved_rules_considered,
        supported_checks_performed=audit.supported_checks_performed, rules_unevaluated=audit.rules_unevaluated,
        scope_limitations=json.loads(audit.scope_limitations), review_status=audit.review_status,
        created_at=audit.created_at, findings=findings, decisions=decisions, repair_decisions=repair_decisions, clearance=clearance)


@router.post("/audits", response_model=AuditRead, status_code=201)
def create_audit(payload: AuditCreate, response: Response, session: Session = Depends(get_audit_session)):
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
            def approved_rules(document_id):
                query = select(CandidateRule).join(GuidelineDocument).options(joinedload(CandidateRule.document)).where(
                    CandidateRule.review_status == "approved",
                    GuidelineDocument.workspace_id == payload.workspace_id,
                    CandidateRule.document_id == document_id,
                )
                return list(session.scalars(query).unique().all())

            rules = approved_rules(document.id) if document else list(session.scalars(
                select(CandidateRule).join(GuidelineDocument).options(joinedload(CandidateRule.document)).where(
                    CandidateRule.review_status == "approved", GuidelineDocument.workspace_id == payload.workspace_id
                )
            ).unique().all())
            # A refreshed extraction remains pending human review. Until it has
            # approved rules, use the nearest prior revision with approved rules.
            effective_document = document
            limitations_note = None
            if document and not rules and document.supersedes_document_id:
                cursor = document
                while cursor.supersedes_document_id:
                    parent = session.get(GuidelineDocument, cursor.supersedes_document_id)
                    if parent is None or parent.workspace_id != payload.workspace_id:
                        break
                    parent_rules = approved_rules(parent.id)
                    if parent_rules:
                        effective_document, rules = parent, parent_rules
                        limitations_note = "The refreshed guideline revision is still in human review; audit checks use the nearest prior revision with approved rules."
                        break
                    cursor = parent
            content_sha256 = hashlib.sha256(payload.content.encode("utf-8")).hexdigest()
            existing = None
            if payload.document_id and effective_document and effective_document.id != payload.document_id:
                existing = session.scalar(select(AuditRun).where(
                    AuditRun.workspace_id == payload.workspace_id,
                    AuditRun.document_id == effective_document.id,
                    AuditRun.content_sha256 == content_sha256,
                ).order_by(AuditRun.created_at, AuditRun.id).limit(1))
            if existing is not None:
                response.status_code = 200
                return _read(session, existing)
            facts = list(session.scalars(select(ImportedFact).where(ImportedFact.workspace_id == payload.workspace_id, ImportedFact.review_status == "approved")).all())
            terms = list(session.scalars(select(ImportedTerm).where(ImportedTerm.workspace_id == payload.workspace_id, ImportedTerm.review_status == "approved")).all())
            findings, checks, unevaluated, limitations = evaluate_copy(payload.content, rules, facts, terms)
            if limitations_note:
                limitations.append(limitations_note)
            findings = [{**finding, **{
                "verification_status": outcome.status,
                "verification_reason": outcome.reason_code,
                "verification_explanation": outcome.explanation,
            }} for finding in findings for outcome in [verify_finding(session, finding, payload.content, payload.workspace_id)]]
            run = AuditRun(workspace_id=payload.workspace_id, document_id=effective_document.id if effective_document else None, content_sha256=content_sha256,
                character_count=len(payload.content), approved_rules_considered=len(rules), supported_checks_performed=checks,
                rules_unevaluated=unevaluated, scope_limitations=json.dumps(limitations), review_status="pending_review")
            session.add(run); session.flush()
            records = [AuditFinding(audit_id=run.id, **item) for item in findings]
            session.add_all(records); session.flush(); session.refresh(run)
        return _read(session, run)
    except SQLAlchemyError as exc:
        session.rollback(); logger.error("Audit persistence failed (%s) sqlstate=%s", type(exc).__name__, getattr(getattr(exc, "orig", None), "sqlstate", None) or "unknown")
        raise HTTPException(status_code=503, detail="Audit results could not be persisted.") from None


@router.get("/audits/{audit_id}", response_model=AuditRead)
def get_audit(audit_id: UUID, workspace_id: UUID, session: Session = Depends(get_audit_session)):
    audit = session.scalar(select(AuditRun).where(AuditRun.id == audit_id, AuditRun.workspace_id == workspace_id))
    if audit is None: raise HTTPException(status_code=404, detail="Audit run was not found.")
    return _read(session, audit)


@router.post("/audits/{audit_id}/verify-source-evidence", response_model=AuditRead)
def verify_source_evidence(audit_id: UUID, payload: SourceEvidenceRecheckCreate, workspace_id: UUID, session: Session = Depends(get_audit_session)):
    audit = session.scalar(select(AuditRun).where(AuditRun.id == audit_id, AuditRun.workspace_id == workspace_id))
    if audit is None:
        raise HTTPException(status_code=404, detail="Audit run was not found.")
    if hashlib.sha256(payload.content.encode("utf-8")).hexdigest() != audit.content_sha256:
        raise HTTPException(status_code=409, detail="The submitted content does not match the persisted audit.")
    findings = session.scalars(select(AuditFinding).where(AuditFinding.audit_id == audit.id)).all()
    for finding in findings:
        outcome = verify_finding(session, {
            "rule_id": finding.rule_id, "fact_id": finding.fact_id, "term_id": finding.term_id,
            "source_document_id": finding.source_document_id, "source_document_sha256": finding.source_document_sha256,
            "matched_phrase": finding.matched_phrase, "match_start": finding.match_start, "match_end": finding.match_end,
            "suggested_correction": finding.suggested_correction, "evidence_excerpt": finding.evidence_excerpt,
            "source_filename": finding.source_filename, "source_page": finding.source_page,
            "source_start_offset": finding.source_start_offset, "source_end_offset": finding.source_end_offset,
            "explanation": finding.explanation,
        }, payload.content, workspace_id)
        finding.verification_status = outcome.status
        finding.verification_reason = outcome.reason_code
        finding.verification_explanation = outcome.explanation
    session.commit()
    return _read(session, audit)


@router.post("/audits/{audit_id}/repair", response_model=RepairRead)
def preview_audit_repair(audit_id: UUID, payload: RepairRequest, workspace_id: UUID, session: Session = Depends(get_audit_session)):
    audit = session.scalar(select(AuditRun).where(AuditRun.id == audit_id, AuditRun.workspace_id == workspace_id))
    if audit is None:
        raise HTTPException(status_code=404, detail="Audit run was not found.")
    if hashlib.sha256(payload.content.encode("utf-8")).hexdigest() != audit.content_sha256:
        raise HTTPException(status_code=409, detail="The submitted content changed; run a new audit before previewing a repair.")
    findings = session.scalars(select(AuditFinding).where(AuditFinding.audit_id == audit.id).order_by(AuditFinding.match_start, AuditFinding.id)).all()
    open_findings = [finding for finding in findings if finding.status in {"pending_review", "flagged"}]
    prior_repairs = session.scalars(
        select(RepairDecision)
        .where(RepairDecision.finding_id.in_([finding.id for finding in open_findings]))
        .order_by(RepairDecision.created_at.desc(), RepairDecision.id.desc())
    ).all() if open_findings else []
    latest_repair_action = {}
    for decision in prior_repairs:
        latest_repair_action.setdefault(decision.finding_id, decision.action)
    available_findings = [finding for finding in open_findings if latest_repair_action.get(finding.id) != "reject"]
    if not findings:
        status = "no_findings"
    elif not open_findings:
        status = "no_open_findings"
    else:
        status = "review_required"
    try:
        repaired, replacements = build_repair_preview(session, payload.content, workspace_id, available_findings)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if replacements:
        status = "preview_available"
    elif findings and not open_findings:
        status = "no_open_findings"
    elif available_findings:
        status = "no_supported_repairs"
    elif open_findings:
        status = "no_supported_repairs"
    return RepairRead(
        audit_id=audit.id, original_sha256=audit.content_sha256, status=status,
        findings_reviewed=len([finding for finding in findings if finding.status != "informational"]),
        repaired_content=repaired, replacements=replacements,
        checks_before=audit.supported_checks_performed, checks_after=audit.supported_checks_performed,
        findings_before=len(findings), findings_after=len(findings) - len(replacements),
        limitations=["Repair is a preview only; the submitted copy is not modified or persisted."])


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
            if payload.action == "accept_suggestion" and hashlib.sha256(payload.content.encode("utf-8")).hexdigest() != audit.content_sha256:
                raise HTTPException(status_code=409, detail="The submitted content does not match the persisted audit.")
            finding.status = {"accept_suggestion": "resolved", "dismiss": "dismissed", "flag": "flagged"}[payload.action]
            session.add(FindingDecision(finding_id=finding.id, action=payload.action, review_reason=payload.reason)); session.flush()
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


REPORT_LOGO = Path(__file__).resolve().parents[4] / "apps" / "web" / "public" / "mint_proofmark_logo.png"

@router.post("/audits/{audit_id}/report")
def generate_audit_report(audit_id: UUID, workspace_id: UUID, payload: AuditReportRequest, session: Session = Depends(get_audit_session)):
    """Export current persisted audit data with mandatory Proofmint watermarks."""
    try:
        audit = session.scalar(select(AuditRun).where(AuditRun.id == audit_id, AuditRun.workspace_id == workspace_id))
        if audit is None:
            raise HTTPException(status_code=404, detail="Audit run was not found.")
        findings = session.scalars(select(AuditFinding).where(AuditFinding.audit_id == audit.id).order_by(AuditFinding.created_at, AuditFinding.id)).all()
        decisions = session.scalars(select(FindingDecision).join(AuditFinding).where(AuditFinding.audit_id == audit.id).order_by(FindingDecision.created_at)).all()
        repair_decisions = session.scalars(select(RepairDecision).join(AuditFinding).where(AuditFinding.audit_id == audit.id).order_by(RepairDecision.created_at, RepairDecision.id)).all()
        clearance = session.scalar(select(ClearanceRecord).where(ClearanceRecord.audit_id == audit.id).order_by(ClearanceRecord.created_at.desc()).limit(1))
        document_ids = {audit.document_id} if audit.document_id else set()
        document_ids.update(f.source_document_id for f in findings if f.source_document_id is not None)
        documents = session.scalars(select(GuidelineDocument).where(
            GuidelineDocument.workspace_id == audit.workspace_id,
            GuidelineDocument.id.in_(document_ids),
        )).all() if document_ids else []
        documents_by_id = {item.id: item for item in documents}
        document = documents_by_id.get(audit.document_id)
        rule_ids = {finding.rule_id for finding in findings if finding.rule_id is not None}
        rules = session.scalars(select(CandidateRule).where(
            CandidateRule.id.in_(rule_ids), CandidateRule.document_id.in_(documents_by_id.keys())
        )).all() if rule_ids and documents_by_id else []
        rules_by_id = {rule.id: rule for rule in rules}
        fact_ids = {f.fact_id for f in findings if f.fact_id is not None}
        facts = session.scalars(select(ImportedFact).where(
            ImportedFact.id.in_(fact_ids), ImportedFact.workspace_id == audit.workspace_id
        )).all() if fact_ids else []
        facts_by_id = {item.id: item for item in facts}
        term_ids = {f.term_id for f in findings if f.term_id is not None}
        terms = session.scalars(select(ImportedTerm).where(
            ImportedTerm.id.in_(term_ids), ImportedTerm.workspace_id == audit.workspace_id
        )).all() if term_ids else []
        terms_by_id = {item.id: item for item in terms}
        data = _generate_pdf_report(audit, findings, decisions, clearance, document, rules_by_id, documents_by_id, facts_by_id, terms_by_id, repair_decisions=repair_decisions) if payload.format == "pdf" else _generate_docx_report(audit, findings, decisions, clearance, document, rules_by_id, documents_by_id, facts_by_id, terms_by_id, repair_decisions=repair_decisions)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("Report data read failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Audit report data could not be read.") from None
    except Exception as exc:
        logger.error("Report generation failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Audit report could not be generated.") from None
    ext = payload.format
    media_type = "application/pdf" if ext == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(data, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="proofmint_report.{ext}"'})


def _report_decisions(decisions):
    grouped = {}
    for decision in decisions:
        grouped.setdefault(decision.finding_id, []).append(decision)
    return grouped


def _report_text(value) -> str:
    return value if value not in (None, "") else "Not recorded"


def _report_finding_source(finding, rules_by_id, documents_by_id) -> str:
    source_document = (documents_by_id or {}).get(finding.source_document_id)
    rule = (rules_by_id or {}).get(finding.rule_id)
    parts = [
        f"Rule ID: {_report_text(finding.rule_id)}",
        f"Rule text: {_report_text(rule.rule_text if rule else None)}",
        f"Rule review state: {_report_text(rule.review_status if rule else None)}",
        f"Rule source excerpt: {_report_text(rule.source_excerpt if rule else None)}",
    ]
    parts.extend([
        f"Source document: {_report_text(finding.source_filename or (source_document.source_filename if source_document else None))}",
        f"Source document ID: {_report_text(finding.source_document_id)}",
        f"Source SHA-256: {_report_text(finding.source_document_sha256 or (source_document.source_sha256 if source_document else None))}",
        f"Rule-set revision: {_report_text(source_document.extraction_revision if source_document else None)}",
        f"Source page: {_report_text(finding.source_page)}",
        f"Source characters: {_report_text(finding.source_start_offset)}–{_report_text(finding.source_end_offset)}",
    ])
    return "; ".join(parts)


def _report_finding_evidence(finding, facts_by_id, terms_by_id) -> str:
    details = [f"Evidence excerpt: {_report_text(finding.evidence_excerpt)}"]
    fact = (facts_by_id or {}).get(finding.fact_id)
    term = (terms_by_id or {}).get(finding.term_id)
    if finding.fact_id:
        details.append(f"Persisted fact: {_report_text(fact.approved_statement if fact else None)}; review state: {_report_text(fact.review_status if fact else None)}")
    if finding.term_id:
        details.append(f"Persisted term: {_report_text(term.term if term else None)}; preferred form: {_report_text(term.preferred_form if term else None)}; review state: {_report_text(term.review_status if term else None)}")
    return "; ".join(details)


def _generate_pdf_report(audit, findings, decisions, clearance, document, rules_by_id=None, documents_by_id=None, facts_by_id=None, terms_by_id=None, repair_decisions=None) -> bytes:
    from PIL import Image as PILImage
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    if not REPORT_LOGO.is_file():
        raise RuntimeError("Official Proofmint logo asset is unavailable")
    output = BytesIO()
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontSize = 8
    body.leading = 10
    story = [Paragraph("Proofmint Audit Decision Report", styles["Title"]), Spacer(1, 12)]
    labels = [
        ("Workspace ID", audit.workspace_id), ("Audit ID", audit.id),
        ("Report generated", datetime.now(timezone.utc).isoformat()),
        ("Original audit timestamp", audit.created_at.isoformat() if audit.created_at else None),
        ("Audited content SHA-256", audit.content_sha256),
        ("Guideline document", f"{document.source_filename} · ID {document.id} · SHA-256 {document.source_sha256}" if document else None),
        ("Rule-set revision", document.extraction_revision if document else None),
        ("Persisted finding count", len(findings)),
        ("Finding counts by persisted state", ", ".join(f"{status}: {count}" for status, count in sorted(Counter(f.status for f in findings).items())) or "No findings recorded"),
        ("Final clearance", clearance.decision if clearance else None),
        ("Clearance timestamp", clearance.created_at.isoformat() if clearance and clearance.created_at else None),
        ("Authorized actor", None), ("Review status", audit.review_status),
        ("Limitations", "; ".join(json.loads(audit.scope_limitations)) or "Not recorded"),
        ("Repair preview", "Not recorded; repair previews are not persisted with this audit"),
    ]
    metadata = [[Paragraph(f"<b>{escape(str(label))}</b>", body), Paragraph(escape(str(_report_text(value))), body)] for label, value in labels]
    story.append(Table(metadata, colWidths=[1.65 * inch, 4.75 * inch], repeatRows=0, style=TableStyle([
        ("GRID", (0, 0), (-1, -1), .35, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf5f0")), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])))
    story.extend([Spacer(1, 12), Paragraph("Findings", styles["Heading2"])])
    grouped = _report_decisions(decisions)
    if not findings:
        story.append(Paragraph("No findings recorded.", body))
    for index, finding in enumerate(findings, start=1):
        story.append(Paragraph(f"Finding {index} · {escape(finding.status)} / {escape(finding.finding_type)}", styles["Heading3"]))
        fields = [
            ("Flagged text span", f"Copy characters {finding.match_start}–{finding.match_end}: {finding.matched_phrase}"),
            ("Applicable rule and source", _report_finding_source(finding, rules_by_id, documents_by_id)),
            ("Evidence verification", f"Status: {_report_text(finding.verification_status)}; reason: {_report_text(finding.verification_reason)}; explanation: {_report_text(finding.verification_explanation)}"),
            ("Evidence details", _report_finding_evidence(finding, facts_by_id, terms_by_id)),
            ("Human review decision", "; ".join(f"{d.action}; reason: {_report_text(d.review_reason)}; actor: Not recorded; timestamp: {d.created_at.isoformat() if d.created_at else 'Not recorded'}" for d in grouped.get(finding.id, [])) or "Not recorded"),
            ("Suggested correction", f"{_report_text(finding.suggested_correction)}; accepted correction content: Not recorded"),
        ]
        cells = [[Paragraph(f"<b>{escape(label)}</b>", body), Paragraph(escape(str(value)), body)] for label, value in fields]
        story.append(Table(cells, colWidths=[1.5 * inch, 4.9 * inch], style=TableStyle([
            ("GRID", (0, 0), (-1, -1), .3, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])))
        story.append(Spacer(1, 8))
    story.extend([
        Paragraph("Interpretation and limitations", styles["Heading2"]),
        Paragraph("A dismissed finding is not necessarily factually disproven. Human review is not independent evidence verification. Suggested corrections are proposals; no corrected content is recorded here as accepted. No clearance is claimed without a persisted clearance record. The current schema does not record reviewer or clearance actor identity.", body),
    ])

    def watermark(canvas: Canvas, _doc):
        canvas.saveState()
        with PILImage.open(REPORT_LOGO) as logo:
            image = logo.convert("RGBA")
            width = 0.9 * inch
            height = width * image.height / image.width
            canvas.setFillAlpha(.16)
            canvas.drawImage(ImageReader(image), letter[0] - width - .35 * inch, .35 * inch, width, height, mask="auto", preserveAspectRatio=True)
        canvas.saveState()
        canvas.setFillAlpha(.08)
        canvas.setFillColor(colors.HexColor("#4f8770"))
        canvas.setFont("Helvetica-Bold", 40)
        canvas.translate(letter[0] / 2, letter[1] / 2)
        canvas.rotate(35)
        canvas.drawCentredString(0, 0, "PROOFMINT")
        canvas.restoreState()
        canvas.restoreState()

    SimpleDocTemplate(output, pagesize=letter, leftMargin=.55 * inch, rightMargin=.55 * inch).build(story, onFirstPage=watermark, onLaterPages=watermark)
    return output.getvalue()


def _generate_docx_report(audit, findings, decisions, clearance, document, rules_by_id=None, documents_by_id=None, facts_by_id=None, terms_by_id=None, repair_decisions=None) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import parse_xml
    from docx.shared import Inches, RGBColor

    if not REPORT_LOGO.is_file():
        raise RuntimeError("Official Proofmint logo asset is unavailable")
    report = Document()
    section = report.sections[0]
    header = section.header
    para = header.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    mark = para.add_run("PROOFMINT")
    mark.bold = True
    mark.font.color.rgb = RGBColor(0xA7, 0xF3, 0xD0)
    logo_run = para.add_run()
    logo_run.add_picture(str(REPORT_LOGO), width=Inches(.9))
    # python-docx's nsdecls() map has no VML (`v`) or Office (`o`) prefixes.
    # Declare those namespaces on the pict element so Word keeps the watermark.
    watermark_xml = (
        '<w:pict xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:o="urn:schemas-microsoft-com:office:office">'
        '<v:shapetype id="_x0000_t136" coordsize="1600,21600" o:spt="136" adj="10800" '
        'path="m@7,l@8,m@5,21600l@6,21600e">'
        '<v:formulas><v:f eqn="sum #0 0 10800"/><v:f eqn="prod #0 2 1"/><v:f eqn="sum 21600 0 @1"/>'
        '<v:f eqn="sum 0 0 @2"/><v:f eqn="sum 21600 0 @3"/><v:f eqn="if @0 @3 0"/><v:f eqn="if @0 21600 @1"/>'
        '<v:f eqn="if @0 0 @2"/><v:f eqn="if @0 @4 21600"/><v:f eqn="mid @5 @6"/><v:f eqn="mid @8 @5"/>'
        '</v:formulas><v:path textpathok="t"/><v:textpath on="t" fitshape="t"/>'
        '<v:handles><v:h position="#0,bottomRight" xrange="6629,14971"/></v:handles>'
        '<o:lock v:ext="edit" text="t" shapetype="t"/></v:shapetype>'
        '<v:shape id="ProofmintTextWatermark" type="#_x0000_t136" '
        'style="position:absolute;margin-left:0;margin-top:220pt;width:420pt;height:80pt;rotation:-35;z-index:-251654144;'
        'mso-position-horizontal:center;mso-position-horizontal-relative:margin;'
        'mso-position-vertical:center;mso-position-vertical-relative:margin" '
        'stroked="f" fillcolor="#A7F3D0"><v:fill opacity=".18"/><v:textpath '
        'style="font-family:Arial;font-size:1pt;font-weight:bold" string="PROOFMINT"/></v:shape>'
        '</w:pict>'
    )


@router.post("/audits/{audit_id}/findings/{finding_id}/repair-decisions", response_model=AuditRead)
def decide_repair(audit_id: UUID, finding_id: UUID, payload: RepairDecisionCreate, workspace_id: UUID, session: Session = Depends(get_audit_session)):
    """Persist an append-only repair decision for a currently supported proposal."""
    try:
        with session.begin():
            audit = session.scalar(select(AuditRun).where(AuditRun.id == audit_id, AuditRun.workspace_id == workspace_id).with_for_update())
            finding = session.scalar(select(AuditFinding).where(AuditFinding.id == finding_id, AuditFinding.audit_id == audit_id).with_for_update())
            if audit is None or finding is None:
                raise HTTPException(status_code=404, detail="Audit repair proposal was not found.")
            if hashlib.sha256(payload.content.encode("utf-8")).hexdigest() != audit.content_sha256:
                raise HTTPException(status_code=409, detail="The submitted content does not match the persisted audit.")
            if finding.status not in {"pending_review", "flagged"}:
                raise HTTPException(status_code=409, detail="This finding is not eligible for a repair decision.")
            latest = session.scalar(
                select(RepairDecision)
                .where(RepairDecision.finding_id == finding.id)
                .order_by(RepairDecision.created_at.desc(), RepairDecision.id.desc())
                .limit(1)
            )
            if latest and latest.action == "reject":
                raise HTTPException(status_code=409, detail="This repair proposal was already rejected and cannot be reopened.")
            try:
                _repaired, replacements = build_repair_preview(session, payload.content, workspace_id, [finding])
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from None
            supported = next((item for item in replacements if item["finding_id"] == finding.id), None)
            if supported is None:
                raise HTTPException(status_code=409, detail="No currently supported repair proposal exists for this finding.")
            if payload.action == "accept" and payload.replacement != supported["replacement"]:
                raise HTTPException(status_code=409, detail="Accept must use the currently supported replacement text.")
            session.add(RepairDecision(
                finding_id=finding.id,
                action=payload.action,
                proposed_replacement=payload.replacement,
                review_reason=payload.reason,
            ))
            session.flush()
        return _read(session, audit)
    except SQLAlchemyError as exc:
        session.rollback(); logger.error("Repair decision failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Repair decision could not be persisted.") from None
    vml_run = para.add_run()
    vml_run._r.append(parse_xml(watermark_xml))
    report.add_heading("Audit Decision Report", 0)
    states = Counter(f.status for f in findings)
    for label, value in [("Workspace ID", audit.workspace_id), ("Audit ID", audit.id), ("Generated", datetime.now(timezone.utc).isoformat()), ("Original audit timestamp", audit.created_at.isoformat() if audit.created_at else "Not recorded"), ("Audited content SHA-256", audit.content_sha256), ("Guideline document", f"{document.source_filename} · ID {document.id} · SHA-256 {document.source_sha256}" if document else "Not recorded"), ("Rule-set revision", document.extraction_revision if document else "Not recorded"), ("Finding count", len(findings)), ("Finding counts by state", ", ".join(f"{status}: {count}" for status, count in sorted(states.items())) or "No findings recorded"), ("Review status", audit.review_status), ("Final clearance", clearance.decision if clearance else "Not recorded"), ("Clearance timestamp", clearance.created_at.isoformat() if clearance and clearance.created_at else "Not recorded"), ("Authorized actor", "Not recorded"), ("Repair preview", "Not recorded; repair previews are not persisted with this audit"), ("Limitations", "; ".join(json.loads(audit.scope_limitations)) or "Not recorded")]:
        report.add_paragraph(f"{label}: {value}")
    report.add_heading("Findings", level=1)
    table = report.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    for cell, text_value in zip(table.rows[0].cells, ["Status/type", "Flagged text", "Rule/source", "Verification", "Decision/reason"]):
        cell.text = text_value
    grouped = _report_decisions(decisions)
    if not findings:
        row = table.add_row().cells
        for cell, text_value in zip(row, ["Not recorded", "No findings recorded", "Not recorded", "Not recorded", "Not recorded"]): cell.text = text_value
    for finding in findings:
        ds = grouped.get(finding.id, [])
        rule = (rules_by_id or {}).get(finding.rule_id)
        values = [f"{finding.status} / {finding.finding_type}", f"Copy characters {finding.match_start}–{finding.match_end}: {finding.matched_phrase or 'Not recorded'}", _report_finding_source(finding, rules_by_id, documents_by_id), f"Status: {_report_text(finding.verification_status)}; reason: {_report_text(finding.verification_reason)}; explanation: {_report_text(finding.verification_explanation)}", "; ".join(f"{d.action}; reason: {_report_text(d.review_reason)}; actor: Not recorded; timestamp: {d.created_at.isoformat() if d.created_at else 'Not recorded'}" for d in ds) or "Not recorded"]
        for cell, value in zip(table.add_row().cells, values): cell.text = str(value)
        report.add_paragraph(f"Finding explanation: {_report_text(finding.explanation)}")
        report.add_paragraph(_report_finding_evidence(finding, facts_by_id, terms_by_id))
        report.add_paragraph(f"Suggested correction: {_report_text(finding.suggested_correction)}; accepted correction content: Not recorded")
    report.add_heading("Interpretation and limitations", level=1)
    report.add_paragraph("A dismissed finding is not necessarily factually disproven. Human review is not independent evidence verification. Suggested corrections are proposals; no corrected content is recorded here as accepted. No clearance is claimed without a persisted clearance record. The current schema does not record reviewer or clearance actor identity.")
    output = BytesIO()
    report.save(output)
    return output.getvalue()


# Customer-facing report generators. These definitions intentionally remain close
# to the legacy helpers above so the endpoint contract and persisted-data lookup
# stay unchanged while the rendered documents use a readable narrative layout.
def _customer_value(value):
    return str(value) if value not in (None, "") else None


def _customer_finding_lines(finding, decisions, rules_by_id, documents_by_id, facts_by_id, terms_by_id, repair_decisions=None):
    rule = (rules_by_id or {}).get(finding.rule_id)
    source = (documents_by_id or {}).get(finding.source_document_id)
    lines = [
        ("Flagged phrase", f"{finding.matched_phrase or 'Unavailable'} · characters {finding.match_start}–{finding.match_end}"),
        ("Finding status", finding.status),
        ("Finding type", finding.finding_type),
    ]
    if rule:
        lines.append(("Applicable guideline", rule.rule_text))
        lines.append(("Guideline source", f"{source.source_filename if source else finding.source_filename or 'Unavailable'} · page {finding.source_page or 'Unavailable'}"))
    elif finding.source_filename or finding.source_page:
        lines.append(("Guideline source", f"{finding.source_filename or 'Unavailable'} · page {finding.source_page or 'Unavailable'}"))
    if finding.evidence_excerpt:
        lines.append(("Supporting evidence", finding.evidence_excerpt))
    lines.append(("Why it was flagged", finding.explanation))
    if finding.verification_status:
        verification = finding.verification_status
        if finding.verification_reason:
            verification += f" · {finding.verification_reason}"
        lines.append(("Evidence verification", verification))
    if finding.suggested_correction:
        lines.append(("Suggested correction", finding.suggested_correction))
    fact = (facts_by_id or {}).get(finding.fact_id)
    term = (terms_by_id or {}).get(finding.term_id)
    if fact:
        lines.append(("Associated approved fact", f"{fact.approved_statement} · review: {fact.review_status}"))
    if term:
        lines.append(("Associated terminology", f"{term.term}{f' → {term.preferred_form}' if term.preferred_form else ''} · review: {term.review_status}"))
    finding_decisions = [decision for decision in decisions if decision.finding_id == finding.id]
    if finding_decisions:
        lines.append(("Persisted review decision", " · ".join(f"{decision.action}{f' ({decision.review_reason})' if decision.review_reason else ''}" for decision in finding_decisions)))
    finding_repairs = [decision for decision in (repair_decisions or []) if decision.finding_id == finding.id]
    if finding_repairs:
        lines.append(("Persisted repair decisions", " · ".join(
            f"{decision.action}{f': {decision.proposed_replacement}' if decision.proposed_replacement else ''}{f' ({decision.review_reason})' if decision.review_reason else ''}"
            for decision in finding_repairs
        )))
    return lines


def _customer_summary(audit, findings, clearance):
    counts = Counter(f.status for f in findings)
    pending = counts.get("pending_review", 0) + counts.get("flagged", 0)
    if clearance:
        outcome = f"Clearance recorded as {clearance.decision}."
    elif pending:
        outcome = f"{pending} finding{'s' if pending != 1 else ''} require human review before clearance."
    else:
        outcome = "No persisted clearance decision is recorded for this audit."
    return outcome, counts


def _generate_pdf_report(audit, findings, decisions, clearance, document, rules_by_id=None, documents_by_id=None, facts_by_id=None, terms_by_id=None, repair_decisions=None) -> bytes:
    from PIL import Image as PILImage
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    if not REPORT_LOGO.is_file():
        raise RuntimeError("Official Proofmint logo asset is unavailable")
    output = BytesIO()
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ProofmintTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=colors.HexColor("#24483d"), spaceAfter=5)
    subtitle = ParagraphStyle("ProofmintSubtitle", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#5f6f68"), spaceAfter=14)
    heading = ParagraphStyle("ProofmintHeading", parent=styles["Heading2"], fontSize=14, leading=17, textColor=colors.HexColor("#24483d"), spaceBefore=12, spaceAfter=7)
    finding_heading = ParagraphStyle("ProofmintFinding", parent=styles["Heading3"], fontSize=11, leading=14, textColor=colors.HexColor("#24483d"), spaceBefore=8, spaceAfter=5)
    body = ParagraphStyle("ProofmintBody", parent=styles["BodyText"], fontSize=9, leading=12, textColor=colors.HexColor("#28332f"), spaceAfter=5)
    small = ParagraphStyle("ProofmintSmall", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#5f6f68"))
    esc = lambda value: escape(str(value)).replace("\n", "<br/>")
    outcome, counts = _customer_summary(audit, findings, clearance)
    story = [Paragraph("Proofmint Audit Decision Report", title), Paragraph("Audit decision report", subtitle)]
    summary_rows = [
        [Paragraph("Audit outcome", body), Paragraph(esc(outcome), body)],
        [Paragraph("Findings requiring review", body), Paragraph(str(counts.get("pending_review", 0) + counts.get("flagged", 0)), body)],
        [Paragraph("Total findings", body), Paragraph(str(len(findings)), body)],
        [Paragraph("Review status", body), Paragraph(esc(audit.review_status), body)],
        [Paragraph("Persisted review decisions", body), Paragraph(esc(", ".join(sorted({"dismissed" if decision.action == "dismiss" else decision.action for decision in decisions})) or "None recorded"), body)],
        [Paragraph("Flagged phrases", body), Paragraph(esc(", ".join(f.matched_phrase for f in findings if f.matched_phrase) or "None recorded"), body)],
    ]
    if clearance:
        summary_rows.append([Paragraph("Clearance", body), Paragraph(esc(clearance.decision), body)])
    story += [Table(summary_rows, colWidths=[2.0 * inch, 4.3 * inch], style=TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eaf4ef")), ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#b8d5c8")), ("INNERGRID", (0, 0), (-1, -1), .25, colors.HexColor("#d5e4dc")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)])), Spacer(1, 12), Paragraph("Executive summary", heading), Paragraph(esc(outcome) + " Findings below reflect persisted audit records. A literal phrase match is not independent evidence verification; verification status is shown only when recorded by the audit.", body)]
    story.append(Paragraph("Detailed findings", heading))
    if not findings:
        story.append(Paragraph("No findings were recorded for this audit.", body))
    for index, finding in enumerate(findings, 1):
        cells = [[Paragraph(f"<b>{escape(label)}</b>", body), Paragraph(esc(value), body)] for label, value in _customer_finding_lines(finding, decisions, rules_by_id, documents_by_id, facts_by_id, terms_by_id, repair_decisions)]
        story.append(KeepTogether([Paragraph(f"Finding {index} · {escape(finding.finding_type)}", finding_heading), Table(cells, colWidths=[1.65 * inch, 4.65 * inch], repeatRows=0, style=TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f6f3")), ("BOX", (0, 0), (-1, -1), .35, colors.HexColor("#c8d8d0")), ("INNERGRID", (0, 0), (-1, -1), .2, colors.HexColor("#e0e9e4")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)])), Spacer(1, 7)]))
    story += [Paragraph("Review status and traceability", heading), Paragraph(esc(outcome) + " Optional technical identifiers are retained below for traceability and are not repeated in the finding narrative.", body)]
    metadata = [[Paragraph("Audit ID", small), Paragraph(esc(audit.id), small)], [Paragraph("Workspace ID", small), Paragraph(esc(audit.workspace_id), small)], [Paragraph("Content SHA-256", small), Paragraph(esc(audit.content_sha256), small)]]
    if document:
        metadata += [[Paragraph("Guideline source", small), Paragraph(esc(document.source_filename), small)], [Paragraph("Guideline SHA-256", small), Paragraph(esc(document.source_sha256), small)], [Paragraph("Rule-set revision", small), Paragraph(str(document.extraction_revision), small)]]
    story += [Table(metadata, colWidths=[1.65 * inch, 4.65 * inch], style=TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f7f9f7")), ("BOX", (0, 0), (-1, -1), .3, colors.HexColor("#d4ded8")), ("INNERGRID", (0, 0), (-1, -1), .2, colors.HexColor("#e5ebe7")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))]

    def decorate(canvas: Canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#5b8f7b")); canvas.setFillAlpha(.08); canvas.setFont("Helvetica-Bold", 38); canvas.translate(letter[0] / 2, letter[1] / 2); canvas.rotate(35); canvas.drawCentredString(0, 0, "PROOFMINT"); canvas.restoreState()
        with PILImage.open(REPORT_LOGO) as logo:
            image = logo.convert("RGBA"); width = .55 * inch; height = width * image.height / image.width
            canvas.saveState(); canvas.setFillAlpha(.2); canvas.drawImage(ImageReader(image), letter[0] - width - .45 * inch, .35 * inch, width, height, mask="auto", preserveAspectRatio=True); canvas.restoreState()
        canvas.saveState(); canvas.setFillColor(colors.HexColor("#6c7d75")); canvas.setFont("Helvetica", 8); canvas.drawString(.55 * inch, .3 * inch, "Proofmint · Nothing ships unproven."); canvas.drawRightString(letter[0] - .55 * inch, .3 * inch, f"Page {doc.page}"); canvas.restoreState()

    SimpleDocTemplate(output, pagesize=letter, leftMargin=.62 * inch, rightMargin=.62 * inch, topMargin=.62 * inch, bottomMargin=.55 * inch).build(story, onFirstPage=decorate, onLaterPages=decorate)
    return output.getvalue()


def _generate_docx_report(audit, findings, decisions, clearance, document, rules_by_id=None, documents_by_id=None, facts_by_id=None, terms_by_id=None, repair_decisions=None) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    if not REPORT_LOGO.is_file():
        raise RuntimeError("Official Proofmint logo asset is unavailable")
    report = Document(); section = report.sections[0]; section.top_margin = Inches(.65); section.bottom_margin = Inches(.65); section.left_margin = Inches(.7); section.right_margin = Inches(.7)
    normal = report.styles["Normal"]; normal.font.name = "Aptos"; normal.font.size = Pt(9); normal.font.color.rgb = RGBColor(0x28, 0x33, 0x2F)
    header = section.header; header_para = header.paragraphs[0]; header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT; run = header_para.add_run(); run.add_picture(str(REPORT_LOGO), width=Inches(.45)); mark = header_para.add_run("  PROOFMINT"); mark.bold = True; mark.font.color.rgb = RGBColor(0x4F, 0x87, 0x70)
    # Keep the mandatory editable VML watermark in the header.
    watermark_xml = '<w:pict xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><v:shape id="ProofmintTextWatermark" type="#_x0000_t136" style="position:absolute;margin-left:0;margin-top:220pt;width:420pt;height:80pt;rotation:-35;z-index:-251654144;mso-position-horizontal:center;mso-position-horizontal-relative:margin;mso-position-vertical:center;mso-position-vertical-relative:margin" stroked="f" fillcolor="#A7F3D0"><v:fill opacity=".18"/><v:textpath style="font-family:Arial;font-size:1pt;font-weight:bold" string="PROOFMINT"/></v:shape></w:pict>'
    watermark_run = header_para.add_run(); watermark_run._r.append(parse_xml(watermark_xml))
    outcome, counts = _customer_summary(audit, findings, clearance)
    report.add_heading("Proofmint Audit Decision Report", 0); report.add_paragraph("Audit decision report", style="Subtitle")
    summary = report.add_table(rows=0, cols=2); summary.style = "Light Shading Accent 1"
    decision_summary = ", ".join(("dismissed" if decision.action == "dismiss" else decision.action) + (f": {decision.review_reason}" if decision.review_reason else "") for decision in decisions) or "No persisted review decision"
    for label, value in [("Audit outcome", outcome), ("Findings requiring review", counts.get("pending_review", 0) + counts.get("flagged", 0)), ("Total findings", len(findings)), ("Review status", audit.review_status), ("Review decisions", decision_summary), ("Flagged phrases", ", ".join(f.matched_phrase for f in findings if f.matched_phrase) or "None recorded")] + ([ ("Clearance", clearance.decision) ] if clearance else []):
        cells = summary.add_row().cells; cells[0].text = label; cells[1].text = str(value)
    report.add_heading("Executive summary", 1); report.add_paragraph(outcome + " Findings below reflect persisted audit records. Literal phrase matches are not independent evidence verification.")
    report.add_heading("Detailed findings", 1)
    if not findings: report.add_paragraph("No findings were recorded for this audit.")
    for index, finding in enumerate(findings, 1):
        report.add_heading(f"Finding {index} · {finding.finding_type}", 2)
        table = report.add_table(rows=0, cols=2); table.style = "Light Shading Accent 1"
        for label, value in _customer_finding_lines(finding, decisions, rules_by_id, documents_by_id, facts_by_id, terms_by_id, repair_decisions):
            cells = table.add_row().cells; cells[0].text = label; cells[1].text = str(value)
        report.add_paragraph()
    report.add_heading("Review status and traceability", 1); report.add_paragraph(outcome + " Technical identifiers are retained for traceability and are not repeated in the main narrative.")
    metadata = report.add_table(rows=0, cols=2); metadata.style = "Light Grid Accent 1"
    for label, value in [("Audit ID", audit.id), ("Workspace ID", audit.workspace_id), ("Content SHA-256", audit.content_sha256)] + ([("Guideline source", document.source_filename), ("Guideline SHA-256", document.source_sha256), ("Rule-set revision", document.extraction_revision)] if document else []):
        cells = metadata.add_row().cells; cells[0].text = label; cells[1].text = str(value)
    footer = section.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.CENTER; footer.add_run("Proofmint · Nothing ships unproven.")
    output = BytesIO(); report.save(output); return output.getvalue()
