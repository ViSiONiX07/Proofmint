"""Add user identities, revocable sessions, and nullable workspace ownership.

Revision ID: 0009_auth_users_sessions
Revises: 0008_persisted_repair_decisions
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_auth_users_sessions"
down_revision = "0008_persisted_repair_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("surname", sa.String(100), server_default="", nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=True),
        sa.Column("google_subject", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("google_subject"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_google_subject", "users", ["google_subject"])
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        sa.CheckConstraint("(role = 'user' AND user_id IS NOT NULL) OR (role = 'judge' AND user_id IS NULL)", name="ck_auth_sessions_role_user"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("verifier", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index("ix_oauth_states_state_hash", "oauth_states", ["state_hash"])
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])
    op.add_column("workspaces", sa.Column("owner_user_id", sa.Uuid(), nullable=True))
    op.add_column("workspaces", sa.Column("owner_judge_session_id", sa.Uuid(), nullable=True))
    op.create_check_constraint("ck_workspaces_single_owner", "workspaces", "NOT (owner_user_id IS NOT NULL AND owner_judge_session_id IS NOT NULL)")
    op.create_foreign_key("fk_workspaces_owner_user", "workspaces", "users", ["owner_user_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_workspaces_judge_session", "workspaces", "auth_sessions", ["owner_judge_session_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"])
    op.create_index("ix_workspaces_owner_judge_session_id", "workspaces", ["owner_judge_session_id"])


def downgrade() -> None:
    op.drop_index("ix_workspaces_owner_judge_session_id", table_name="workspaces")
    op.drop_index("ix_workspaces_owner_user_id", table_name="workspaces")
    op.drop_constraint("fk_workspaces_judge_session", "workspaces", type_="foreignkey")
    op.drop_constraint("fk_workspaces_owner_user", "workspaces", type_="foreignkey")
    op.drop_constraint("ck_workspaces_single_owner", "workspaces", type_="check")
    op.drop_column("workspaces", "owner_judge_session_id")
    op.drop_column("workspaces", "owner_user_id")
    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_index("ix_oauth_states_state_hash", table_name="oauth_states")
    op.drop_table("oauth_states")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_users_google_subject", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
