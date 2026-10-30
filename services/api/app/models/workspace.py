"""Logical workflow workspace for session-scoped demo data."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (CheckConstraint("NOT (owner_user_id IS NOT NULL AND owner_judge_session_id IS NOT NULL)", name="ck_workspaces_single_owner"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="session", server_default=text("'session'"))
    # Null means legacy/anonymous historical data. Such workspaces are inaccessible
    # through authenticated APIs until an explicit safe ownership process is designed.
    owner_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    owner_judge_session_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("auth_sessions.id", ondelete="CASCADE"), index=True)
