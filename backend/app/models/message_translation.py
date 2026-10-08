import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MessageTranslation(Base):
    """Cached Urdu / Roman Urdu rendering of one assistant message. Looked up before every
    explain request so repeating one never costs an LLM call or a quota unit."""

    __tablename__ = "message_translations"
    __table_args__ = (UniqueConstraint("message_id", "language", "mode", name="uq_message_translation"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String, nullable=False)  # a Language value
    mode: Mapped[str] = mapped_column(String, nullable=False)  # an ExplainMode value
    text: Mapped[str] = mapped_column(Text, nullable=False)
    fidelity_warning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
