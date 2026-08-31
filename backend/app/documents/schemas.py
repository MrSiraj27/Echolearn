import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.document import DocumentStatus


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
    folder_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class DocumentSearchResult(BaseModel):
    text: str
    page_number: int | None = None
    score: float


class DocumentSummaryResponse(BaseModel):
    summary: str | None = None
    suggested_questions: list[str] = []
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
