"""Local email authentication, Google OIDC, profile and isolated judge sessions."""

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import re
import secrets
import threading
import time
from urllib.parse import urlencode
from uuid import UUID

import httpx
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError
    _argon = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)
except ImportError:  # development fallback for environments that have not installed requirements
    PasswordHasher = None
    InvalidHash = VerificationError = VerifyMismatchError = Exception
    _argon = None
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import CSRF_COOKIE, SESSION_COOKIE, Principal, digest, get_principal, new_secret, require_csrf
from app.core.config import settings
from app.core.database import get_db_session
from app.models.identity import AuthSession, OAuthState, User
from app.models.workspace import Workspace

router = APIRouter(prefix="/auth", tags=["Authentication"])
_attempts: dict[str, deque[float]] = defaultdict(deque)
_attempt_lock = threading.Lock()
_EMAIL = re.compile(r"^[^\s@]{1,64}@[^\s@.]+(?:\.[^\s@.]+)+$")


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def _rate_limit(request: Request, action: str) -> None:
    key = f"{action}:{request.client.host if request.client else 'unknown'}"
    now = time.monotonic()
    with _attempt_lock:
        recent = _attempts[key]
        while recent and now - recent[0] > 900:
            recent.popleft()
        if len(recent) >= 10:
            raise HTTPException(status_code=429, detail="Too many attempts. Wait before trying again.", headers={"Retry-After": "900"})
        recent.append(now)


def _hash_password(password: str) -> str:
    if _argon is not None:
        return _argon.hash(password)
    salt = secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode(), salt=salt, n=2**15, r=8, p=1, dklen=64, maxmem=64 * 1024 * 1024)
    return "scrypt$32768$8$1$" + base64.urlsafe_b64encode(salt + value).decode("ascii")


def _verify_password(password: str, stored: str | None) -> bool:
    if isinstance(stored, str) and stored.startswith("$argon2id$") and _argon is not None:
        try:
            return _argon.verify(stored, password)
        except (InvalidHash, VerificationError, VerifyMismatchError):
            return False
    try:
        algorithm, n, r, p, encoded = stored.split("$", 4)  # type: ignore[union-attr]
        if algorithm != "scrypt" or (n, r, p) != ("32768", "8", "1"):
            return False
        packed = base64.urlsafe_b64decode(encoded.encode("ascii"))
        actual = hashlib.scrypt(password.encode(), salt=packed[:16], n=int(n), r=int(r), p=int(p), dklen=len(packed) - 16, maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(actual, packed[16:])
    except (ValueError, TypeError, AttributeError):
        return False


def _issue_session(response: Response, db: Session, *, user: User | None, role: str, ttl: timedelta) -> tuple[AuthSession, dict]:
    token, csrf = new_secret(), new_secret()
    row = AuthSession(user_id=user.id if user else None, role=role, token_hash=digest(token), csrf_hash=digest(csrf), expires_at=datetime.now(timezone.utc) + ttl)
    db.add(row)
    db.flush()
    secure = settings.APP_ENV.casefold() == "production"
    same_site = "none" if secure else "lax"
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=secure, samesite=same_site, path="/", max_age=int(ttl.total_seconds()))
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite=same_site, path="/", max_age=int(ttl.total_seconds()))
    return row, {"role": role, "expires_at": row.expires_at.isoformat(), "csrf_token": csrf}


def _public_user(user: User) -> dict:
    return {"id": str(user.id), "first_name": user.first_name, "surname": user.surname, "email": user.email}


def _credential_error():
    raise HTTPException(status_code=401, detail="Email or password is incorrect.")


