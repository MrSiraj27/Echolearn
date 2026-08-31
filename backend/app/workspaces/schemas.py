import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class CreateWorkspaceRequest(BaseModel):
    name: str
    document_ids: list[uuid.UUID] = []

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Workspace name cannot be blank.")
        return v[:100]


class AddDocumentRequest(BaseModel):
    document_id: uuid.UUID


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    document_count: int = 0


class WorkspaceDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    document_ids: list[uuid.UUID]
