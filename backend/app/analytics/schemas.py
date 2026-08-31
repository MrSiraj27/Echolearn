import uuid

from pydantic import BaseModel


class QuestionsOverTimePoint(BaseModel):
    date: str
    count: int


class OverviewResponse(BaseModel):
    total_questions_asked: int
    total_documents: int
    total_quizzes_taken: int
    avg_quiz_score: float | None = None
    most_active_document: str | None = None
    questions_over_time: list[QuestionsOverTimePoint]


class KnowledgeGapTheme(BaseModel):
    theme: str
    count: int
    example_questions: list[str]


class DocumentPerformanceItem(BaseModel):
    document_id: uuid.UUID
    filename: str
    times_referenced: int
    times_not_found: int
    quiz_avg_score: float | None = None


class QuizInsightQuestion(BaseModel):
    quiz_id: uuid.UUID
    quiz_title: str
    question_id: str
    question: str
    times_wrong: int
    times_attempted: int
    wrong_rate: float


class QuizInsightsResponse(BaseModel):
    questions: list[QuizInsightQuestion]
