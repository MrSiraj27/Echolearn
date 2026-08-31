"""add document_folders table and documents.folder_id

Revision ID: 0004_folders
Revises: 0003_quizzes
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_folders"
down_revision = "0003_quizzes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.add_column("documents", sa.Column("folder_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_documents_folder_id", "documents", "document_folders", ["folder_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_documents_folder_id", "documents", type_="foreignkey")
    op.drop_column("documents", "folder_id")
    op.drop_table("document_folders")
