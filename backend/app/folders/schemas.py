import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class CreateFolderRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Folder name cannot be blank.")
        return v[:100]


class FolderResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    document_count: int = 0


class MoveDocumentRequest(BaseModel):
    folder_id: uuid.UUID | None = None
