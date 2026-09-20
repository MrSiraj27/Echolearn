import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PastPaperAnalysisStatus(str, enum.Enum):
    pending = "pending"
    analyzing = "analyzing"
    ready = "ready"
    failed = "failed"


class PracticePaperStatus(str, enum.Enum):
    generating = "generating"
    ready = "ready"
    failed = "failed"


class PastPaper(Base):
    """A past exam paper the user uploaded so we can learn its *structure* (sections,
    question types, counts, marks). The upload is a normal Document (so it goes through
    the same parse/chunk/embed pipeline and quota rules); this row just tracks the
    structural analysis. Deleting the underlying Document cascades to this row."""

    __tablename__ = "past_papers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    exam_name: Mapped[str | None] = mapped_column(String, nullable=True)
    extracted_pattern: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_status: Mapped[PastPaperAnalysisStatus] = mapped_column(
        Enum(PastPaperAnalysisStatus, name="past_paper_analysis_status"),
        default=PastPaperAnalysisStatus.pending,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PracticePaper(Base):
    """An AI-generated practice exam. Source documents live in a JSON list (no FK) so
    deleting a source document never destroys a paper the user already has."""

    __tablename__ = "practice_papers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    document_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    based_on_past_paper_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    important_topics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    pattern_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # "custom" | "past_papers" | "standard" - drives the badge in the UI.
    pattern_source: Mapped[str] = mapped_column(String, nullable=False, default="standard")
    pattern_note: Mapped[str | None] = mapped_column(String, nullable=True)
    time_allowed_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[PracticePaperStatus] = mapped_column(
        Enum(PracticePaperStatus, name="practice_paper_status"), default=PracticePaperStatus.generating, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    attempts = relationship("PracticePaperAttempt", back_populates="paper", cascade="all, delete-orphan")


class PracticePaperAttempt(Base):
    __tablename__ = "practice_paper_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("practice_papers.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    results: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    paper = relationship("PracticePaper", back_populates="attempts")
