"""Lazy SQLAlchemy engine and request-scoped session management."""

from collections.abc import Generator
from threading import RLock

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when code requests persistence without PostgreSQL configuration."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_lock = RLock()


def get_engine() -> Engine:
    """Create the PostgreSQL engine on first use, never during API import/startup."""
    global _engine
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is None:
            database_url = settings.get_database_url()
            if database_url is None:
                raise DatabaseNotConfiguredError(
                    "PostgreSQL is not configured. Set DATABASE_URL or POSTGRES_SERVER, "
                    "POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB before using persistence."
                )
            _engine = create_engine(database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return a reusable factory; creating it does not connect to PostgreSQL."""
    global _session_factory
    if _session_factory is not None:
        return _session_factory
    with _lock:
        if _session_factory is None:
            _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI-compatible dependency that always closes its session."""
    with get_session_factory()() as session:
        yield session


def dispose_database() -> None:
    """Dispose cached engine state (also useful for controlled test isolation)."""
    global _engine, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _session_factory = None