@router.post("/register", status_code=201)
def register(request: Request, response: Response, payload: dict, db: Session = Depends(get_db_session)):
    _rate_limit(request, "register")
    first = str(payload.get("first_name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    email = normalize_email(str(payload.get("email", "")))
    password, confirmation = payload.get("password"), payload.get("confirm_password")
    if not first or len(first) > 100 or len(surname) > 100 or not _EMAIL.fullmatch(email):
        raise HTTPException(status_code=422, detail="Enter a valid first name, surname, and email address.")
    if not isinstance(password, str) or len(password) < 12 or len(password) > 256 or not any(c.islower() for c in password) or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password) or not any(not c.isalnum() for c in password):
        raise HTTPException(status_code=422, detail="Use at least 12 characters with upper and lowercase letters, a number, and a symbol.")
    if password != confirmation:
        raise HTTPException(status_code=422, detail="Passwords do not match.")
    user = User(first_name=first, surname=surname, email=email, password_hash=_hash_password(password))
    db.add(user)
    try:
        db.flush()
        _row, session_data = _issue_session(response, db, user=user, role="user", ttl=timedelta(hours=12))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account could not be created with those details.") from None
    return {"user": _public_user(user), "session": session_data}


@router.post("/login")
def login(request: Request, response: Response, payload: dict, db: Session = Depends(get_db_session)):
    _rate_limit(request, "login")
    email = normalize_email(str(payload.get("email", "")))
    user = db.scalar(select(User).where(User.email == email)) if _EMAIL.fullmatch(email) else None
    if user is None or not isinstance(payload.get("password"), str) or not _verify_password(payload["password"], user.password_hash):
        _credential_error()
    _row, session_data = _issue_session(response, db, user=user, role="user", ttl=timedelta(hours=12))
    db.commit()
    return {"user": _public_user(user), "session": session_data}


@router.get("/me")
def me(request: Request, principal: Principal = Depends(get_principal)):
    if principal.role == "judge":
        return {"role": "judge", "profile": None, "label": "Judge — Demonstration Access", "csrf_token": request.cookies.get(CSRF_COOKIE)}
    return {"role": "user", "profile": _public_user(principal.user), "csrf_token": request.cookies.get(CSRF_COOKIE)}


@router.put("/profile")
def update_profile(payload: dict, principal: Principal = Depends(require_csrf), db: Session = Depends(get_db_session)):
    if principal.role != "user" or principal.user is None:
        raise HTTPException(status_code=403, detail="Judge sessions cannot modify user profiles.")
    first, surname = str(payload.get("first_name", "")).strip(), str(payload.get("surname", "")).strip()
    if not first or len(first) > 100 or len(surname) > 100:
        raise HTTPException(status_code=422, detail="First name is required; names must be 100 characters or fewer.")
    user = db.get(User, principal.user.id)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in again to update your profile.")
    user.first_name, user.surname = first, surname
    db.commit()
    return {"profile": _public_user(user)}


@router.put("/password")
def update_password(payload: dict, principal: Principal = Depends(require_csrf), db: Session = Depends(get_db_session)):
    if principal.role != "user" or principal.user is None:
        raise HTTPException(status_code=403, detail="Judge sessions cannot manage account credentials.")
    current, replacement, confirmation = payload.get("current_password"), payload.get("new_password"), payload.get("confirm_password")
    user = db.get(User, principal.user.id)
    if user is None or not isinstance(current, str) or not _verify_password(current, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if not isinstance(replacement, str) or len(replacement) < 12 or len(replacement) > 256 or not any(c.islower() for c in replacement) or not any(c.isupper() for c in replacement) or not any(c.isdigit() for c in replacement) or not any(not c.isalnum() for c in replacement):
        raise HTTPException(status_code=422, detail="Use at least 12 characters with upper and lowercase letters, a number, and a symbol.")
    if replacement != confirmation:
        raise HTTPException(status_code=422, detail="Passwords do not match.")
    user.password_hash = _hash_password(replacement)
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.id != principal.session.id, AuthSession.revoked_at.is_(None)).update({AuthSession.revoked_at: datetime.now(timezone.utc)}, synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.post("/logout")
def logout(response: Response, principal: Principal = Depends(require_csrf), db: Session = Depends(get_db_session)):
    principal.session.revoked_at = datetime.now(timezone.utc)
    db.add(principal.session)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}


@router.post("/judge")
def judge_mode(response: Response, db: Session = Depends(get_db_session)):
    judge, session_data = _issue_session(response, db, user=None, role="judge", ttl=timedelta(hours=2))
    workspace = Workspace(kind="judge_demo", owner_judge_session_id=judge.id)
    db.add(workspace)
    db.commit()
    return {"role": "judge", "label": "Judge — Demonstration Access", "workspace_id": str(workspace.id), "session": session_data}


@router.get("/google/start")
def google_start(response: Response, db: Session = Depends(get_db_session)):
    if not settings.GOOGLE_AUTH_ENABLED:
        raise HTTPException(status_code=503, detail="Google sign-in is unavailable because this domain is not currently supported by Google authentication.")
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured for this environment.")
    state, nonce, verifier = new_secret(), new_secret(), new_secret()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    db.add(OAuthState(state_hash=digest(state), nonce=nonce, verifier=verifier, expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
    db.commit()
    secure = settings.APP_ENV.casefold() == "production"
    same_site = "none" if secure else "lax"
    response.set_cookie("proofmint_oauth_state", state, httponly=True, secure=secure, samesite=same_site, path="/api/v1/auth/google", max_age=600)
    query = urlencode({"client_id": settings.GOOGLE_CLIENT_ID, "redirect_uri": settings.GOOGLE_REDIRECT_URI, "response_type": "code", "scope": "openid email profile", "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account"})
    response.status_code = 302
    response.headers["Location"] = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    return response


@router.get("/google/callback")
async def google_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None, db: Session = Depends(get_db_session)):
    def fail(kind: str):
        result = RedirectResponse(f"{settings.AUTH_FRONTEND_URL.rstrip('/')}/auth?error={kind}", status_code=303)
        result.delete_cookie("proofmint_oauth_state", path="/api/v1/auth/google")
        return result

    if error or not code or not state or not hmac.compare_digest(state, request.cookies.get("proofmint_oauth_state", "")):
        return fail("google_cancelled" if error == "access_denied" else "google_state_invalid")
    record = db.scalar(select(OAuthState).where(OAuthState.state_hash == digest(state)))
    if record is None or record.expires_at <= datetime.now(timezone.utc):
        return fail("google_state_expired")
    db.delete(record)
    db.commit()
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET or not settings.GOOGLE_REDIRECT_URI:
        return fail("google_not_configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": settings.GOOGLE_CLIENT_ID, "client_secret": settings.GOOGLE_CLIENT_SECRET.get_secret_value(), "redirect_uri": settings.GOOGLE_REDIRECT_URI, "grant_type": "authorization_code", "code_verifier": record.verifier})
            if not token_response.is_success:
                return fail("google_exchange_failed")
            identity_token = token_response.json().get("id_token")
            if not isinstance(identity_token, str):
                return fail("google_identity_missing")
            verified = await client.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": identity_token})
            if not verified.is_success:
                return fail("google_identity_invalid")
            claims = verified.json()
    except httpx.RequestError:
        return fail("google_unavailable")
    try:
        valid = claims.get("aud") == settings.GOOGLE_CLIENT_ID and claims.get("iss") in {"accounts.google.com", "https://accounts.google.com"} and int(claims.get("exp", 0)) > int(time.time()) and claims.get("nonce") == record.nonce and str(claims.get("email_verified", "")).casefold() == "true"
    except (TypeError, ValueError):
        valid = False
    subject, email = claims.get("sub"), normalize_email(str(claims.get("email", "")))
    if not valid or not isinstance(subject, str) or not subject or not _EMAIL.fullmatch(email):
        return fail("google_identity_invalid")
    user = db.scalar(select(User).where(User.google_subject == subject))
    if user is None:
        if db.scalar(select(User.id).where(User.email == email)):
            return fail("account_link_required")
        names = str(claims.get("name", "")).strip().split()
        user = User(first_name=str(claims.get("given_name") or (names[0] if names else "User"))[:100], surname=str(claims.get("family_name") or " ".join(names[1:]))[:100], email=email, google_subject=subject)
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return fail("account_link_required")
    token, csrf = new_secret(), new_secret()
    db.add(AuthSession(user_id=user.id, role="user", token_hash=digest(token), csrf_hash=digest(csrf), expires_at=datetime.now(timezone.utc) + timedelta(hours=12)))
    db.commit()
    secure = settings.APP_ENV.casefold() == "production"
    same_site = "none" if secure else "lax"
    result = RedirectResponse(f"{settings.AUTH_FRONTEND_URL.rstrip('/')}/auth?google=success", status_code=303)
    result.set_cookie(SESSION_COOKIE, token, httponly=True, secure=secure, samesite=same_site, path="/", max_age=43200)
    result.set_cookie(CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite=same_site, path="/", max_age=43200)
    result.delete_cookie("proofmint_oauth_state", path="/api/v1/auth/google")
    return result
