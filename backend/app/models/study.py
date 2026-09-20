import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReviewQuestionType(str, enum.Enum):
    multiple_choice = "multiple_choice"
    short_answer = "short_answer"
    true_false = "true_false"


class StudyPlanStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    abandoned = "abandoned"


class StudySessionType(str, enum.Enum):
    learn = "learn"
    review = "review"
    quiz = "quiz"
    checkpoint = "checkpoint"


class StudySessionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    skipped = "skipped"


class ReviewCard(Base):
    """A single spaced-repetition flashcard (Prompt 30). Auto-generated from quiz
    questions / study-session practice questions, or manually saved by the user from an
    AI chat answer. `source_chunk_id` lets the frontend jump back to the source material —
    it's a composite string ("page:<n>" for paginated documents, "time:<start>-<end>" for
    audio/video transcripts) since chunks in the vectorstore aren't independently
    addressable by a stable id; document_id + this string is enough to re-locate it."""

    __tablename__ = "review_cards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[ReviewQuestionType] = mapped_column(
        Enum(ReviewQuestionType, name="review_question_type"), default=ReviewQuestionType.short_answer, nullable=False
    )
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_chunk_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    state = relationship("ReviewCardState", back_populates="card", uselist=False, cascade="all, delete-orphan")


class ReviewCardState(Base):
    """Per-user SM-2 scheduling state for a ReviewCard. 1:1 with ReviewCard today (cards
    aren't shared across users), split into its own table because it's the part that
    changes on every review while the card content itself never does."""

    __tablename__ = "review_card_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_cards.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # New cards are due immediately rather than after some initial delay.
    next_review_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    card = relationship("ReviewCard", back_populates="state")


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Nullable if workspace_id is set instead — a plan is scoped to one or the other.
    document_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # SET NULL (not CASCADE) to match Chat.workspace_id's convention elsewhere in this
    # app: deleting a workspace is a grouping change, not a reason to destroy a plan the
    # user is actively working through.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    daily_study_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[StudyPlanStatus] = mapped_column(
        Enum(StudyPlanStatus, name="study_plan_status"), default=StudyPlanStatus.active, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sessions = relationship(
        "StudySession", back_populates="plan", cascade="all, delete-orphan", order_by="StudySession.scheduled_date"
    )


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    topic_title: Mapped[str] = mapped_column(String, nullable=False)
    topic_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Whatever chunk/page identifiers let us scope on-demand content generation later —
    # list of {"document_id": str, "page_number": int | None, "start_time_seconds": float | None,
    # "end_time_seconds": float | None}.
    source_chunks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    session_type: Mapped[StudySessionType] = mapped_column(
        Enum(StudySessionType, name="study_session_type"), nullable=False
    )
    status: Mapped[StudySessionStatus] = mapped_column(
        Enum(StudySessionStatus, name="study_session_status"), default=StudySessionStatus.pending, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # SET NULL: if the linked quiz is ever deleted, the session should just fall back to
    # being an un-linked checkpoint rather than disappearing.
    quiz_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="SET NULL"), nullable=True
    )

    plan = relationship("StudyPlan", back_populates="sessions")
