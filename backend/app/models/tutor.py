import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# String-valued fields (not DB enums) so the value sets can grow without a migration:
#   TutorSession.level    beginner | intermediate | exam_ready
#   TutorSession.language en | ur | roman_ur
#   TutorSession.status   active | completed | abandoned
#   TutorTurn.role        tutor | student
#   TutorTurn.turn_type   question | hint | explanation | feedback | check | summary | answer_reveal
#   TutorTurn.verdict     correct | partial | incorrect | skipped
#   TutorConceptState.phase  starter | application | check | done


class TutorSession(Base):
    """One guided, question-first learning session on a topic from the student's documents."""

    __tablename__ = "tutor_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    document_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    topic: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[str] = mapped_column(String, nullable=False, default="intermediate")
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # The teaching plan, generated once per session and cached here: concepts with their
    # questions, expected points and the source passage each is grounded in.
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TutorTurn(Base):
    __tablename__ = "tutor_turns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tutor_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    turn_type: Mapped[str | None] = mapped_column(String, nullable=True)
    hint_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    # [{document_id, filename, page_number, start_time_seconds}, ...]: opens the Source Viewer.
    source_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TutorConceptState(Base):
    """Per-concept progress within a session."""

    __tablename__ = "tutor_concept_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tutor_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_index: Mapped[int] = mapped_column(Integer, nullable=False)
    concept: Mapped[str] = mapped_column(String, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revealed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mastered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_chunk_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Where this concept is in its mini-lesson, and the question currently on the table.
    phase: Mapped[str] = mapped_column(String, nullable=False, default="starter")
    hint_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
