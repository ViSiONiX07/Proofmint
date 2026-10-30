from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from sqlalchemy import select
from datetime import datetime, timezone
import json
from uuid import UUID

from app.core.auth import CSRF_COOKIE, SESSION_COOKIE, Principal, digest, require_workspace_access
from app.core.database import DatabaseNotConfiguredError, get_session_factory
from app.models.identity import AuthSession, User
from app.core.config import settings
from app.api.health import router as health_router
from app.api.guidelines import router as guidelines_router
from app.api.imports import router as imports_router
from app.api.candidate_rules import router as candidate_rules_router
from app.api.import_review import router as import_review_router
from app.api.audits import router as audits_router
from app.api.workspaces import router as workspaces_router
from app.api.auth import router as auth_router
from app.core.upload_limits import GuidelineUploadBodyLimitMiddleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Proofmint AI Brand Verification Workspace API.",
    docs_url=None if settings.APP_ENV.casefold() == "production" else "/docs",
    redoc_url=None if settings.APP_ENV.casefold() == "production" else "/redoc",
    openapi_url=None if settings.APP_ENV.casefold() == "production" else "/openapi.json",
)

app.add_middleware(GuidelineUploadBodyLimitMiddleware)

@app.exception_handler(DatabaseNotConfiguredError)
async def database_not_configured(_request: Request, _exc: DatabaseNotConfiguredError):
    return JSONResponse(
        {"detail": "Authentication storage is unavailable. Configure PostgreSQL and apply the database migrations before signing in."},
        status_code=503,
    )


class AuthzMiddleware:
    """Enforce session, CSRF, and workspace ownership on API requests."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        path = request.url.path
        api_prefix = "/api/v1/"
        exempt = path.startswith("/api/v1/auth/") or path in {"/api/v1/health", "/api/v1/evaluation"}
        if not path.startswith(api_prefix) or exempt:
            await self.app(scope, receive, send)
            return
        raw_token = request.cookies.get(SESSION_COOKIE)
        if not raw_token:
            await JSONResponse({"detail": "Sign in to access this resource."}, status_code=401)(scope, receive, send)
            return
        body = b""
        should_replay = False
        try:
            factory = get_session_factory()
            with factory() as db:
                session = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(raw_token)))
                now = datetime.now(timezone.utc)
                if session is None or session.revoked_at is not None or session.expires_at.replace(tzinfo=session.expires_at.tzinfo or timezone.utc) <= now:
                    await JSONResponse({"detail": "Your session has expired. Sign in again."}, status_code=401)(scope, receive, send)
                    return
                user = db.get(User, session.user_id) if session.user_id else None
                if session.role == "user" and user is None or session.role == "judge" and session.user_id is not None:
                    await JSONResponse({"detail": "The session is invalid."}, status_code=401)(scope, receive, send)
                    return
                if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                    csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
                    csrf_header = request.headers.get("x-csrf-token", "")
                    import hmac
                    if not csrf_cookie or not hmac.compare_digest(csrf_cookie, csrf_header) or not hmac.compare_digest(digest(csrf_cookie), session.csrf_hash):
                        await JSONResponse({"detail": "The request could not be verified. Refresh and try again."}, status_code=403)(scope, receive, send)
                        return
                workspace_value = request.query_params.get("workspace_id")
                if not workspace_value and path.startswith("/api/v1/workspaces/"):
                    workspace_value = path.rsplit("/", 1)[-1]
                if path == "/api/v1/audits" and request.method == "POST":
                    try:
                        if int(request.headers.get("content-length", "0")) > 1_000_000:
                            await JSONResponse({"detail": "Audit payload exceeds the supported size."}, status_code=413)(scope, receive, send)
                            return
                    except ValueError:
                        await JSONResponse({"detail": "Audit payload length is invalid."}, status_code=400)(scope, receive, send)
                        return
                    body = await request.body()
                    if len(body) > 1_000_000:
                        await JSONResponse({"detail": "Audit payload exceeds the supported size."}, status_code=413)(scope, receive, send)
                        return
                    should_replay = True
                    try:
                        payload = json.loads(body)
                        body_workspace = str(payload.get("workspace_id", "")) if isinstance(payload, dict) else ""
                    except (ValueError, AttributeError):
                        body_workspace = ""
                    if workspace_value and workspace_value != body_workspace:
                        await JSONResponse({"detail": "Workspace context does not match the audit request."}, status_code=400)(scope, receive, send)
                        return
                    workspace_value = body_workspace
                principal = Principal(session=session, user=user)
                scope.setdefault("state", {})["principal"] = principal
                if workspace_value:
                    try:
                        require_workspace_access(db, UUID(workspace_value), principal)
                    except (ValueError, HTTPException) as exc:
                        status = exc.status_code if isinstance(exc, HTTPException) else 404
                        detail = exc.detail if isinstance(exc, HTTPException) else "Workspace was not found."
                        await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
                        return
                elif path not in {"/api/v1/guidelines/ingest", "/api/v1/facts/import", "/api/v1/terms/import"}:
                    await JSONResponse({"detail": "A workspace context is required."}, status_code=400)(scope, receive, send)
                    return
        except DatabaseNotConfiguredError:
            await JSONResponse({"detail": "Authentication storage is unavailable."}, status_code=503)(scope, receive, send)
            return

        async def replay_receive():
            nonlocal body, should_replay
            if should_replay:
                should_replay = False
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay_receive if body else receive, send)

app.include_router(health_router, prefix=settings.API_V1_STR, tags=["Health"])
app.include_router(guidelines_router, prefix=settings.API_V1_STR, tags=["Guidelines"])
app.include_router(imports_router, prefix=settings.API_V1_STR, tags=["Imports"])
app.include_router(candidate_rules_router, prefix=settings.API_V1_STR, tags=["Candidate Rules"])
app.include_router(import_review_router, prefix=settings.API_V1_STR, tags=["Imported Row Review"])
app.include_router(audits_router, prefix=settings.API_V1_STR, tags=["Audits"])
app.include_router(workspaces_router, prefix=settings.API_V1_STR, tags=["Workspaces"])
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.add_middleware(AuthzMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.BACKEND_CORS_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "X-CSRF-Token"])

@app.get("/")
async def root():
    return {
        "product": "Proofmint",
        "tagline": "Nothing ships unproven.",
        "status": "online",
        "docs": "/docs"
    }
