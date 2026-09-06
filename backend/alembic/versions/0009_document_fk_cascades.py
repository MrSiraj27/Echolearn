"""Fix missing ON DELETE CASCADE on chat_documents/workspace_documents -> documents.

Without this, deleting a document that belongs to any chat or workspace raises an
unhandled IntegrityError (surfaced to the user as a raw 500), since the junction row
still references the deleted document. content_reports already had CASCADE here;
this brings the other two document junction tables in line with it.

Revision ID: 0009_document_fk_cascades
Revises: 0008_plans_quotas
Create Date: 2026-09-06
"""
from alembic import op

revision = "0009_document_fk_cascades"
down_revision = "0008_plans_quotas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("chat_documents_document_id_fkey", "chat_documents", type_="foreignkey")
    op.create_foreign_key(
        "chat_documents_document_id_fkey",
        "chat_documents",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("workspace_documents_document_id_fkey", "workspace_documents", type_="foreignkey")
    op.create_foreign_key(
        "workspace_documents_document_id_fkey",
        "workspace_documents",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("workspace_documents_document_id_fkey", "workspace_documents", type_="foreignkey")
    op.create_foreign_key(
        "workspace_documents_document_id_fkey", "workspace_documents", "documents", ["document_id"], ["id"]
    )

    op.drop_constraint("chat_documents_document_id_fkey", "chat_documents", type_="foreignkey")
    op.create_foreign_key("chat_documents_document_id_fkey", "chat_documents", "documents", ["document_id"], ["id"])
