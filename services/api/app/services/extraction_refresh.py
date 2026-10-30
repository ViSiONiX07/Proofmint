"""Version-aware refresh of extracted rules from an already-retained guideline PDF.

A guideline document row is an immutable source version. Refreshing does not edit it:
the corrected candidates are written as a new revision in the same source lineage, the
old revision keeps its rules, approvals, and every historical audit reference, and the
refreshed candidates stay in human review until a person approves them.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.guideline import CandidateRule, GuidelineDocument
from app.services.candidate_extraction import (
    CandidateRuleText,
    candidate_signature,
    extract_candidate_rules,
)
from app.services.source_document_store import SourceDocumentError, SourceDocumentStore, page_text

ComparisonKind = Literal["unchanged", "changed", "added", "removed"]

_RECOVERY_PATH = (
    "Re-upload the exact original PDF into this workspace to restore its private source copy, "
    "then refresh the extraction again."
)
_LIMITATIONS = [
    "Refresh re-runs the deterministic extractor against the retained original PDF. It uses no model and never invents wording.",
    "A candidate whose source page, character span, and text are unchanged keeps the existing human decision; every other candidate starts as pending_review.",
    "Rules the corrected extractor no longer produces are omitted from the new revision. The earlier revision keeps its rules, approvals, and source references.",
    "The refreshed revision becomes the newest revision for this source and is used by new audits once it holds approved rules.",
]


class ExtractionRefreshError(RuntimeError):
    """A refresh that must be refused rather than guessed at."""

    def __init__(self, code: str, message: str, recovery: str | None = None):
        super().__init__(code)
        self.code = code
        self.message = message
        self.recovery = recovery

    @property
    def detail(self) -> str:
        return f"{self.message} {self.recovery}" if self.recovery else self.message


@dataclass(frozen=True)
class SourceExtraction:
    """The retained source bytes and the candidates the current extractor produces."""

    data: bytes
    candidates: list[CandidateRuleText]
    signature: str


def lineage_documents(session: Session, document: GuidelineDocument) -> list[GuidelineDocument]:
    """Return every rule-set revision of one source, newest revision first."""
    return list(session.scalars(select(GuidelineDocument).where(
        GuidelineDocument.workspace_id == document.workspace_id,
        GuidelineDocument.source_sha256 == document.source_sha256,
    ).order_by(
        GuidelineDocument.extraction_revision.desc(),
        GuidelineDocument.created_at.desc(),
        GuidelineDocument.id,
    )))


def newest_revision(session: Session, document: GuidelineDocument) -> GuidelineDocument:
    documents = lineage_documents(session, document)
    return documents[0] if documents else document


def extract_retained_source(session: Session, document: GuidelineDocument) -> SourceExtraction:
    """Re-extract the retained original PDF, refusing any source that cannot be trusted."""
    store = SourceDocumentStore()
    try:
        data = store.read_verified(document)
    except SourceDocumentError as error:
        if error.code == "source_document_not_retained":
            raise ExtractionRefreshError(
                error.code,
                "The original PDF for this guideline is not in private server-side storage, so its rules cannot be re-extracted.",
                _RECOVERY_PATH,
            ) from None
        if error.code == "source_document_inaccessible":
            raise ExtractionRefreshError(
                error.code,
                "The stored original PDF could not be read, so its rules cannot be re-extracted.",
                "Check private storage permissions and availability, then retry.",
            ) from None
        raise ExtractionRefreshError(
            "source_hash_mismatch",
            "The stored source bytes no longer match the SHA-256 recorded for this guideline, so no rules were re-extracted.",
            "The stored copy must be restored or removed by an operator before the exact original PDF can be "
            "re-uploaded; this service never overwrites an object whose bytes do not match its recorded hash.",
        ) from None

    try:
        parsed = store.inspect_pdf(document, data)
    except SourceDocumentError:
        raise ExtractionRefreshError(
            "source_metadata_mismatch",
            "The stored source does not match this guideline's recorded page count or is not a readable PDF, so no rules were re-extracted.",
            _RECOVERY_PATH,
        ) from None

    try:
        pages = [(index + 1, page_text(page)) for index, page in enumerate(parsed)]
    except Exception:
        raise ExtractionRefreshError(
            "source_text_unavailable",
            "Text could not be read from the retained original PDF, so no rules were re-extracted.",
            _RECOVERY_PATH,
        ) from None
    finally:
        parsed.close()

    if len(pages) != document.page_count:
        raise ExtractionRefreshError(
            "source_metadata_mismatch",
            f"The retained PDF has {len(pages)} page(s) but this guideline records {document.page_count}, so no rules were re-extracted.",
            _RECOVERY_PATH,
        )

    try:
        candidates = extract_candidate_rules(pages)
    except Exception:
        raise ExtractionRefreshError(
            "candidate_extraction_failed",
            "Candidate rules could not be re-extracted from this PDF.",
        ) from None

    return SourceExtraction(data=data, candidates=candidates, signature=candidate_signature(candidates))


def _span_key(page: int, start: int, end: int) -> tuple[int, int, int]:
    return (page, start, end)


def summarize_review_statuses(session: Session, document_id: UUID) -> dict[str, int]:
    rows = session.execute(
        select(CandidateRule.review_status, func.count())
        .where(CandidateRule.document_id == document_id)
        .group_by(CandidateRule.review_status)
    ).all()
    counts = {status: 0 for status in ("pending_review", "approved", "rejected")}
    for status, count in rows:
        counts[status] = count
    return counts


def compare_rule_sets(existing_rules: list[CandidateRule], candidates: list[CandidateRuleText]) -> list[dict]:
    """Compare stored rules with the freshly extracted candidates by source page and span."""
    existing_by_span = {_span_key(rule.source_page, rule.source_start_offset, rule.source_end_offset): rule
                        for rule in existing_rules}
    extracted_by_span = {_span_key(item.source_page, item.source_start_offset, item.source_end_offset): item
                         for item in candidates}
    comparisons: list[dict] = []
    for key in sorted(set(existing_by_span) | set(extracted_by_span)):
        stored = existing_by_span.get(key)
        extracted = extracted_by_span.get(key)
        if stored is not None and extracted is not None:
            comparison: ComparisonKind = "unchanged" if stored.rule_text == extracted.rule_text else "changed"
        elif extracted is not None:
            comparison = "added"
        else:
            comparison = "removed"
        comparisons.append({
            "comparison": comparison,
            "source_page": key[0],
            "source_start_offset": key[1],
            "source_end_offset": key[2],
            "existing_rule_id": stored.id if stored is not None else None,
            "existing_rule_text": stored.rule_text if stored is not None else None,
            "existing_review_status": stored.review_status if stored is not None else None,
            "extracted_rule_text": extracted.rule_text if extracted is not None else None,
            "extracted_category": extracted.category if extracted is not None else None,
            "decision_carried_forward": comparison == "unchanged"
            and stored is not None and stored.review_status != "pending_review",
        })
    return comparisons


def build_extraction_revision_preview(session: Session, document: GuidelineDocument) -> dict:
    """Describe exactly which rules a refresh would change, without writing anything."""
    current = newest_revision(session, document)
    source = extract_retained_source(session, current)
    existing_rules = list(session.scalars(select(CandidateRule).where(
        CandidateRule.document_id == current.id
    ).order_by(CandidateRule.created_at, CandidateRule.id)))
    comparisons = compare_rule_sets(existing_rules, source.candidates)
    counts = {kind: sum(item["comparison"] == kind for item in comparisons)
              for kind in ("unchanged", "changed", "added", "removed")}
    return {
        "workspace_id": current.workspace_id,
        "document_id": current.id,
        "source_filename": current.source_filename,
        "source_sha256": current.source_sha256,
        "page_count": current.page_count,
        "current_revision": current.extraction_revision,
        "next_revision": current.extraction_revision + 1,
        "already_current": current.extraction_signature == source.signature,
        "existing_rule_count": len(existing_rules),
        "extracted_rule_count": len(source.candidates),
        "unchanged_count": counts["unchanged"],
        "changed_count": counts["changed"],
        "added_count": counts["added"],
        "removed_count": counts["removed"],
        "comparisons": comparisons,
        "limitations": list(_LIMITATIONS),
    }


def create_extraction_revision(session: Session, document: GuidelineDocument) -> dict:
    """Write the refreshed rules as a new immutable revision, or report an existing one.

    Repeating the call for the same source and extractor is a no-op: the revision is
    identified by the canonical candidate signature, so no duplicate revision or rule row
    is created. The caller owns the surrounding transaction.
    """
    current = newest_revision(session, document)
    source = extract_retained_source(session, current)

    if current.extraction_signature == source.signature:
        counts = summarize_review_statuses(session, current.id)
        return {
            "workspace_id": current.workspace_id,
            "document_id": current.id,
            "supersedes_document_id": current.supersedes_document_id,
            "extraction_revision": current.extraction_revision,
            "already_existed": True,
            "source_filename": current.source_filename,
            "source_sha256": current.source_sha256,
            "page_count": current.page_count,
            "file_size_bytes": current.file_size_bytes,
            "candidate_rule_count": sum(counts.values()),
            "approved_rule_count": counts["approved"],
            "pending_rule_count": counts["pending_review"],
            "rejected_rule_count": counts["rejected"],
            "carried_forward_decisions": 0,
            "removed_rule_count": 0,
            "created_at": current.created_at,
            "limitations": ["The stored rule set already matches the current extractor, so no new revision was created."],
        }

    existing_rules = list(session.scalars(select(CandidateRule).where(CandidateRule.document_id == current.id)))
    decisions = {
        _span_key(rule.source_page, rule.source_start_offset, rule.source_end_offset): rule.review_status
        for rule in existing_rules if rule.review_status != "pending_review"
    }
    comparisons = compare_rule_sets(existing_rules, source.candidates)
    removed_rule_count = sum(item["comparison"] == "removed" for item in comparisons)

    store = SourceDocumentStore()
    revision_id = uuid4()
    # Retain the same bytes under the new revision so its rules stay independently
    # verifiable; the source hash and filename are unchanged.
    try:
        store.retain(current.workspace_id, revision_id, current.source_sha256, source.data)
    except SourceDocumentError:
        raise ExtractionRefreshError(
            "source_storage_unavailable",
            "The retained source PDF could not be copied for a new revision, so no revision was created.",
            "Check private storage availability and retry.",
        ) from None

    revision = GuidelineDocument(
        id=revision_id,
        workspace_id=current.workspace_id,
        source_filename=current.source_filename,
        source_sha256=current.source_sha256,
        file_size_bytes=current.file_size_bytes,
        page_count=current.page_count,
        extraction_revision=current.extraction_revision + 1,
        supersedes_document_id=current.id,
        extraction_signature=source.signature,
    )
    rows = [
        CandidateRule(
            document_id=revision.id,
            rule_text=candidate.rule_text,
            category=candidate.category,
            source_page=candidate.source_page,
            source_start_offset=candidate.source_start_offset,
            source_end_offset=candidate.source_end_offset,
            source_excerpt=candidate.source_excerpt,
            review_status=decisions.get(
                _span_key(candidate.source_page, candidate.source_start_offset, candidate.source_end_offset),
                "pending_review",
            ),
        )
        for candidate in source.candidates
    ]
    session.add(revision)
    session.flush()
    session.add_all(rows)
    session.flush()
    session.refresh(revision, attribute_names=["created_at"])

    approved = sum(row.review_status == "approved" for row in rows)
    pending = sum(row.review_status == "pending_review" for row in rows)
    rejected = sum(row.review_status == "rejected" for row in rows)
    return {
        "workspace_id": revision.workspace_id,
        "document_id": revision.id,
        "supersedes_document_id": current.id,
        "extraction_revision": revision.extraction_revision,
        "already_existed": False,
        "source_filename": revision.source_filename,
        "source_sha256": revision.source_sha256,
        "page_count": revision.page_count,
        "file_size_bytes": revision.file_size_bytes,
        "candidate_rule_count": len(rows),
        "approved_rule_count": approved,
        "pending_rule_count": pending,
        "rejected_rule_count": rejected,
        # In a brand-new revision every non-pending status was inherited from an
        # identical rule a human already reviewed, so this is the preserved-decision count.
        "carried_forward_decisions": approved + rejected,
        "removed_rule_count": removed_rule_count,
        "created_at": revision.created_at,
        "limitations": list(_LIMITATIONS),
    }
