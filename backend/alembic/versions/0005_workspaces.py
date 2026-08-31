"""add workspaces, workspace_documents tables and chats.workspace_id

Revision ID: 0005_workspaces
Revises: 0004_folders
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_workspaces"
down_revision = "0004_folders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "workspace_documents",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), primary_key=True),
    )
    op.add_column("chats", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_chats_workspace_id", "chats", "workspaces", ["workspace_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_chats_workspace_id", "chats", type_="foreignkey")
    op.drop_column("chats", "workspace_id")
    op.drop_table("workspace_documents")
    op.drop_table("workspaces")
