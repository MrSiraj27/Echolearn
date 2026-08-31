import re
from pathlib import Path

from app.core.config import settings

_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_\-]")


def _cache_path(message_id: str, voice_id: str) -> Path:
    safe_id = _SAFE_ID_RE.sub("_", message_id)
    safe_voice = _SAFE_ID_RE.sub("_", voice_id)
    return Path(settings.VOICE_AUDIO_CACHE_PATH) / f"{safe_id}__{safe_voice}.wav"


def get_cached_audio(message_id: str | None, voice_id: str) -> bytes | None:
    if not message_id:
        return None
    path = _cache_path(message_id, voice_id)
    if path.exists():
        return path.read_bytes()
    return None


def store_cached_audio(message_id: str | None, voice_id: str, audio_bytes: bytes) -> None:
    if not message_id:
        return
    path = _cache_path(message_id, voice_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio_bytes)
