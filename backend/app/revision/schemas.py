import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SheetLanguage = Literal["en", "ur", "roman_ur", "bilingual"]


class CreateRevisionSheetRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    document_ids: list[uuid.UUID] = []
    workspace_id: uuid.UUID | None = None
    topics: list[str] | None = None
    language: SheetLanguage = "en"
    page_target: Literal[1, 2] = 1
    include_weak_spots: bool = False
    # True = make a fresh sheet even if an identical one exists (counts toward the quota).
    regenerate: bool = False


class CreateRevisionSheetResponse(BaseModel):
    id: uuid.UUID
    status: str
    cached: bool = False


class RevisionSheetStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    error_message: str | None = None


class RevisionSheetListItem(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    language: str
    page_target: int
    created_at: datetime


class RevisionSheetResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    language: str
    page_target: int
    include_weak_spots: bool
    topics: list[str] | None = None
    content: dict | None = None
    error_message: str | None = None
    created_at: datetime
