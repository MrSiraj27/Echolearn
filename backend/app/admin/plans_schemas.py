import uuid
from datetime import datetime

from pydantic import BaseModel


class PlanLimits(BaseModel):
    max_documents: int | None = None
    max_file_size_mb: int | None = None
    max_audio_video_minutes: int | None = None
    messages_per_window: int | None = None
    message_window_hours: int = 5
    max_workspaces: int | None = None
    quiz_generations_per_month: int | None = None
    tts_uses_per_day: int | None = None
    diagrams_infographics_per_month: int | None = None
    max_storage_mb: int | None = None
    priority_processing: bool = False


class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_default: bool
    limits: PlanLimits
    price_monthly: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreatePlanRequest(BaseModel):
    name: str
    slug: str
    limits: PlanLimits
    price_monthly: float | None = None
    is_default: bool = False


class UpdatePlanRequest(BaseModel):
    name: str | None = None
    limits: PlanLimits | None = None
    price_monthly: float | None = None
    is_default: bool | None = None
