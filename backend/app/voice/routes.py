import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.admin.config_service import is_feature_enabled
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import check_rate_limit
from app.core.security import get_current_user
from app.core.usage import check_and_record_usage
from app.models import User
from app.voice.cache import get_cached_audio, store_cached_audio
from app.voice.schemas import SpeakRequest, VoiceOption
from app.voice.tts import (
    DEFAULT_VOICE_ID,
    VoiceUnavailableError,
    is_voice_ready,
    list_available_voices,
    synthesize_speech,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

VOICE_RATE_LIMIT_MAX = 20
VOICE_RATE_LIMIT_WINDOW_SECONDS = 60


def _synthesize_via_hf_space(text: str, voice_id: str) -> bytes:
    import requests

    if not settings.VOICE_HF_SPACE_URL:
        raise VoiceUnavailableError("VOICE_BACKEND is 'hf_space' but VOICE_HF_SPACE_URL is not set.")

    # Expects the Space to expose a plain POST endpoint that accepts {"text": ..., "voice_id": ...}
    # and returns raw WAV bytes — see README for a minimal FastAPI/gradio wrapper example
    # that satisfies this contract using the same synthesize_speech() logic.
    response = requests.post(
        f"{settings.VOICE_HF_SPACE_URL.rstrip('/')}/synthesize",
        json={"text": text, "voice_id": voice_id},
        timeout=30,
    )
    response.raise_for_status()
    return response.content


@router.get("/voices", response_model=list[VoiceOption])
def get_voices():
    return list_available_voices()


@router.post("/speak")
def speak(
    payload: SpeakRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not is_feature_enabled("voice_output_enabled"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Voice output is temporarily unavailable.")

    check_rate_limit(
        f"voice:{current_user.id}", max_attempts=VOICE_RATE_LIMIT_MAX, window_seconds=VOICE_RATE_LIMIT_WINDOW_SECONDS
    )

    check_and_record_usage(db, current_user, "tts_use")

    voice_id = payload.voice_id or DEFAULT_VOICE_ID

    cached = get_cached_audio(payload.message_id, voice_id)
    if cached is not None:
        return Response(content=cached, media_type="audio/wav")

    try:
        if settings.VOICE_BACKEND == "hf_space":
            audio_bytes = _synthesize_via_hf_space(payload.text, voice_id)
        else:
            if not is_voice_ready(voice_id):
                raise VoiceUnavailableError(f"Voice '{voice_id}' is not configured on this server.")
            audio_bytes = synthesize_speech(payload.text, voice_id)
    except VoiceUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception:
        logger.exception("Voice synthesis failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Voice synthesis failed. Please try again.")

    store_cached_audio(payload.message_id, voice_id, audio_bytes)

    return Response(content=audio_bytes, media_type="audio/wav")
