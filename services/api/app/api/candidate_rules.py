"""Candidate-rule listing and explicit human review transitions."""

import logging
from collections.abc import Generator
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import DatabaseNotConfiguredError, get_db_session
from app.models.guideline import CandidateRule, GuidelineDocument
from app.schemas.candidate_rule import CandidateRuleList, CandidateRuleRead, ReviewStatus

router = APIRouter()
logger = logging.getLogger(__name__)
REVIEW_PAGE_SIZE = 50


def get_review_db_session() -> Generator[Session, None, None]:
    """Translate missing persistence configuration into a clear service error."""
    try:
        yield from get_db_session()
    except DatabaseNotConfiguredError:
        raise HTTPException(status_code=503, detail="PostgreSQL is not configured for candidate review.") from None


def _database_failure(session: Session, exc: SQLAlchemyError):
    session.rollback()
    logger.error("Candidate-rule database operation failed (%s)", type(exc).__name__)
    raise HTTPException(status_code=503, detail="Candidate-rule data is temporarily unavailable.") from None


def _as_read(rule: CandidateRule, document: GuidelineDocument) -> CandidateRuleRead:
    return CandidateRuleRead(
        id=rule.id,
        document_id=rule.document_id,
        rule_text=rule.rule_text,
        category=rule.category,
        source_page=rule.source_page,
        source_start_offset=rule.source_start_offset,
        source_end_offset=rule.source_end_offset,
        source_excerpt=rule.source_excerpt,
        review_status=rule.review_status,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        source_filename=document.source_filename,
        source_sha256=document.source_sha256,
    )


def _list_rules(
    session: Session,
    *,
    workspace_id: UUID,
    document_id: UUID | None,
    status: ReviewStatus | None,
    limit: int,
    offset: int,
) -> CandidateRuleList:
    filters = []
    if document_id is not None:
        document = session.get(GuidelineDocument, document_id)
        if document is None or document.workspace_id != workspace_id:
            raise HTTPException(status_code=404, detail="Guideline document was not found.")
        filters.append(CandidateRule.document_id == document_id)
    filters.append(GuidelineDocument.workspace_id == workspace_id)
    if status is not None:
        filters.append(CandidateRule.review_status == status)

    total = session.scalar(select(func.count()).select_from(CandidateRule).join(GuidelineDocument, CandidateRule.document_id == GuidelineDocument.id).where(*filters)) or 0
    rows = session.execute(
        select(CandidateRule, GuidelineDocument)
        .join(GuidelineDocument, CandidateRule.document_id == GuidelineDocument.id)
        .where(*filters)
        .order_by(CandidateRule.created_at, CandidateRule.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return CandidateRuleList(
        items=[_as_read(rule, document) for rule, document in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/rules/pending",
    response_model=CandidateRuleList,
    summary="List pending candidate rules",
    description="Lists unreviewed candidates with source document and source-span information. No approval is implied.",
)
def list_pending_rules(
    workspace_id: UUID,
    document_id: UUID | None = None,
    limit: int = Query(REVIEW_PAGE_SIZE, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_review_db_session),
):
    try:
        return _list_rules(
            session, workspace_id=workspace_id, document_id=document_id, status="pending_review", limit=limit, offset=offset
        )
    except SQLAlchemyError as exc:
        _database_failure(session, exc)


@router.get(
    "/guidelines/{document_id}/rules",
    response_model=CandidateRuleList,
    summary="List candidate rules for a guideline document",
)
def list_document_rules(
    document_id: UUID,
    workspace_id: UUID,
    status: ReviewStatus | None = None,
    limit: int = Query(REVIEW_PAGE_SIZE, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_review_db_session),
):
    try:
        return _list_rules(session, workspace_id=workspace_id, document_id=document_id, status=status, limit=limit, offset=offset)
    except SQLAlchemyError as exc:
        _database_failure(session, exc)


@router.get(
    "/rules/{candidate_id}",
    response_model=CandidateRuleRead,
    summary="Get candidate rule and its source span",
)
def get_candidate_rule(candidate_id: UUID, workspace_id: UUID, session: Session = Depends(get_review_db_session)):
    try:
        rule = session.get(CandidateRule, candidate_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Candidate rule was not found.")
        document = session.get(GuidelineDocument, rule.document_id)
        if document is None or document.workspace_id != workspace_id:
            # The foreign key should prevent this; fail closed if the schema is inconsistent.
            raise HTTPException(status_code=404, detail="Source guideline document was not found.")
        return _as_read(rule, document)
    except SQLAlchemyError as exc:
        _database_failure(session, exc)


def _transition(candidate_id: UUID, workspace_id: UUID, target: Literal["approved", "rejected"], session: Session):
    try:
        with session.begin():
            rule = session.scalar(
                select(CandidateRule).where(CandidateRule.id == candidate_id).with_for_update()
            )
            if rule is None:
                raise HTTPException(status_code=404, detail="Candidate rule was not found.")
            document = session.get(GuidelineDocument, rule.document_id)
            if document is None or document.workspace_id != workspace_id:
                raise HTTPException(status_code=404, detail="Candidate rule was not found.")
            if rule.review_status != "pending_review":
                raise HTTPException(
                    status_code=409,
                    detail=f"Candidate rule is already {rule.review_status}; only pending rules can be reviewed.",
                )
            rule.review_status = target
            session.flush()
            session.refresh(rule, attribute_names=["updated_at"])
            document = session.get(GuidelineDocument, rule.document_id)
            if document is None:
                raise HTTPException(status_code=404, detail="Source guideline document was not found.")
            response = _as_read(rule, document)
        return response
    except SQLAlchemyError as exc:
        _database_failure(session, exc)


@router.post(
    "/rules/{candidate_id}/approve",
    response_model=CandidateRuleRead,
    summary="Approve a pending candidate rule",
    description="Explicitly transitions pending_review to approved. Reviewer identity and audit history are not stored.",
)
def approve_candidate_rule(candidate_id: UUID, workspace_id: UUID, session: Session = Depends(get_review_db_session)):
    return _transition(candidate_id, workspace_id, "approved", session)


@router.post(
    "/rules/{candidate_id}/reject",
    response_model=CandidateRuleRead,
    summary="Reject a pending candidate rule",
    description="Explicitly transitions pending_review to rejected. Reviewer identity and audit history are not stored.",
)
def reject_candidate_rule(candidate_id: UUID, workspace_id: UUID, session: Session = Depends(get_review_db_session)):
    return _transition(candidate_id, workspace_id, "rejected", session)
