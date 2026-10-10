import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Level = Literal["beginner", "intermediate", "exam_ready"]
TutorLanguage = Literal["en", "ur", "roman_ur"]


class CreateTutorSessionRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    document_ids: list[uuid.UUID] = []
    workspace_id: uuid.UUID | None = None
    level: Level = "intermediate"
    language: TutorLanguage | None = None  # default: the user's preferred language (en if unset)


class TutorMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class SourceRef(BaseModel):
    document_id: str | None = None
    filename: str | None = None
    page_number: int | None = None
    start_time_seconds: float | None = None


class TutorTurnResponse(BaseModel):
    id: uuid.UUID
    step_index: int
    role: str
    content: str
    turn_type: str | None = None
    hint_level: int | None = None
    verdict: str | None = None
    source_refs: list[SourceRef] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConceptProgress(BaseModel):
    index: int
    name: str
    phase: str
    mastered: bool
    revealed: bool
    attempts: int
    hints_used: int


class TutorProgress(BaseModel):
    concept_index: int
    total_concepts: int
    mastered_count: int
    revealed_count: int
    hint_level: int
    phase: str
    concepts: list[ConceptProgress]


class TutorSessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    topic: str
    level: str
    language: str
    status: str
    turn_count: int
    max_turns: int
    document_ids: list[str]
    workspace_id: uuid.UUID | None = None
    created_at: datetime
    completed_at: datetime | None = None
    summary: dict | None = None
    progress: TutorProgress
    finished: bool = False  # all concepts done or the turn limit reached: call /end for the summary
    turns: list[TutorTurnResponse] = []


class TutorSessionListItem(BaseModel):
    id: uuid.UUID
    title: str
    topic: str
    level: str
    status: str
    turn_count: int
    mastered_count: int
    total_concepts: int
    created_at: datetime


class TutorActionResponse(BaseModel):
    """Result of a hint / just-tell-me / skip / end action (message uses SSE)."""

    turn: TutorTurnResponse | None = None
    session: TutorSessionResponse
