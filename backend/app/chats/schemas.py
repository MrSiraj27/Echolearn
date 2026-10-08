import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.languages import ExplainMode, Language
from app.models.message import MessageRole


class CreateChatRequest(BaseModel):
    title: str | None = None
    document_ids: list[uuid.UUID] = []
    workspace_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime


class ChatDetailResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    document_ids: list[uuid.UUID]
    workspace_id: uuid.UUID | None = None
    workspace_name: str | None = None


class ChatListItem(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    preview: str | None = None


class TranslationItem(BaseModel):
    """An already-generated Urdu/Roman Urdu rendering of a message, so the UI can show it
    instantly without another request."""

    language: Language
    mode: ExplainMode
    text: str
    fidelity_warning: bool = False


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    citations: list[dict] | None = None
    content_type: str = "text"
    created_at: datetime
    translations: list[TranslationItem] = []

    model_config = {"from_attributes": True}


class DiagramRequest(BaseModel):
    instruction: str


class DiagramResponse(BaseModel):
    possible: bool
    message: MessageResponse | None = None
    error: str | None = None


class InfographicRequest(BaseModel):
    instruction: str | None = None
    template: str = "auto"


class InfographicResponse(BaseModel):
    possible: bool
    message: MessageResponse | None = None
    error: str | None = None


class SendMessageRequest(BaseModel):
    content: str


class ExplainMessageRequest(BaseModel):
    language: Language
    mode: ExplainMode = ExplainMode.translate


class ExplainMessageResponse(BaseModel):
    text: str
    language: Language
    mode: ExplainMode
    fidelity_warning: bool = False
    cached: bool = False


class ExplainRequest(BaseModel):
    text: str


class ExplainResponse(BaseModel):
    explanation: str
    citations: list[dict] = []
