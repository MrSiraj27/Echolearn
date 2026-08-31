"""add query_logs table and messages.content_type

Revision ID: 0006_analytics
Revises: 0005_workspaces
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_analytics"
down_revision = "0005_workspaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "query_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_ids", postgresql.JSON, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("was_answered", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.add_column("messages", sa.Column("content_type", sa.String, nullable=False, server_default="text"))


def downgrade() -> None:
    op.drop_column("messages", "content_type")
    op.drop_table("query_logs")
