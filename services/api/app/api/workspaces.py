"""Read-only workspace recovery for refreshing the active browser session."""

from collections.abc import Generator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import DatabaseNotConfiguredError, get_db_session
from app.models.guideline import GuidelineDocument
from app.models.workspace import Workspace
from app.models.audit import AuditRun

router = APIRouter()


def get_workspace_session() -> Generator[Session, None, None]:
    try:
        yield from get_db_session()
    except DatabaseNotConfiguredError:
        raise HTTPException(status_code=503, detail="PostgreSQL is not configured for workspace access.") from None


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: UUID, session: Session = Depends(get_workspace_session)):
    workspace = session.get(Workspace, workspace_id)
    if workspace is None or workspace.kind == "legacy":
        raise HTTPException(status_code=404, detail="Workspace was not found.")
    documents = session.scalars(
        select(GuidelineDocument).where(GuidelineDocument.workspace_id == workspace_id)
        .order_by(GuidelineDocument.created_at.desc(), GuidelineDocument.id)
    ).all()
    latest_audit = session.scalar(
        select(AuditRun).where(AuditRun.workspace_id == workspace_id)
        .order_by(AuditRun.created_at.desc(), AuditRun.id).limit(1)
    )
    return {"id": workspace.id, "created_at": workspace.created_at, "documents": documents,
            "latest_audit_id": latest_audit.id if latest_audit else None}
