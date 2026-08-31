import uuid
from datetime import datetime

from pydantic import BaseModel


class ProviderStat(BaseModel):
    provider: str
    total_calls: int
    error_count: int
    error_rate: float
    avg_duration_ms: float | None


class PurposeBreakdown(BaseModel):
    purpose: str
    count: int


class TopUser(BaseModel):
    user_id: uuid.UUID
    email: str
    call_count: int


class UsageOverviewResponse(BaseModel):
    calls_today: int
    calls_this_week: int
    calls_this_month: int
    provider_stats: list[ProviderStat]
    purpose_breakdown: list[PurposeBreakdown]
    top_users: list[TopUser]


class StuckJob(BaseModel):
    document_id: uuid.UUID
    filename: str
    user_email: str
    status: str
    stuck_for_minutes: float


class FailedJob(BaseModel):
    document_id: uuid.UUID
    filename: str
    user_email: str
    created_at: datetime


class JobHealthResponse(BaseModel):
    stuck_jobs: list[StuckJob]
    failed_jobs: list[FailedJob]


class UserStorageItem(BaseModel):
    user_id: uuid.UUID
    email: str
    document_count: int
    bytes_used: int


class StorageResponse(BaseModel):
    total_bytes: int
    by_user: list[UserStorageItem]


class BlockedUserItem(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    blocked_reason: str | None
    blocked_at: datetime | None
    blocked_by_name: str | None  # "System" if auto-blocked
    is_auto_blocked: bool
