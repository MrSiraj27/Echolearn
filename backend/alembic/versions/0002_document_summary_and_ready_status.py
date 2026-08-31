"""add document summary/suggested_questions columns and 'ready' status

Revision ID: 0002_summary_ready
Revises: 0001_initial
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_summary_ready"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'ready'")
    op.add_column("documents", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("suggested_questions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "suggested_questions")
    op.drop_column("documents", "summary")
    # Postgres doesn't support removing an enum value; leaving 'ready' in place on downgrade.
