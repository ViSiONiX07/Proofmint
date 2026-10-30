"""Reusable real-session fixtures for isolated API tests."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import CSRF_COOKIE, SESSION_COOKIE, digest, new_secret
from app.core.database import get_db_session
import app.main as main_module
from app.main import app
from app.models.identity import AuthSession, User
from app.models.workspace import Workspace


def install_authenticated_user(engine, client, *, email="test-user@example.test"):
    """Bind auth lookup to *engine*, persist a real session, and set client cookies."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    token, csrf = new_secret(), new_secret()
    with Session(engine, expire_on_commit=False) as db:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            user = User(first_name="Test", surname="User", email=email, password_hash="fixture-password-hash")
            db.add(user)
            db.flush()
        db.add(AuthSession(
            user_id=user.id,
            role="user",
            token_hash=digest(token),
            csrf_hash=digest(csrf),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        for workspace in db.query(Workspace).filter(
            Workspace.kind == "session", Workspace.owner_user_id.is_(None)
        ).all():
            workspace.owner_user_id = user.id
        db.commit()

    def override_session():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db_session] = override_session
    # AuthzMiddleware performs its own session lookup through this factory.
    # Point that lookup at the same isolated engine as FastAPI dependencies.
    main_module.get_session_factory = lambda: factory
    client.cookies.set(SESSION_COOKIE, token)
    client.cookies.set(CSRF_COOKIE, csrf)
    client.headers.update({"X-CSRF-Token": csrf})
    return user.id, factory


def remove_authenticated_user(engine):
    app.dependency_overrides.pop(get_db_session, None)
    engine.dispose()
