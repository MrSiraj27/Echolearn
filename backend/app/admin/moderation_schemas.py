import uuid
from datetime import datetime

from pydantic import BaseModel


class ContentReportItem(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    document_owner_email: str
    reporter_email: str | None
    reason: str
    details: str | None
    status: str
    auto_flagged: bool
    created_at: datetime
    text_preview: str | None = None


class ModerationActionRequest(BaseModel):
    action: str  # dismiss | remove_document | suspend_user
    notes: str


class AbuseSignal(BaseModel):
    user_id: uuid.UUID
    email: str
    violation_count: int
    last_violation_at: datetime
