"""Daily Spaced Repetition Review (Prompt 30) + Exam/Deadline-Aware Study Planner
(Prompt 29): review_cards, review_card_states, study_plans, study_sessions, plus
users.daily_review_cap.

Every user_id FK cascades on user delete, matching the fix in 0010 for
workspaces/quizzes and 0011 for voice_clone_jobs. review_cards.document_id cascades
(a card is meaningless once its source document is gone). study_plans.workspace_id is
SET NULL, matching chats.workspace_id's existing convention — deleting a workspace is a
grouping change, not a reason to destroy an in-progress plan. study_sessions.quiz_id is
SET NULL for the same reason: losing the linked quiz shouldn't delete the session.

Revision ID: 0012_study_review
Revises: 0011_voice_clone_jobs
Create Date: 2026-09-18
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_study_review"
down_revision = "0011_voice_clone_jobs"
branch_labels = None
depends_on = None

review_question_type = postgresql.ENUM(
    "multiple_choice", "short_answer", "true_false", name="review_question_type", create_type=False
)
study_plan_status = postgresql.ENUM("active", "completed", "abandoned", name="study_plan_status", create_type=False)
study_session_type = postgresql.ENUM(
    "learn", "review", "quiz", "checkpoint", name="study_session_type", create_type=False
)
study_session_status = postgresql.ENUM(
    "pending", "completed", "skipped", name="study_session_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    review_question_type.create(bind, checkfirst=True)
    study_plan_status.create(bind, checkfirst=True)
    study_session_type.create(bind, checkfirst=True)
    study_session_status.create(bind, checkfirst=True)

    op.add_column("users", sa.Column("daily_review_cap", sa.Integer(), nullable=True))

    op.create_table(
        "review_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("question_type", review_question_type, nullable=False, server_default="short_answer"),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("source_chunk_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_review_cards_user_id", "review_cards", ["user_id"])

    op.create_table(
        "review_card_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "review_card_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("review_cards.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_review_date", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_review_card_states_user_due", "review_card_states", ["user_id", "next_review_date"])

    op.create_table(
        "study_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("document_ids", sa.JSON(), nullable=True),
        sa.Column(
            "workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("daily_study_minutes", sa.Integer(), nullable=False),
        sa.Column("status", study_plan_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_study_plans_user_id", "study_plans", ["user_id"])

    op.create_table(
        "study_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("topic_title", sa.String(), nullable=False),
        sa.Column("topic_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_chunks", sa.JSON(), nullable=False),
        sa.Column("session_type", study_session_type, nullable=False),
        sa.Column("status", study_session_status, nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quiz_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quizzes.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_study_sessions_plan_id", "study_sessions", ["plan_id"])
    op.create_index("ix_study_sessions_plan_date", "study_sessions", ["plan_id", "scheduled_date"])


def downgrade() -> None:
    op.drop_index("ix_study_sessions_plan_date", table_name="study_sessions")
    op.drop_index("ix_study_sessions_plan_id", table_name="study_sessions")
    op.drop_table("study_sessions")

    op.drop_index("ix_study_plans_user_id", table_name="study_plans")
    op.drop_table("study_plans")

    op.drop_index("ix_review_card_states_user_due", table_name="review_card_states")
    op.drop_table("review_card_states")

    op.drop_index("ix_review_cards_user_id", table_name="review_cards")
    op.drop_table("review_cards")

    op.drop_column("users", "daily_review_cap")

    bind = op.get_bind()
    study_session_status.drop(bind, checkfirst=True)
    study_session_type.drop(bind, checkfirst=True)
    study_plan_status.drop(bind, checkfirst=True)
    review_question_type.drop(bind, checkfirst=True)
