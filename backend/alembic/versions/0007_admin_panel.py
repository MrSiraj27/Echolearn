"""add admin panel: user admin/suspend fields + admin_audit_logs, content_reports,
api_call_logs, system_config tables

Revision ID: 0007_admin
Revises: 0006_analytics
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_admin"
down_revision = "0006_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("admin_role", sa.String, nullable=True))
    op.add_column("users", sa.Column("is_suspended", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("admin_notes", sa.Text, nullable=True))

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("admin_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("target_id", sa.String, nullable=True),
        sa.Column("details", postgresql.JSON, nullable=True),
        sa.Column("ip_address", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "content_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reporter_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.String, nullable=False),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("auto_flagged", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "api_call_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("endpoint_or_purpose", sa.String, nullable=False),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "system_config",
        sa.Column("key", sa.String, primary_key=True),
        sa.Column("value", postgresql.JSON, nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("system_config")
    op.drop_table("api_call_logs")
    op.drop_table("content_reports")
    op.drop_table("admin_audit_logs")
    op.drop_column("users", "admin_notes")
    op.drop_column("users", "is_suspended")
    op.drop_column("users", "admin_role")
    op.drop_column("users", "is_admin")
