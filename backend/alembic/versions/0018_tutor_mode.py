"""Tutor Mode (Prompt 34): tutor_sessions / tutor_turns / tutor_concept_states and plan quotas.

Revision ID: 0018_tutor_mode
Revises: 0017_revision_sheets
Create Date: 2026-10-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018_tutor_mode"
down_revision = "0017_revision_sheets"
branch_labels = None
depends_on = None

ALL_LEVELS = ["beginner", "intermediate", "exam_ready"]
ALL_LANGUAGES = ["en", "ur", "roman_ur"]

# A missing key means "unlimited / everything allowed" in this app, so seed every default plan
# explicitly - otherwise existing plans would get unlimited tutor sessions.
PLAN_LIMITS = {
    "free": {
        "tutor_sessions_per_week": 3,
        "tutor_max_turns_per_session": 15,
        "tutor_levels_allowed": ["beginner", "intermediate"],
        "tutor_languages_allowed": ["en"],
    },
    "pro": {
        "tutor_sessions_per_week": 50,
        "tutor_max_turns_per_session": 40,
        "tutor_levels_allowed": ALL_LEVELS,
        "tutor_languages_allowed": ALL_LANGUAGES,
    },
    "enterprise": {
        "tutor_sessions_per_week": None,
        "tutor_max_turns_per_session": 60,
        "tutor_levels_allowed": ALL_LEVELS,
        "tutor_languages_allowed": ALL_LANGUAGES,
    },
}


def upgrade() -> None:
    op.create_table(
        "tutor_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("document_ids", sa.JSON(), nullable=False),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("level", sa.String(), nullable=False, server_default="intermediate"),
        sa.Column("language", sa.String(), nullable=False, server_default="en"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_turns", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("plan", sa.JSON(), nullable=True),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tutor_sessions_user_id", "tutor_sessions", ["user_id"])

    op.create_table(
        "tutor_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tutor_sessions.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("turn_type", sa.String(), nullable=True),
        sa.Column("hint_level", sa.Integer(), nullable=True),
        sa.Column("verdict", sa.String(), nullable=True),
        sa.Column("source_refs", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tutor_turns_session_id", "tutor_turns", ["session_id"])

    op.create_table(
        "tutor_concept_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tutor_sessions.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("concept_index", sa.Integer(), nullable=False),
        sa.Column("concept", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revealed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mastered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("phase", sa.String(), nullable=False, server_default="starter"),
        sa.Column("hint_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_question", sa.Text(), nullable=True),
        sa.Column("check_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_tutor_concept_states_session_id", "tutor_concept_states", ["session_id"])

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
    op.drop_index("ix_tutor_concept_states_session_id", table_name="tutor_concept_states")
    op.drop_table("tutor_concept_states")
    op.drop_index("ix_tutor_turns_session_id", table_name="tutor_turns")
    op.drop_table("tutor_turns")
    op.drop_index("ix_tutor_sessions_user_id", table_name="tutor_sessions")
    op.drop_table("tutor_sessions")
