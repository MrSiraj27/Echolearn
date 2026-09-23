import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Admin panel (never settable via any public API route — only via the
    # scripts/create_admin.py CLI seed script or another admin's action).
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    admin_role: Mapped[str | None] = mapped_column(String, nullable=True)  # "superadmin" | "support" | "moderator"
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Blocking (replaces the old is_suspended field). blocked_by is null when the
    # block was automatic (abuse detection) rather than an admin action.
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Plans & quotas
    plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=True)
    custom_limits: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Voice cloning (Prompt 28). Set once a reference sample is uploaded; cleared on delete.
    cloned_voice_sample_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    # Fish Audio voice model id created from the current sample — cached so repeated
    # clone requests reuse it instead of re-uploading the reference clip every time.
    # Cleared (set back to None) whenever the sample is replaced or deleted.
    fish_voice_model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Opt-in: clone each new assistant reply in the background so Listen is instant.
    voice_pregenerate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))

    # Daily Review (Prompt 30). Null means "use the app default" (see
    # app.study.spaced_repetition.DEFAULT_DAILY_CARD_CAP) rather than baking the default
    # in at write time, so lowering the app-wide default later doesn't require a backfill.
    daily_review_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)

    auth_tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    plan = relationship("Plan", foreign_keys=[plan_id])
