import uuid
from datetime import datetime

from pydantic import BaseModel

from app.admin.plans_schemas import PlanLimits


class AdminUserListItem(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    is_verified: bool
    is_blocked: bool
    is_admin: bool
    created_at: datetime
    last_active: datetime | None
    document_count: int
    message_count: int


class AdminDocumentSummary(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    created_at: datetime


class AdminChatSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    message_count: int
    created_at: datetime


class AdminQuizAttemptSummary(BaseModel):
    quiz_title: str
    score: float
    taken_at: datetime


class AdminQueryLogItem(BaseModel):
    question: str
    was_answered: bool
    created_at: datetime


class AdminUserDetail(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    is_verified: bool
    is_blocked: bool
    blocked_reason: str | None
    blocked_at: datetime | None
    blocked_by_name: str | None
    is_admin: bool
    admin_role: str | None
    admin_notes: str | None
    created_at: datetime
    plan_id: uuid.UUID | None
    plan_name: str | None
    documents: list[AdminDocumentSummary]
    chats: list[AdminChatSummary]
    workspace_names: list[str]
    quiz_attempts: list[AdminQuizAttemptSummary]
    recent_queries: list[AdminQueryLogItem]


class BlockUserRequest(BaseModel):
    reason: str


class DeleteUserRequest(BaseModel):
    confirm_email: str


class UpdateNotesRequest(BaseModel):
    notes: str


class ImpersonateResponse(BaseModel):
    access_token: str
    expires_in_minutes: int = 10
    user_email: str


class RecentErrorItem(BaseModel):
    kind: str  # "query" | "api_call"
    detail: str
    created_at: datetime


class ActivityItem(BaseModel):
    kind: str  # "document_upload" | "chat_created" | "query" | "error"
    detail: str
    created_at: datetime


class QuotaUsageItem(BaseModel):
    key: str  # e.g. "messages_per_window", "max_documents"
    label: str
    limit: int | float | bool | None
    current_usage: int | float
    resets_in_seconds: int | None = None
    resets_in_human: str | None = None


class UserLimitsResponse(BaseModel):
    plan_id: uuid.UUID | None
    plan_name: str | None
    custom_limits: dict | None
    effective_limits: PlanLimits
    usage: list[QuotaUsageItem]


class UpdateUserPlanRequest(BaseModel):
    plan_id: uuid.UUID


class UpdateCustomLimitsRequest(BaseModel):
    custom_limits: dict
