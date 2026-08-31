"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    auth_token_type = postgresql.ENUM("verify_email", "reset_password", name="auth_token_type", create_type=False)
    document_status = postgresql.ENUM(
        "uploaded", "parsing", "embedded", "failed", name="document_status", create_type=False
    )
    message_role = postgresql.ENUM("user", "assistant", name="message_role", create_type=False)
    auth_token_type.create(op.get_bind(), checkfirst=True)
    document_status.create(op.get_bind(), checkfirst=True)
    message_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("email", sa.String, nullable=False, unique=True),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("is_verified", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "auth_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String, nullable=False),
        sa.Column("type", auth_token_type, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean, server_default=sa.false()),
    )
    op.create_index("ix_auth_tokens_token", "auth_tokens", ["token"])

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("file_type", sa.String, nullable=False),
        sa.Column("storage_path", sa.String, nullable=False),
        sa.Column("status", document_status, server_default="uploaded"),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "chats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "chat_documents",
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats.id"), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), primary_key=True),
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats.id"), nullable=False),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("chat_documents")
    op.drop_table("chats")
    op.drop_table("documents")
    op.drop_table("auth_tokens")
    op.drop_table("users")
    postgresql.ENUM(name="message_role").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="document_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="auth_token_type").drop(op.get_bind(), checkfirst=True)
