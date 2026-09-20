import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.admin.config_service import is_feature_enabled
from app.core.config import settings
from app.core.limits import get_effective_limits
from app.documents.parsers import AUDIO_VIDEO_EXTENSIONS, SUPPORTED_EXTENSIONS, VIDEO_EXTENSIONS
from app.documents.storage import sanitize_filename, save_upload
from app.models import Document, DocumentFolder, DocumentStatus, User

MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


async def ingest_upload(
    file: UploadFile,
    folder_id: uuid.UUID | None,
    current_user: User,
    db: Session,
) -> tuple[Document, str, str]:
    """Validates an uploaded file (extension allowlist, feature flags, plan size limit,
    empty file, document-count quota, folder ownership), creates the Document row and
    saves the file. Returns (document, storage_path, extension); the caller schedules
    the parsing task. Shared by POST /documents/upload and POST /past-papers/upload so
    both go through exactly the same rules."""
    extension = _extension_of(file.filename or "")
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}.",
        )

    if extension in VIDEO_EXTENSIONS and not is_feature_enabled("video_upload_enabled"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Video upload is temporarily unavailable."
        )
    if extension in AUDIO_VIDEO_EXTENSIONS and extension not in VIDEO_EXTENSIONS and not is_feature_enabled(
        "audio_upload_enabled"
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Audio upload is temporarily unavailable."
        )

    limits = get_effective_limits(current_user)
    max_file_size_mb = limits.get("max_file_size_mb")
    effective_max_bytes = MAX_UPLOAD_BYTES if max_file_size_mb is None else min(
        MAX_UPLOAD_BYTES, max_file_size_mb * 1024 * 1024
    )

    content = await file.read()
    if len(content) > effective_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {effective_max_bytes // (1024 * 1024)}MB on your plan.",
        )
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    max_documents = limits.get("max_documents")
    if max_documents is not None:
        existing_count = db.query(Document).filter(Document.user_id == current_user.id).count()
        if existing_count >= max_documents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document limit reached. Your plan allows {max_documents} documents.",
            )

    if folder_id is not None:
        folder = (
            db.query(DocumentFolder)
            .filter(DocumentFolder.id == folder_id, DocumentFolder.user_id == current_user.id)
            .first()
        )
        if not folder:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder not found.")

    document = Document(
        user_id=current_user.id,
        filename=sanitize_filename(file.filename or "unnamed"),
        file_type=extension,
        storage_path="",
        status=DocumentStatus.uploaded,
        folder_id=folder_id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    storage_path = save_upload(current_user.id, document.id, file.filename or "unnamed", content)
    document.storage_path = storage_path
    db.commit()

    return document, storage_path, extension
