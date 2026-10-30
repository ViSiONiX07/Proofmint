"""Independent, conservative verification of deterministic audit findings."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.guideline import CandidateRule, GuidelineDocument
from app.models.imports import ImportedFact, ImportedTerm
from app.services.source_document_store import SourceDocumentError, SourceDocumentStore, page_text

VerificationStatus = Literal["verified", "uncertain", "rejected"]


@dataclass(frozen=True)
class VerificationOutcome:
    status: VerificationStatus
    reason_code: str | None
    explanation: str


def _rejected(code: str, explanation: str) -> VerificationOutcome:
    return VerificationOutcome("rejected", code, explanation)


def verify_finding(session: Session, finding: dict, content: str, workspace_id: UUID) -> VerificationOutcome:
    """Cross-check offsets, live approved records, workspace ownership and source metadata.

    Rule findings are verified only after independently reopening the exact retained
    PDF version and comparing the cited page-local source span with persisted evidence.
    """
    start, end = finding.get("match_start"), finding.get("match_end")
    phrase = finding.get("matched_phrase")
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end > len(content):
        return _rejected("invalid_offsets", "Finding offsets are outside the submitted text.")
    if not isinstance(phrase, str) or content[start:end] != phrase:
        return _rejected("span_mismatch", "The submitted text at the finding offsets does not match the reported phrase.")

    references = [name for name in ("rule_id", "fact_id", "term_id") if finding.get(name) is not None]
    if len(references) != 1:
        return _rejected("invalid_evidence_references", "A finding must point to exactly one approved evidence record.")

    if references[0] == "rule_id":
        rule = session.get(CandidateRule, finding["rule_id"])
        if rule is None:
            return _rejected("source_reference_missing", "The referenced guideline rule no longer exists.")
        document = session.get(GuidelineDocument, rule.document_id)
        if document is None:
            return _rejected("source_reference_missing", "The guideline document for this rule no longer exists.")
        if document.workspace_id != workspace_id:
            return _rejected("workspace_mismatch", "The referenced rule belongs to a different workspace.")
        if finding.get("source_document_id") != document.id or finding.get("source_document_sha256") != document.source_sha256:
            return _rejected("source_version_mismatch", "The finding's recorded source version does not match its approved rule.")
        if rule.review_status != "approved":
            return _rejected("rule_not_approved", "The referenced guideline rule is not approved.")
        if (rule.source_page < 1 or rule.source_start_offset < 0
                or rule.source_end_offset <= rule.source_start_offset
                or rule.source_end_offset - rule.source_start_offset != len(rule.source_excerpt)
                or rule.source_excerpt != rule.rule_text
                or finding.get("evidence_excerpt") != rule.source_excerpt
                or finding.get("source_filename") != document.source_filename
                or finding.get("source_page") != rule.source_page
                or finding.get("source_start_offset") != rule.source_start_offset
                or finding.get("source_end_offset") != rule.source_end_offset):
            return _rejected("source_reference_invalid", "Persisted rule excerpt and source span metadata are inconsistent.")
        if rule.rule_text.find(phrase) < 0 and phrase.casefold() not in rule.rule_text.casefold():
            return _rejected("evidence_mismatch", "The matched phrase is not supported by the approved rule text.")
        try:
            source_data = SourceDocumentStore().read_verified(document)
        except SourceDocumentError as exc:
            if exc.code in {"source_document_not_retained", "source_document_inaccessible"}:
                return VerificationOutcome("uncertain", exc.code, "The exact source PDF is unavailable for independent verification.")
            return _rejected(exc.code, "The retained source PDF failed its integrity or metadata check.")
        try:
            pdf = SourceDocumentStore().inspect_pdf(document, source_data)
        except SourceDocumentError as exc:
            return _rejected(exc.code, "The retained PDF is unreadable or differs from its recorded metadata.")
        try:
            if rule.source_page > pdf.page_count:
                return _rejected("source_page_invalid", "The cited page does not exist in the retained source PDF.")
            try:
                actual_page_text = page_text(pdf[rule.source_page - 1])
            except Exception:
                return _rejected("source_page_unreadable", "The cited page could not be independently read from the retained PDF.")
        finally:
            pdf.close()
        if (rule.source_end_offset > len(actual_page_text)
                or actual_page_text[rule.source_start_offset:rule.source_end_offset] != rule.source_excerpt):
            return _rejected("source_span_mismatch", "The stored citation span does not match the retained PDF page text.")
        return VerificationOutcome("verified", None,
            "The exact retained PDF hash, workspace, approved rule version, cited page, and page-local source span were independently checked.")

    if references[0] == "fact_id":
        fact = session.get(ImportedFact, finding["fact_id"])
        if fact is None:
            return _rejected("fact_reference_invalid", "The referenced approved fact does not exist.")
        if fact.workspace_id != workspace_id:
            return _rejected("workspace_mismatch", "The referenced fact belongs to a different workspace.")
        if fact.review_status != "approved":
            return _rejected("fact_not_approved", "The referenced fact is not approved.")
        if not fact.source_filename or fact.source_row_number < 1 or len(fact.source_sha256) != 64:
            return _rejected("source_reference_invalid", "The approved fact is missing valid import provenance.")
        statement = fact.approved_statement.strip()
        expected_explanation = "Submitted text exactly contains this approved factual statement; this literal match does not verify claims by meaning."
        if (content[start:end].casefold() != statement.casefold()
                or finding.get("evidence_excerpt") != fact.approved_statement[:1000]
                or finding.get("source_filename") != fact.source_filename
                or finding.get("explanation") != expected_explanation):
            return _rejected("evidence_mismatch", "The finding does not match the approved fact as a literal statement.")
        return VerificationOutcome("verified", None, "The text exactly matches an approved fact record and its stored import provenance; semantic truth is not established.")

    term = session.get(ImportedTerm, finding["term_id"])
    if term is None:
        return _rejected("term_reference_invalid", "The referenced terminology record does not exist.")
    if term.workspace_id != workspace_id:
        return _rejected("workspace_mismatch", "The referenced terminology record belongs to a different workspace.")
    if term.review_status != "approved":
        return _rejected("term_not_approved", "The referenced terminology record is not approved.")
    if (not term.preferred_form or term.preferred_form == term.term
            or not term.source_filename or term.source_row_number < 1 or len(term.source_sha256) != 64):
        return _rejected("source_reference_invalid", "The terminology record has no valid preferred form or import provenance.")
    expected_explanation = "The submitted text uses the imported term instead of its explicitly configured preferred form."
    if (content[start:end].casefold() != term.term.casefold()
            or finding.get("suggested_correction") != term.preferred_form
            or finding.get("evidence_excerpt") != f"{term.term} → {term.preferred_form}"
            or finding.get("source_filename") != term.source_filename
            or finding.get("explanation") != expected_explanation):
        return _rejected("evidence_mismatch", "The terminology match or proposed preferred form differs from the approved record.")
    return VerificationOutcome("verified", None, "The literal term and preferred form match an approved, workspace-scoped terminology record.")


def verify_findings(session: Session, findings: list[dict], content: str, workspace_id: UUID) -> list[dict]:
    """Return finding records enriched with independently computed outcomes."""
    result = []
    for finding in findings:
        outcome = verify_finding(session, finding, content, workspace_id)
        result.append({**finding, "verification_status": outcome.status,
                       "verification_reason": outcome.reason_code,
                       "verification_explanation": outcome.explanation})
    return result
