"""Revision sheets (Prompt 33): revision_sheets table and the plan quotas that gate it.

Revision ID: 0017_revision_sheets
Revises: 0016_language_explain
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017_revision_sheets"
down_revision = "0016_language_explain"
branch_labels = None
depends_on = None

# A missing limit key means "unlimited"/"allowed" in this app, so every default plan is seeded
# explicitly. Free: 2 a month, one page, English only. Pro: 30 a month, two pages, all
# languages and weak-spot mode. Enterprise: unlimited.
PLAN_LIMITS = {
    "free": {"revision_sheets_per_month": 2, "revision_sheet_max_pages": 1, "revision_sheet_advanced": False},
    "pro": {"revision_sheets_per_month": 30, "revision_sheet_max_pages": 2, "revision_sheet_advanced": True},
    "enterprise": {"revision_sheets_per_month": None, "revision_sheet_max_pages": 2, "revision_sheet_advanced": True},
}


def upgrade() -> None:
    status_enum = postgresql.ENUM("queued", "generating", "ready", "failed", name="revision_sheet_status")
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "revision_sheets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("document_ids", sa.JSON(), nullable=False),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("topics", sa.JSON(), nullable=True),
        sa.Column("language", sa.String(), nullable=False, server_default="en"),
        sa.Column("page_target", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("include_weak_spots", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("pdf_path", sa.String(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("queued", "generating", "ready", "failed", name="revision_sheet_status", create_type=False),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_revision_sheets_user_id", "revision_sheets", ["user_id"])
    op.create_index("ix_revision_sheets_content_hash", "revision_sheets", ["content_hash"])

    plans = sa.table("plans", sa.column("slug", sa.String), sa.column("limits", postgresql.JSON))
    conn = op.get_bind()
    for slug, new_limits in PLAN_LIMITS.items():
        row = conn.execute(sa.select(plans.c.limits).where(plans.c.slug == slug)).first()
        if row is None:
            continue
        limits = dict(row[0] or {})
        for key, value in new_limits.items():
            limits.setdefault(key, value)  # never overwrite a value an admin already set
        conn.execute(sa.update(plans).where(plans.c.slug == slug).values(limits=limits))


def downgrade() -> None:
    op.drop_index("ix_revision_sheets_content_hash", table_name="revision_sheets")
    op.drop_index("ix_revision_sheets_user_id", table_name="revision_sheets")
    op.drop_table("revision_sheets")
    postgresql.ENUM(name="revision_sheet_status").drop(op.get_bind(), checkfirst=True)
