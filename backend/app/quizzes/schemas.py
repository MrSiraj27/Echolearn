import uuid
from datetime import datetime

from pydantic import BaseModel


class GenerateQuizRequest(BaseModel):
    document_ids: list[uuid.UUID]
    num_questions: int = 10
    difficulty: str = "medium"  # easy | medium | hard
    question_type: str = "mixed"  # multiple_choice | short_answer | mixed
    title: str | None = None


class QuizQuestionPublic(BaseModel):
    """Question shape returned before submission — no answer key."""

    id: str
    question: str
    type: str
    options: list[str]


class QuizResponse(BaseModel):
    id: uuid.UUID
    title: str
    document_ids: list[uuid.UUID]
    questions: list[QuizQuestionPublic]
    created_at: datetime


class QuizListItem(BaseModel):
    id: uuid.UUID
    title: str
    question_count: int
    created_at: datetime
    best_score: float | None = None
    attempt_count: int = 0


class SubmitQuizRequest(BaseModel):
    answers: dict[str, str]  # question id -> submitted answer


class QuestionResult(BaseModel):
    id: str
    question: str
    type: str
    options: list[str]
    submitted_answer: str | None
    correct_answer: str
    is_correct: bool
    explanation: str
    source_page: int | None
    source_filename: str | None


class SubmitQuizResponse(BaseModel):
    attempt_id: uuid.UUID
    score: float
    total: int
    correct_count: int
    results: list[QuestionResult]
