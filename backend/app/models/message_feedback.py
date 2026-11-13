import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# rating: helpful | not_helpful | incorrect
FEEDBACK_RATINGS = ("helpful", "not_helpful", "incorrect")


class MessageFeedback(Base):
    """One user's verdict on one assistant answer. Used to evaluate retrieval and answer
    quality (admin: GET /admin/system/feedback); never shown to other users."""

    __tablename__ = "message_feedback"
    __table_args__ = (UniqueConstraint("message_id", "user_id", name="uq_message_feedback_message_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
