import uuid
from datetime import date, datetime

from pydantic import BaseModel, field_validator

# ---- Review cards (Prompt 30) ----


class ManualReviewCardCreate(BaseModel):
    question: str
    answer: str
    document_id: uuid.UUID
    question_type: str = "short_answer"  # multiple_choice | short_answer | true_false
    options: list[str] | None = None

    @field_validator("question", "answer")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Cannot be blank.")
        return v


class ReviewCardPublic(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    question: str
    answer: str
    question_type: str
    options: list[str] | None
    source_chunk_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewCardWithState(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    question: str
    answer: str
    question_type: str
    options: list[str] | None
    source_chunk_id: str | None
    ease_factor: float
    interval_days: int
    repetitions: int
    next_review_date: date


class TodayReviewResponse(BaseModel):
    cards: list[ReviewCardWithState]
    total_due: int
    capped_at: int


class SubmitReviewRequest(BaseModel):
    quality: int

    @field_validator("quality")
    @classmethod
    def in_range(cls, v: int) -> int:
        if not (0 <= v <= 5):
            raise ValueError("quality must be between 0 and 5.")
        return v


class SubmitReviewResponse(BaseModel):
    next_review_date: date
    interval_days: int


class ReviewStatsResponse(BaseModel):
    current_streak_days: int
    total_cards: int
    cards_mastered: int
    cards_struggling: int


class ReviewSettingsResponse(BaseModel):
    daily_cap: int


class ReviewSettingsUpdate(BaseModel):
    daily_cap: int

    @field_validator("daily_cap")
    @classmethod
    def in_range(cls, v: int) -> int:
        from app.study.spaced_repetition import MAX_DAILY_CARD_CAP, MIN_DAILY_CARD_CAP

        if not (MIN_DAILY_CARD_CAP <= v <= MAX_DAILY_CARD_CAP):
            raise ValueError(f"daily_cap must be between {MIN_DAILY_CARD_CAP} and {MAX_DAILY_CARD_CAP}.")
        return v


# ---- Study plans (Prompt 29) ----


class StudyPlanRequestBase(BaseModel):
    title: str
    exam_date: date
    document_ids: list[uuid.UUID] | None = None
    workspace_id: uuid.UUID | None = None
    daily_study_minutes: int = 45

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be blank.")
        return v[:200]

    @field_validator("daily_study_minutes")
    @classmethod
    def minutes_positive(cls, v: int) -> int:
        if not (10 <= v <= 480):
            raise ValueError("daily_study_minutes must be between 10 and 480.")
        return v


class PreviewStudyPlanRequest(StudyPlanRequestBase):
    pass


class TopicPreview(BaseModel):
    title: str
    description: str
    estimated_difficulty: str


class SessionPreview(BaseModel):
    scheduled_date: date
    topic_title: str
    topic_description: str
    session_type: str


class PlanWarning(BaseModel):
    warning: str
    suggested_reduced_topics: list[str]


class PreviewStudyPlanResponse(BaseModel):
    plan_token: str
    topics: list[TopicPreview]
    sessions: list[SessionPreview]
    warning: PlanWarning | None = None


class CreateStudyPlanRequest(BaseModel):
    plan_token: str
    document_ids: list[uuid.UUID] | None = None
    workspace_id: uuid.UUID | None = None
    reduced_topic_titles: list[str] | None = None


class StudySessionPublic(BaseModel):
    id: uuid.UUID
    scheduled_date: date
    topic_title: str
    topic_description: str
    session_type: str
    status: str
    completed_at: datetime | None
    quiz_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class StudyPlanResponse(BaseModel):
    id: uuid.UUID
    title: str
    exam_date: date
    document_ids: list[uuid.UUID] | None
    workspace_id: uuid.UUID | None
    daily_study_minutes: int
    status: str
    created_at: datetime
    session_count: int = 0
    completed_count: int = 0


class StudyPlanDetailResponse(StudyPlanResponse):
    sessions: list[StudySessionPublic]


class TodaySessionItem(BaseModel):
    plan_id: uuid.UUID
    plan_title: str
    session: StudySessionPublic


class PlanStatusResponse(BaseModel):
    status: str  # on_track | slightly_behind | significantly_behind
    completed_count: int
    expected_by_now_count: int
    total_count: int


class SessionContentResponse(BaseModel):
    topic_title: str
    topic_description: str
    session_type: str
    explanation: str
    practice_questions: list[dict]
