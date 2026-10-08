"""Urdu / Roman Urdu explanations: users.preferred_language, message_translations cache,
and the language_explanations_per_day quota seeded onto the default plans.

Revision ID: 0016_language_explain
Revises: 0015_fish_voice_model_id
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_language_explain"
down_revision = "0015_fish_voice_model_id"
branch_labels = None
depends_on = None

# A missing limit key means "unlimited" in this app, so seed every default plan explicitly
# rather than leaving existing plans with no cap on a feature that costs LLM calls.
QUOTA_KEY = "language_explanations_per_day"
PLAN_QUOTAS = {"free": 10, "pro": 200, "enterprise": None}


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_language", sa.String(), nullable=False, server_default="en"))

    op.create_table(
        "message_translations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("fidelity_warning", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("message_id", "language", "mode", name="uq_message_translation"),
    )
    op.create_index("ix_message_translations_message_id", "message_translations", ["message_id"])

    plans = sa.table("plans", sa.column("slug", sa.String), sa.column("limits", postgresql.JSON))
    conn = op.get_bind()
    for slug, value in PLAN_QUOTAS.items():
        row = conn.execute(sa.select(plans.c.limits).where(plans.c.slug == slug)).first()
        if row is None:
            continue
        limits = dict(row[0] or {})
        limits.setdefault(QUOTA_KEY, value)
        conn.execute(sa.update(plans).where(plans.c.slug == slug).values(limits=limits))


def downgrade() -> None:
    op.drop_index("ix_message_translations_message_id", table_name="message_translations")
    op.drop_table("message_translations")
    op.drop_column("users", "preferred_language")
