"""plans, quotas & full admin control: Plan/UsageEvent/RateLimitViolation tables,
user plan_id/custom_limits, rename is_suspended -> is_blocked + block metadata

Revision ID: 0008_plans_quotas
Revises: 0007_admin
Create Date: 2026-08-31
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_plans_quotas"
down_revision = "0007_admin"
branch_labels = None
depends_on = None


FREE_LIMITS = {
    "max_documents": 5,
    "max_file_size_mb": 10,
    "max_audio_video_minutes": 10,
    "messages_per_window": 30,
    "message_window_hours": 5,
    "max_workspaces": 1,
    "quiz_generations_per_month": 5,
    "tts_uses_per_day": 20,
    "diagrams_infographics_per_month": 3,
    "max_storage_mb": 100,
    "priority_processing": False,
}

PRO_LIMITS = {
    "max_documents": 100,
    "max_file_size_mb": 50,
    "max_audio_video_minutes": 120,
    "messages_per_window": 300,
    "message_window_hours": 5,
    "max_workspaces": 10,
    "quiz_generations_per_month": None,
    "tts_uses_per_day": None,
    "diagrams_infographics_per_month": None,
    "max_storage_mb": 5000,
    "priority_processing": True,
}

ENTERPRISE_LIMITS = {
    "max_documents": None,
    "max_file_size_mb": 200,
    "max_audio_video_minutes": None,
    "messages_per_window": None,
    "message_window_hours": 5,
    "max_workspaces": None,
    "quiz_generations_per_month": None,
    "tts_uses_per_day": None,
    "diagrams_infographics_per_month": None,
    "max_storage_mb": None,
    "priority_processing": True,
}


def upgrade() -> None:
    # --- users: rename is_suspended -> is_blocked, add block metadata + plan fields ---
    op.alter_column("users", "is_suspended", new_column_name="is_blocked")
    op.add_column("users", sa.Column("blocked_reason", sa.Text, nullable=True))
    op.add_column("users", sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("blocked_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("users", sa.Column("custom_limits", postgresql.JSON, nullable=True))

    # --- plans ---
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("slug", sa.String, unique=True, nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("limits", postgresql.JSON, nullable=False),
        sa.Column("price_monthly", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.add_column("users", sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id"), nullable=True))

    # --- usage_events ---
    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_usage_events_user_type_created", "usage_events", ["user_id", "event_type", "created_at"]
    )

    # --- rate_limit_violations ---
    op.create_table(
        "rate_limit_violations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # --- seed the three default plans ---
    plans_table = sa.table(
        "plans",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("is_default", sa.Boolean),
        sa.column("limits", postgresql.JSON),
        sa.column("price_monthly", sa.Float),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    free_id = uuid.uuid4()
    pro_id = uuid.uuid4()
    enterprise_id = uuid.uuid4()

    now = sa.func.now()

    op.bulk_insert(
        plans_table,
        [
            {
                "id": free_id,
                "name": "Starter",
                "slug": "free",
                "is_default": True,
                "limits": FREE_LIMITS,
                "price_monthly": 0,
            },
            {
                "id": pro_id,
                "name": "Scholar",
                "slug": "pro",
                "is_default": False,
                "limits": PRO_LIMITS,
                "price_monthly": 19,
            },
            {
                "id": enterprise_id,
                "name": "Institution",
                "slug": "enterprise",
                "is_default": False,
                "limits": ENTERPRISE_LIMITS,
                "price_monthly": None,
            },
        ],
    )
    # created_at/updated_at have no server_default (matches other tables in this app,
    # e.g. admin_audit_logs) — set them explicitly here since bulk_insert bypasses the
    # ORM-level Python defaults.
    op.execute(f"UPDATE plans SET created_at = now(), updated_at = now() WHERE id IN "
               f"('{free_id}', '{pro_id}', '{enterprise_id}')")

    # Backfill every existing user onto the default (Free) plan.
    op.execute(f"UPDATE users SET plan_id = '{free_id}' WHERE plan_id IS NULL")


def downgrade() -> None:
    op.drop_column("users", "plan_id")
    op.drop_table("rate_limit_violations")
    op.drop_index("ix_usage_events_user_type_created", table_name="usage_events")
    op.drop_table("usage_events")
    op.drop_table("plans")
    op.drop_column("users", "custom_limits")
    op.drop_column("users", "blocked_by")
    op.drop_column("users", "blocked_at")
    op.drop_column("users", "blocked_reason")
    op.alter_column("users", "is_blocked", new_column_name="is_suspended")
