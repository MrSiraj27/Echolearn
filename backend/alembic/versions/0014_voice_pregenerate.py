"""users.voice_pregenerate: opt-in background cloning of new assistant replies.

Revision ID: 0014_voice_pregenerate
Revises: 0013_practice_papers
Create Date: 2026-09-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0014_voice_pregenerate"
down_revision = "0013_practice_papers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("voice_pregenerate", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("users", "voice_pregenerate")
