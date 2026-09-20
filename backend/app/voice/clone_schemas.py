from pydantic import BaseModel

TEXT_HARD_CAP = 800


class CloneRequestBody(BaseModel):
    message_id: str


class CloneRequestResponse(BaseModel):
    status: str  # "done" | "queued"
    job_id: str | None = None
    audio_url: str | None = None
    truncated: bool = False


class CloneStatusResponse(BaseModel):
    status: str  # "queued" | "processing" | "done" | "failed"
    audio_url: str | None = None
    error_message: str | None = None


class PregenerateBody(BaseModel):
    enabled: bool


class SampleInfoResponse(BaseModel):
    has_sample: bool
    pregenerate: bool = False
