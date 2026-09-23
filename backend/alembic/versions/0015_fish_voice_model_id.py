"""users.fish_voice_model_id: cached Fish Audio voice model id for the current sample.

Revision ID: 0015_fish_voice_model_id
Revises: 0014_voice_pregenerate
Create Date: 2026-09-23
"""
import sqlalchemy as sa
from alembic import op

revision = "0015_fish_voice_model_id"
down_revision = "0014_voice_pregenerate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("fish_voice_model_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "fish_voice_model_id")
