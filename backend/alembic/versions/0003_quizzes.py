"""add quizzes and quiz_attempts tables

Revision ID: 0003_quizzes
Revises: 0002_summary_ready
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_quizzes"
down_revision = "0002_summary_ready"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quizzes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_ids", sa.JSON, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("questions", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "quiz_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("quiz_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quizzes.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("answers", sa.JSON, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("quiz_attempts")
    op.drop_table("quizzes")
