import logging
import uuid
from threading import Lock

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import SystemConfig

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, dict] = {
    "feature_flags": {
        "audio_upload_enabled": True,
        "video_upload_enabled": True,
        "quiz_generation_enabled": True,
        "diagram_generation_enabled": True,
        "infographic_generation_enabled": True,
        "voice_output_enabled": True,
        "voice_input_enabled": True,
    },
    "model_selection": {
        "primary_llm_provider": "groq",
        "fallback_llm_provider": "gemini",
    },
    "moderation": {
        "flag_keywords": ["child abuse", "credit card dump", "social security number list"],
    },
    "abuse_detection": {
        "auto_block_enabled": True,
        "auto_block_rate_limit_violations_threshold": 10,
        "auto_block_violation_window_minutes": 60,
    },
}

_cache: dict[str, dict] = {}
_lock = Lock()
_loaded = False


def _load_from_db(db: Session) -> dict[str, dict]:
    rows = db.query(SystemConfig).all()
    values = {row.key: row.value for row in rows}
    # Seed any missing keys with defaults (first boot, or a newly-added config key).
    for key, default_value in DEFAULT_CONFIG.items():
        if key not in values:
            values[key] = default_value
    return values


def ensure_loaded() -> None:
    global _loaded
    with _lock:
        if _loaded:
            return
        db = SessionLocal()
        try:
            _cache.update(_load_from_db(db))
        finally:
            db.close()
        _loaded = True


def get_config() -> dict[str, dict]:
    ensure_loaded()
    return _cache


def get_config_value(key: str) -> dict:
    ensure_loaded()
    return _cache.get(key, DEFAULT_CONFIG.get(key, {}))


def is_feature_enabled(flag: str) -> bool:
    return bool(get_config_value("feature_flags").get(flag, True))


def refresh_config(db: Session) -> None:
    """Re-read all config from the DB into the in-memory cache — call this right after
    an admin updates a key so every subsequent request sees the new value immediately,
    with no restart needed."""
    with _lock:
        _cache.clear()
        _cache.update(_load_from_db(db))


def set_config_value(db: Session, key: str, value: dict, updated_by: uuid.UUID | None) -> None:
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if row:
        row.value = value
        row.updated_by = updated_by
    else:
        row = SystemConfig(key=key, value=value, updated_by=updated_by)
        db.add(row)
