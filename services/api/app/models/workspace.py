"""Logical workflow workspace for session-scoped demo data."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="session", server_default=text("'session'"))
