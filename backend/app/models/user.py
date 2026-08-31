import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
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

    auth_tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    plan = relationship("Plan", foreign_keys=[plan_id])
