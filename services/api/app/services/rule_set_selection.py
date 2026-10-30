"""Choose which guideline rule-set revision a new audit evaluates against.

Historical audits never move: an audit stores the document it used and each finding
snapshots its own ``source_document_id``/``source_document_sha256``. Only the choice made
for a *new* audit is resolved here.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.guideline import CandidateRule, GuidelineDocument


def _approved_rule_counts(session: Session, document_ids: list[UUID]) -> dict[UUID, int]:
    if not document_ids:
        return {}
    rows = session.execute(
        select(CandidateRule.document_id, func.count())
        .where(CandidateRule.document_id.in_(document_ids), CandidateRule.review_status == "approved")
        .group_by(CandidateRule.document_id)
    ).all()
    return {document_id: count for document_id, count in rows}


def resolve_audit_document(
    session: Session,
    workspace_id: UUID,
    document: GuidelineDocument | None,
) -> tuple[GuidelineDocument | None, list[str]]:
    """Return the revision whose approved rules this audit should use, plus honest notes.

    The newest revision of the source lineage is preferred, but only once it holds an
    approved rule. A freshly refreshed revision starts with no approved rules, and an audit
    must never quietly evaluate zero rules while an approved revision is still available.
    """
    if document is None:
        return None, []

    revisions = list(session.scalars(select(GuidelineDocument).where(
        GuidelineDocument.workspace_id == workspace_id,
        GuidelineDocument.source_sha256 == document.source_sha256,
    ).order_by(
        GuidelineDocument.extraction_revision.desc(),
        GuidelineDocument.created_at.desc(),
        GuidelineDocument.id,
    )))
    if not revisions:
        return document, []

    approved = _approved_rule_counts(session, [item.id for item in revisions])
    newest = revisions[0]
    for revision in revisions:
        if approved.get(revision.id, 0) > 0:
            notes: list[str] = []
            if revision.id != document.id:
                notes.append(
                    f"Approved rules were taken from extraction revision {revision.extraction_revision} "
                    f"of this guideline source."
                )
            if revision.id != newest.id:
                notes.append(
                    f"Extraction revision {newest.extraction_revision} of this guideline is still in human "
                    f"review, so this audit used the approved rules of revision {revision.extraction_revision}."
                )
            return revision, notes
    return document, []
