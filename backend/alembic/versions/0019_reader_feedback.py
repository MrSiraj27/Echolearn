"""Document failure reasons + file size, and answer feedback.

documents.error_message  why processing failed, shown to the user (NULL otherwise)
documents.file_size      bytes of the original upload (NULL for rows created before this)
message_feedback         helpful / not_helpful / incorrect per user per assistant message

Purely additive: no existing data is changed or removed.

Revision ID: 0019_reader_feedback
Revises: 0018_tutor_mode
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019_reader_feedback"
down_revision = "0018_tutor_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("file_size", sa.BigInteger(), nullable=True))

    op.create_table(
        "message_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("rating", sa.String(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("message_id", "user_id", name="uq_message_feedback_message_user"),
    )
    op.create_index("ix_message_feedback_message_id", "message_feedback", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_message_feedback_message_id", table_name="message_feedback")
    op.drop_table("message_feedback")
    op.drop_column("documents", "file_size")
    op.drop_column("documents", "error_message")
