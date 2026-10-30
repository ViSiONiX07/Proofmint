"""Preview-only minimal literal repairs backed by current verified evidence."""

from sqlalchemy.orm import Session

from app.models.imports import ImportedTerm
from app.services.evidence_verification import verify_finding


def build_repair_preview(session: Session, content: str, workspace_id, findings: list) -> tuple[str, list[dict]]:
    replacements = []
    previous_end = -1
    for finding in sorted(findings, key=lambda item: (item.match_start, item.match_end, str(item.id))):
        # Only approved preferred terminology provides a deterministic replacement.
        # A rule match, fact match, or merely populated suggestion field is not enough.
        if (
            finding.finding_type != "preferred_terminology"
            or finding.term_id is None
            or finding.rule_id is not None
            or finding.fact_id is not None
            or finding.verification_status != "verified"
            or not finding.suggested_correction
            or finding.suggested_correction == finding.matched_phrase
        ):
            continue
        start, end = finding.match_start, finding.match_end
        if start < 0 or end <= start or end > len(content) or content[start:end] != finding.matched_phrase:
            raise ValueError("A repair suggestion has a stale or invalid source span.")
        outcome = verify_finding(session, {
            "rule_id": finding.rule_id, "fact_id": finding.fact_id, "term_id": finding.term_id,
            "source_document_id": finding.source_document_id,
            "source_document_sha256": finding.source_document_sha256,
            "matched_phrase": finding.matched_phrase, "match_start": start, "match_end": end,
            "suggested_correction": finding.suggested_correction, "evidence_excerpt": finding.evidence_excerpt,
            "source_filename": finding.source_filename, "source_page": finding.source_page,
            "source_start_offset": finding.source_start_offset, "source_end_offset": finding.source_end_offset,
            "explanation": finding.explanation,
        }, content, workspace_id)
        if outcome.status != "verified":
            raise ValueError("The approved evidence for a repair suggestion has changed or is no longer valid.")
        if start < previous_end:
            continue
        term = session.get(ImportedTerm, finding.term_id) if finding.term_id else None
        replacements.append({
            "finding_id": finding.id, "start": start, "end": end,
            "original": finding.matched_phrase, "replacement": finding.suggested_correction,
            "source_filename": finding.source_filename or "",
            "source_label": f"Approved terminology: {term.term} → {term.preferred_form}" if term else "Approved rule",
            "reason": finding.explanation,
        })
        previous_end = end
    repaired = content
    for replacement in reversed(replacements):
        repaired = repaired[:replacement["start"]] + replacement["replacement"] + repaired[replacement["end"]:]
    return repaired, replacements
