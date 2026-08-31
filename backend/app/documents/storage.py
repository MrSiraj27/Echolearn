import re
import uuid
from pathlib import Path

from app.core.config import settings

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_.\-]")


def sanitize_filename(filename: str) -> str:
    """Strip path components and any character that isn't alphanumeric, dot, dash or underscore."""
    name = Path(filename).name
    name = _UNSAFE_CHARS.sub("_", name)
    return name.lstrip(".") or "file"


def document_dir(user_id: uuid.UUID, document_id: uuid.UUID) -> Path:
    path = Path(settings.STORAGE_PATH) / str(user_id) / str(document_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload(user_id: uuid.UUID, document_id: uuid.UUID, filename: str, content: bytes) -> str:
    safe_name = sanitize_filename(filename)
    dest = document_dir(user_id, document_id) / safe_name
    dest.write_bytes(content)
    return str(dest)


def delete_document_files(user_id: uuid.UUID, document_id: uuid.UUID) -> None:
    import shutil

    path = Path(settings.STORAGE_PATH) / str(user_id) / str(document_id)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
