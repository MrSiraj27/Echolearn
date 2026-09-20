"""Voice cloning: job table + cached sample hash on users.

Adds VoiceCloneJob (Prompt 28 — async CPU voice cloning). user_id cascades on user
delete (matching the fix in 0010 for workspaces/quizzes — this table must not survive
its owning user and must not raise an IntegrityError during admin user-deletion).
message_id is SET NULL on message delete: a generated clip should still be servable/
cached even if the source message later disappears, so it must not cascade-delete.

Revision ID: 0011_voice_clone_jobs
Revises: 0010_workspace_quiz_user_cascade
Create Date: 2026-09-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_voice_clone_jobs"
down_revision = "0010_workspace_quiz_user_cascade"
branch_labels = None
depends_on = None

voice_clone_job_status = postgresql.ENUM(
    "queued", "processing", "done", "failed", name="voice_clone_job_status", create_type=False
)


def upgrade() -> None:
    voice_clone_job_status.create(op.get_bind(), checkfirst=True)

    op.add_column("users", sa.Column("cloned_voice_sample_hash", sa.String(), nullable=True))

    op.create_table(
        "voice_clone_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("reference_audio_hash", sa.String(), nullable=False),
        sa.Column("text_hash", sa.String(), nullable=False),
        sa.Column(
            "status",
            voice_clone_job_status,
            nullable=False,
            server_default="queued",
        ),
        sa.Column("output_audio_path", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_voice_clone_jobs_lookup",
        "voice_clone_jobs",
        ["user_id", "reference_audio_hash", "text_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_voice_clone_jobs_lookup", table_name="voice_clone_jobs")
    op.drop_table("voice_clone_jobs")
    op.drop_column("users", "cloned_voice_sample_hash")
    voice_clone_job_status.drop(op.get_bind(), checkfirst=True)
