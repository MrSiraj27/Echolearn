"""Practice Paper Generator (Prompt 31): past_papers, practice_papers,
practice_paper_attempts.

Every user_id FK cascades on user delete (matching 0010-0012). past_papers.document_id
cascades: an analysis row is meaningless once its document is gone. practice_papers keep
their source documents in a JSON list (no FK), so deleting a source document never
destroys an already-generated paper. practice_paper_attempts cascade from both the paper
and the user.

Revision ID: 0013_practice_papers
Revises: 0012_study_review
Create Date: 2026-09-19
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_practice_papers"
down_revision = "0012_study_review"
branch_labels = None
depends_on = None

past_paper_analysis_status = postgresql.ENUM(
    "pending", "analyzing", "ready", "failed", name="past_paper_analysis_status", create_type=False
)
practice_paper_status = postgresql.ENUM(
    "generating", "ready", "failed", name="practice_paper_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    past_paper_analysis_status.create(bind, checkfirst=True)
    practice_paper_status.create(bind, checkfirst=True)

    op.create_table(
        "past_papers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("exam_name", sa.String(), nullable=True),
        sa.Column("extracted_pattern", sa.JSON(), nullable=True),
        sa.Column("analysis_status", past_paper_analysis_status, nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_past_papers_user_id", "past_papers", ["user_id"])
    op.create_index("ix_past_papers_document_id", "past_papers", ["document_id"])

    op.create_table(
        "practice_papers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("document_ids", sa.JSON(), nullable=False),
        sa.Column("based_on_past_paper_ids", sa.JSON(), nullable=True),
        sa.Column("important_topics", sa.JSON(), nullable=True),
        sa.Column("pattern_config", sa.JSON(), nullable=False),
        sa.Column("pattern_source", sa.String(), nullable=False, server_default="standard"),
        sa.Column("pattern_note", sa.String(), nullable=True),
        sa.Column("time_allowed_minutes", sa.Integer(), nullable=True),
        sa.Column("generated_content", sa.JSON(), nullable=True),
        sa.Column("status", practice_paper_status, nullable=False, server_default="generating"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_practice_papers_user_id", "practice_papers", ["user_id"])

    op.create_table(
        "practice_paper_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "paper_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("practice_papers.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_practice_paper_attempts_paper_id", "practice_paper_attempts", ["paper_id"])
    op.create_index("ix_practice_paper_attempts_user_id", "practice_paper_attempts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_practice_paper_attempts_user_id", table_name="practice_paper_attempts")
    op.drop_index("ix_practice_paper_attempts_paper_id", table_name="practice_paper_attempts")
    op.drop_table("practice_paper_attempts")

    op.drop_index("ix_practice_papers_user_id", table_name="practice_papers")
    op.drop_table("practice_papers")

    op.drop_index("ix_past_papers_document_id", table_name="past_papers")
    op.drop_index("ix_past_papers_user_id", table_name="past_papers")
    op.drop_table("past_papers")

    bind = op.get_bind()
    practice_paper_status.drop(bind, checkfirst=True)
    past_paper_analysis_status.drop(bind, checkfirst=True)
