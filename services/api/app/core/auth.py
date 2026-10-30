"""HttpOnly-cookie authentication primitives and fail-closed resource authorization."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import secrets
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.models.identity import AuthSession, User
from app.models.workspace import Workspace

SESSION_COOKIE = "proofmint_session"
CSRF_COOKIE = "proofmint_csrf"


@dataclass(frozen=True)
class Principal:
    session: AuthSession
    user: User | None

    @property
    def role(self) -> str:
        return self.session.role


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_principal(request: Request, db: Session = Depends(get_db_session)) -> Principal:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise HTTPException(status_code=401, detail="Sign in to access this resource.")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(raw)))
    now = datetime.now(timezone.utc)
    expiry = session.expires_at.replace(tzinfo=session.expires_at.tzinfo or timezone.utc) if session is not None else now
    if session is None or session.revoked_at is not None or expiry <= now:
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.")
    user = db.get(User, session.user_id) if session.user_id else None
    if session.role == "user" and user is None or session.role == "judge" and session.user_id is not None:
        raise HTTPException(status_code=401, detail="The session is invalid.")
    return Principal(session=session, user=user)


def require_user(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.role != "user" or principal.user is None:
        raise HTTPException(status_code=403, detail="This action is not available in Judge Mode.")
    return principal


def require_csrf(request: Request, principal: Principal = Depends(get_principal)) -> Principal:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header) or not hmac.compare_digest(digest(cookie), principal.session.csrf_hash):
        raise HTTPException(status_code=403, detail="The request could not be verified. Refresh and try again.")
    return principal


def require_workspace_access(db: Session, workspace_id: UUID, principal: Principal, *, write: bool = False) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.kind == "legacy":
        raise HTTPException(status_code=404, detail="Workspace was not found.")
    if principal.role == "user":
        allowed = principal.user is not None and workspace.owner_user_id == principal.user.id
    elif principal.role == "judge":
        allowed = workspace.kind == "judge_demo" and workspace.owner_judge_session_id == principal.session.id
    else:
        allowed = False
    if not allowed:
        raise HTTPException(status_code=404, detail="Workspace was not found.")
    return workspace


def new_secret() -> str:
    return secrets.token_urlsafe(32)
