import mimetypes
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import block_if_impersonating, get_current_user, get_current_user_media
from app.core.limits import get_effective_limits
from app.documents.background import run_parsing_task, run_url_ingest_task
from app.admin.config_service import is_feature_enabled
from app.documents.parsers import AUDIO_VIDEO_EXTENSIONS, SUPPORTED_EXTENSIONS, VIDEO_EXTENSIONS
from app.documents.page_content import find_highlight_offsets, get_page, load_pages
from app.documents.schemas import (
    DocumentFromUrlRequest,
    DocumentListItem,
    DocumentSearchResult,
    DocumentStatusResponse,
    DocumentSummaryResponse,
    DocumentUploadResponse,
    PageContentRequest,
    PageContentResponse,
    ReportDocumentRequest,
    TranscriptSegmentResponse,
)
from app.documents.storage import delete_document_files, save_upload
from app.folders.schemas import MoveDocumentRequest
from app.models import ContentReport, Document, DocumentFolder, DocumentStatus, User
from app.rag.vectorstore import delete_document as delete_vector_chunks
from app.rag.vectorstore import search as vector_search

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    folder_id: uuid.UUID | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
        filename=file.filename or "unnamed",
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

    background_tasks.add_task(run_parsing_task, document.id, storage_path, extension)

    return DocumentUploadResponse(document_id=document.id, status=document.status)


@router.post("/from-url", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_document_from_url(
    background_tasks: BackgroundTasks,
    payload: DocumentFromUrlRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a document from a video URL (YouTube or any other yt-dlp-supported site) —
    downloads the audio track locally and transcribes it exactly like an uploaded file."""
    url = payload.url.strip()
    if not url or not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid video URL.")

    if payload.folder_id is not None:
        folder = (
            db.query(DocumentFolder)
            .filter(DocumentFolder.id == payload.folder_id, DocumentFolder.user_id == current_user.id)
            .first()
        )
        if not folder:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder not found.")

    document = Document(
        user_id=current_user.id,
        filename="Downloading video…",
        file_type="wav",
        storage_path="",
        status=DocumentStatus.uploaded,
        folder_id=payload.folder_id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(run_url_ingest_task, document.id, url)

    return DocumentUploadResponse(document_id=document.id, status=document.status)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    return DocumentStatusResponse(
        id=document.id, status=document.status, page_count=document.page_count, filename=document.filename
    )


@router.get("/{document_id}/summary", response_model=DocumentSummaryResponse)
def get_document_summary(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    return DocumentSummaryResponse(
        summary=document.summary,
        suggested_questions=document.suggested_questions or [],
        status=document.status,
    )


@router.post("/{document_id}/page/{page_number}", response_model=PageContentResponse)
def get_document_page(
    document_id: uuid.UUID,
    page_number: int,
    payload: PageContentRequest = PageContentRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Text-only source preview: returns the raw text of one page/slide plus the
    character offsets of the cited chunk within it, if it can be located. PDF pages are
    not rendered as images (keeps this endpoint free of extra system dependencies and
    hosting cost) — the frontend shows the extracted text instead, which is what was
    actually used to generate the answer anyway."""
    document = (
        db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    pages = load_pages(document)
    if not pages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This document has no readable pages.")

    page = get_page(document, page_number)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Page {page_number} not found.")

    highlight = find_highlight_offsets(page["text"], payload.chunk_text)

    return PageContentResponse(
        page_number=page_number,
        text=page["text"],
        total_pages=len(pages),
        highlight_start=highlight[0] if highlight else None,
        highlight_end=highlight[1] if highlight else None,
    )


@router.get("/{document_id}/transcript", response_model=list[TranscriptSegmentResponse])
def get_document_transcript(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    pages = load_pages(document)
    return [
        TranscriptSegmentResponse(start_time=p.get("start_time"), end_time=p.get("end_time"), text=p.get("text", ""))
        for p in pages
        if p.get("start_time") is not None
    ]


CHUNK_SIZE = 1024 * 1024


@router.get("/{document_id}/media")
def get_document_media(
    document_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user_media),
    db: Session = Depends(get_db),
):
    """Serve the original audio/video file for playback, with Range support so the
    frontend <audio>/<video> element can seek without downloading the whole file."""
    document = (
        db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    file_path = document.storage_path
    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found on disk.")

    file_size = os.path.getsize(file_path)
    content_type = mimetypes.guess_type(document.filename)[0] or "application/octet-stream"

    range_header = request.headers.get("range")
    start, end = 0, file_size - 1
    if range_header:
        try:
            range_value = range_header.strip().removeprefix("bytes=")
            start_str, end_str = range_value.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
        except ValueError:
            raise HTTPException(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE, detail="Invalid Range header.")

    end = min(end, file_size - 1)
    if start > end or start < 0:
        raise HTTPException(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE, detail="Invalid Range header.")

    content_length = end - start + 1

    def iter_file():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk = f.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
    }
    status_code = status.HTTP_206_PARTIAL_CONTENT if range_header else status.HTTP_200_OK
    return StreamingResponse(iter_file(), status_code=status_code, media_type=content_type, headers=headers)


@router.get("/", response_model=list[DocumentListItem])
def list_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    documents = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return documents


@router.get("/{document_id}/search", response_model=list[DocumentSearchResult])
def search_document(
    document_id: uuid.UUID,
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if not q.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Search query cannot be empty.")

    if document.status not in (DocumentStatus.embedded, DocumentStatus.ready):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This document is still processing — search will be available once it's ready.",
        )

    results = vector_search(q, current_user.id, [document_id], top_k=10)
    return [
        DocumentSearchResult(
            text=r["text"],
            page_number=r["metadata"].get("page_number"),
            score=max(0.0, 1 - r["distance"]),
        )
        for r in results
    ]


@router.patch("/{document_id}/folder", response_model=DocumentListItem)
def move_document_to_folder(
    document_id: uuid.UUID,
    payload: MoveDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if payload.folder_id is not None:
        folder = (
            db.query(DocumentFolder)
            .filter(DocumentFolder.id == payload.folder_id, DocumentFolder.user_id == current_user.id)
            .first()
        )
        if not folder:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder not found.")

    document.folder_id = payload.folder_id
    db.commit()
    db.refresh(document)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    document = (
        db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    delete_document_files(current_user.id, document.id)
    delete_vector_chunks(document.id)
    db.delete(document)
    db.commit()


_VALID_REPORT_REASONS = {"copyright", "illegal_content", "spam", "other"}


@router.post("/{document_id}/report", status_code=status.HTTP_204_NO_CONTENT)
def report_document(
    document_id: uuid.UUID,
    payload: ReportDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Any user can flag a document (not just its owner) — reports are reviewed in the
    admin moderation queue."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if payload.reason not in _VALID_REPORT_REASONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"reason must be one of {sorted(_VALID_REPORT_REASONS)}."
        )

    db.add(
        ContentReport(
            document_id=document.id,
            reporter_user_id=current_user.id,
            reason=payload.reason,
            details=payload.details,
        )
    )
    db.commit()
