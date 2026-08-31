from pydantic import BaseModel, field_validator

MAX_TEXT_LENGTH = 5000


class SpeakRequest(BaseModel):
    text: str
    message_id: str | None = None
    voice_id: str | None = None

    @field_validator("text")
    @classmethod
    def text_not_too_long(cls, v: str) -> str:
        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError(f"Text must be at most {MAX_TEXT_LENGTH} characters.")
        return v


class VoiceOption(BaseModel):
    id: str
    label: str
