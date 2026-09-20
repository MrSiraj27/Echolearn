import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VoiceCloneJobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    failed = "failed"


class VoiceCloneJob(Base):
    """One row per voice-cloning generation request. Looked up by
    (user_id, reference_audio_hash, text_hash) before creating a new job — an existing
    "done" row for that exact triple is a cache hit and short-circuits both a new job
    and a quota charge (see app/voice/clone_routes.py)."""

    __tablename__ = "voice_clone_jobs"
    __table_args__ = (
        Index("ix_voice_clone_jobs_lookup", "user_id", "reference_audio_hash", "text_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Nullable + SET NULL: the generated audio can still be served/cached even if the
    # source message is later deleted — we don't want a message delete to cascade into
    # destroying a (possibly still-cached) cloned clip.
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    reference_audio_hash: Mapped[str] = mapped_column(String, nullable=False)
    text_hash: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[VoiceCloneJobStatus] = mapped_column(
        Enum(VoiceCloneJobStatus, name="voice_clone_job_status"), nullable=False, default=VoiceCloneJobStatus.queued
    )
    output_audio_path: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
