"""Listing and explicit human review for imported facts and terminology."""

import logging
from collections.abc import Generator
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import DatabaseNotConfiguredError, get_db_session
from app.models.imports import ImportedFact, ImportedTerm
from app.models.workspace import Workspace
from app.schemas.candidate_rule import ReviewStatus
from app.schemas.import_review import (
    ImportedFactList,
    ImportedFactRead,
    ImportedTermList,
    ImportedTermRead,
)

router = APIRouter()
logger = logging.getLogger(__name__)
REVIEW_PAGE_SIZE = 50


def get_import_review_db_session() -> Generator[Session, None, None]:
    """Translate missing persistence configuration into a clear service error."""
    try:
        yield from get_db_session()
    except DatabaseNotConfiguredError:
        raise HTTPException(status_code=503, detail="PostgreSQL is not configured for imported-row review.") from None


def _database_failure(session: Session, exc: SQLAlchemyError):
    session.rollback()
    logger.error("Imported-row review database operation failed (%s)", type(exc).__name__)
    raise HTTPException(status_code=503, detail="Imported data is temporarily unavailable.") from None


def _require_workspace(session: Session, workspace_id: UUID):
    workspace = session.get(Workspace, workspace_id)
    if workspace is None or workspace.kind == "legacy":
        raise HTTPException(status_code=404, detail="Workspace was not found.")


def _list_records(session: Session, model, workspace_id: UUID, status: ReviewStatus | None, limit: int, offset: int):
    _require_workspace(session, workspace_id)
    filters = [model.workspace_id == workspace_id]
    if status is not None:
        filters.append(model.review_status == status)
    total = session.scalar(select(func.count()).select_from(model).where(*filters)) or 0
    items = session.scalars(
        select(model).where(*filters).order_by(model.imported_at, model.id).limit(limit).offset(offset)
    ).all()
    return items, total


def _transition(session: Session, model, record_id: UUID, workspace_id: UUID, target: Literal["approved", "rejected"]):
    try:
        with session.begin():
            _require_workspace(session, workspace_id)
            record = session.scalar(select(model).where(model.id == record_id, model.workspace_id == workspace_id).with_for_update())
            if record is None:
                raise HTTPException(status_code=404, detail="Imported record was not found.")
            if record.review_status != "pending_review":
                raise HTTPException(
                    status_code=409,
                    detail=f"Imported record is already {record.review_status}; only pending records can be reviewed.",
                )
            record.review_status = target
            session.flush()
            session.refresh(record, attribute_names=["updated_at"])
            response = record
        return response
    except SQLAlchemyError as exc:
        _database_failure(session, exc)


@router.get("/facts", response_model=ImportedFactList, summary="List imported facts for review")
def list_facts(
    workspace_id: UUID,
    status: ReviewStatus | None = None,
    limit: int = Query(REVIEW_PAGE_SIZE, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_import_review_db_session),
):
    try:
        items, total = _list_records(session, ImportedFact, workspace_id, status, limit, offset)
        return ImportedFactList(items=items, total=total, limit=limit, offset=offset)
    except SQLAlchemyError as exc:
        _database_failure(session, exc)


@router.get("/terms", response_model=ImportedTermList, summary="List imported terminology for review")
def list_terms(
    workspace_id: UUID,
    status: ReviewStatus | None = None,
    limit: int = Query(REVIEW_PAGE_SIZE, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_import_review_db_session),
):
    try:
        items, total = _list_records(session, ImportedTerm, workspace_id, status, limit, offset)
        return ImportedTermList(items=items, total=total, limit=limit, offset=offset)
    except SQLAlchemyError as exc:
        _database_failure(session, exc)


@router.get("/facts/{fact_id}", response_model=ImportedFactRead, summary="Get an imported fact and its provenance")
def get_fact(fact_id: UUID, workspace_id: UUID, session: Session = Depends(get_import_review_db_session)):
    try:
        _require_workspace(session, workspace_id)
        record = session.scalar(select(ImportedFact).where(ImportedFact.id == fact_id, ImportedFact.workspace_id == workspace_id))
        if record is None:
            raise HTTPException(status_code=404, detail="Imported fact was not found.")
        return record
    except SQLAlchemyError as exc:
        _database_failure(session, exc)


@router.get("/terms/{term_id}", response_model=ImportedTermRead, summary="Get imported terminology and its provenance")
def get_term(term_id: UUID, workspace_id: UUID, session: Session = Depends(get_import_review_db_session)):
    try:
        _require_workspace(session, workspace_id)
        record = session.scalar(select(ImportedTerm).where(ImportedTerm.id == term_id, ImportedTerm.workspace_id == workspace_id))
        if record is None:
            raise HTTPException(status_code=404, detail="Imported term was not found.")
        return record
    except SQLAlchemyError as exc:
        _database_failure(session, exc)


def _register_transition_routes(resource: str, model):
    for action, target in (("approve", "approved"), ("reject", "rejected")):
        def make_endpoint(route_model, route_target):
            def endpoint(record_id: UUID, workspace_id: UUID, session: Session = Depends(get_import_review_db_session)):
                return _transition(session, route_model, record_id, workspace_id, route_target)

            return endpoint

        endpoint = make_endpoint(model, target)

        endpoint.__name__ = f"{target}_{resource.rstrip('s')}"
        router.add_api_route(
            f"/{resource}/{{record_id}}/{action}",
            endpoint,
            methods=["POST"],
            response_model=ImportedFactRead if model is ImportedFact else ImportedTermRead,
            summary=f"{target.capitalize()} a pending imported {resource.rstrip('s')}",
            description=(
                f"Explicitly transitions pending_review to {target}. Only pending records can be reviewed. "
                "Reviewer identity and an audit trail are not stored by the current schema."
            ),
        )


_register_transition_routes("facts", ImportedFact)
_register_transition_routes("terms", ImportedTerm)
