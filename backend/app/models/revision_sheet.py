import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RevisionSheetStatus(str, enum.Enum):
    queued = "queued"
    generating = "generating"
    ready = "ready"
    failed = "failed"


class RevisionSheet(Base):
    """A one/two-page printable cheat sheet generated from the user's documents.

    Source documents live in a JSON list (no FK), like practice papers, so deleting a source
    document never destroys a sheet the user already has. `content` is the structured sheet
    (see app/rag/revision_sheet.py); the PDF is rendered from it and can always be rebuilt,
    because `pdf_path` sits on a disk that may be wiped by a restart."""

    __tablename__ = "revision_sheets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    document_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Set when the sheet was requested for a whole workspace; document_ids is then the
    # workspace's documents at request time.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    topics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # "en" | "ur" | "roman_ur" | "bilingual"
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    page_target: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    include_weak_spots: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[RevisionSheetStatus] = mapped_column(
        Enum(RevisionSheetStatus, name="revision_sheet_status"), default=RevisionSheetStatus.queued, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
