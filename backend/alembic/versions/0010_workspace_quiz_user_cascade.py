"""Fix missing ON DELETE CASCADE on workspaces.user_id / quizzes.user_id -> users.

Without this, admin-deleting a user with any workspace or quiz raises an unhandled
IntegrityError (surfaced to the caller as a raw 500) even though the route already
tries to pre-delete those rows in Python — SQLAlchemy's flush ordering doesn't
reliably sequence deletes across mapped classes that have a bare FK column with no
declared relationship(), so the explicit pre-delete loop isn't sufficient on its own.
Making the DB itself cascade removes the need to get that ordering right in code.

Revision ID: 0010_workspace_quiz_user_cascade
Revises: 0009_document_fk_cascades
Create Date: 2026-09-06
"""
from alembic import op

revision = "0010_workspace_quiz_user_cascade"
down_revision = "0009_document_fk_cascades"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("workspaces_user_id_fkey", "workspaces", type_="foreignkey")
    op.create_foreign_key(
        "workspaces_user_id_fkey", "workspaces", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )

    op.drop_constraint("quizzes_user_id_fkey", "quizzes", type_="foreignkey")
    op.create_foreign_key("quizzes_user_id_fkey", "quizzes", "users", ["user_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("quizzes_user_id_fkey", "quizzes", type_="foreignkey")
    op.create_foreign_key("quizzes_user_id_fkey", "quizzes", "users", ["user_id"], ["id"])

    op.drop_constraint("workspaces_user_id_fkey", "workspaces", type_="foreignkey")
    op.create_foreign_key("workspaces_user_id_fkey", "workspaces", "users", ["user_id"], ["id"])
