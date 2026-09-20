import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

# ---- Past papers ----


class PastPaperResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    exam_name: str | None
    analysis_status: str
    error_message: str | None
    extracted_pattern: dict | None
    pattern_summary: str | None
    created_at: datetime


class PastPaperStatusResponse(BaseModel):
    id: uuid.UUID
    analysis_status: str
    document_status: str | None
    error_message: str | None
    extracted_pattern: dict | None
    pattern_summary: str | None


# ---- Practice papers ----


class SectionConfig(BaseModel):
    name: str
    question_type: str
    count: int
    marks_each: float


class PatternOverride(BaseModel):
    sections: list[SectionConfig]


class PreviewPatternRequest(BaseModel):
    based_on_past_paper_ids: list[uuid.UUID] | None = None
    custom_pattern_override: PatternOverride | None = None


class PreviewPatternResponse(BaseModel):
    pattern_config: dict
    pattern_source: str
    pattern_note: str
    estimated_time_minutes: int
    recurring_topics: list[str]
    past_paper_summary: str | None
    section_confidence: list[str] | None = None


class GeneratePracticePaperRequest(BaseModel):
    title: str
    document_ids: list[uuid.UUID]
    based_on_past_paper_ids: list[uuid.UUID] | None = None
    important_topics: list[str] | None = None
    custom_pattern_override: PatternOverride | None = None
    time_allowed_minutes: int | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Give the paper a title.")
        return v[:150]


class GeneratePracticePaperResponse(BaseModel):
    id: uuid.UUID
    status: str


class PracticePaperListItem(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    pattern_source: str
    pattern_note: str | None
    total_marks: Any | None
    total_questions: int | None
    time_allowed_minutes: int | None
    error_message: str | None
    created_at: datetime


class PracticePaperStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    error_message: str | None


class PracticePaperDetail(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    disclaimer: str
    pattern_source: str
    pattern_note: str | None
    pattern_config: dict
    time_allowed_minutes: int | None
    time_estimated: bool
    total_marks: Any | None
    total_questions: int | None
    important_topics: list[str] | None
    topic_coverage: list[dict]
    sections: list[dict]
    created_at: datetime


class SubmitPracticePaperRequest(BaseModel):
    answers: dict[str, str] = {}
    self_marks: dict[str, float] | None = None


class SelfGradeRequest(BaseModel):
    self_marks: dict[str, float]


class AttemptResultResponse(BaseModel):
    attempt_id: uuid.UUID
    marks_obtained: float
    total_marks: Any
    score_percent: float
    pending_self_grade_count: int
    results: list[dict]
