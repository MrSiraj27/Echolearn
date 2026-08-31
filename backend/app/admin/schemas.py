import uuid
from datetime import datetime

from pydantic import BaseModel


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    name: str
    email: str
    admin_role: str | None


class AdminMeResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    admin_role: str | None


class AuditLogItem(BaseModel):
    id: uuid.UUID
    admin_user_id: uuid.UUID | None
    admin_name: str | None = None
    action: str
    target_id: str | None
    details: dict | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
