"""Add persistent session workspaces and assign legacy rows explicitly.

Revision ID: 0003_session_workspaces
Revises: 0002_persisted_audits
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_session_workspaces"
down_revision = "0002_persisted_audits"
branch_labels = None
depends_on = None

LEGACY_WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("kind", sa.String(length=30), server_default=sa.text("'session'"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(sa.text(
        "INSERT INTO workspaces (id, kind) VALUES (CAST(:id AS uuid), 'legacy')"
    ).bindparams(id=LEGACY_WORKSPACE_ID))

    for table in ("guideline_documents", "imported_facts", "imported_terms", "audit_runs"):
        op.add_column(table, sa.Column("workspace_id", sa.Uuid(), nullable=True))
        op.execute(sa.text(f"UPDATE {table} SET workspace_id = CAST(:id AS uuid) WHERE workspace_id IS NULL").bindparams(id=LEGACY_WORKSPACE_ID))
        op.alter_column(table, "workspace_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_workspace_id_workspaces", table, "workspaces",
            ["workspace_id"], ["id"], ondelete="RESTRICT",
        )
        op.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])


def downgrade() -> None:
    for table in ("audit_runs", "imported_terms", "imported_facts", "guideline_documents"):
        op.drop_index(f"ix_{table}_workspace_id", table_name=table)
        op.drop_constraint(f"fk_{table}_workspace_id_workspaces", table, type_="foreignkey")
        op.drop_column(table, "workspace_id")
    op.drop_table("workspaces")
