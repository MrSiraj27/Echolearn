import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.languages import contains_devanagari
from app.models.document import DocumentStatus


def _drop_hindi_questions(questions: list[str] | None) -> list[str] | None:
    """Suggestion chips generated before the no-Hindi rule may be in Devanagari: hide them."""
    if questions is None:
        return None
    return [q for q in questions if not contains_devanagari(q)]


def _drop_hindi_summary(summary: str | None) -> str | None:
    return None if contains_devanagari(summary) else summary


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    status: DocumentStatus


class DocumentFromUrlRequest(BaseModel):
    url: str
    folder_id: uuid.UUID | None = None


class ReportDocumentRequest(BaseModel):
    reason: str  # copyright | illegal_content | spam | other
    details: str | None = None


class DocumentStatusResponse(BaseModel):
    id: uuid.UUID
    status: DocumentStatus
    page_count: int | None = None
    filename: str


class DocumentListItem(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    status: DocumentStatus
    created_at: datetime
    summary: str | None = None
    suggested_questions: list[str] | None = None

    _clean_summary = field_validator("summary")(_drop_hindi_summary)
    _clean_questions = field_validator("suggested_questions")(_drop_hindi_questions)
    folder_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class DocumentSearchResult(BaseModel):
    text: str
    page_number: int | None = None
    score: float


class DocumentSummaryResponse(BaseModel):
    summary: str | None = None
    suggested_questions: list[str] = []

    _clean_summary = field_validator("summary")(_drop_hindi_summary)
    _clean_questions = field_validator("suggested_questions")(_drop_hindi_questions)
    status: DocumentStatus


class PageContentRequest(BaseModel):
    chunk_text: str | None = None


class PageContentResponse(BaseModel):
    page_number: int
    text: str
    total_pages: int
    highlight_start: int | None = None
    highlight_end: int | None = None


class TranscriptSegmentResponse(BaseModel):
    start_time: float | None = None
    end_time: float | None = None
    text: str
