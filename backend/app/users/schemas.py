import uuid

from pydantic import BaseModel

from app.admin.plans_schemas import PlanLimits


class PublicPlan(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_default: bool
    limits: PlanLimits
    price_monthly: float | None

    model_config = {"from_attributes": True}


class QuotaUsageItem(BaseModel):
    key: str
    label: str
    limit: int | float | bool | None
    current_usage: int | float
    resets_in_seconds: int | None = None
    resets_in_human: str | None = None


class MyUsageResponse(BaseModel):
    plan_id: uuid.UUID | None
    plan_name: str | None
    quotas: list[QuotaUsageItem]
