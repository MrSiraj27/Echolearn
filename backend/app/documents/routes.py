import logging
import mimetypes
import os
from pathlib import Path
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
from app.core.usage import enforce_quota, record_usage
from app.documents.schemas import (
    DocumentFromUrlRequest,
    DocumentPage,
    DocumentPagesResponse,
    ExplainSelectionRequest,
    ExplainSelectionResponse,
    ExplainSource,
    RenameDocumentRequest,
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
from app.documents.object_storage import download_dir
from app.documents.storage import delete_document_files
from app.documents.upload_service import ingest_upload
from app.folders.schemas import MoveDocumentRequest
from app.models import ContentReport, Document, DocumentFolder, DocumentStatus, User
from app.rag.vectorstore import delete_document as delete_vector_chunks
from app.rag.vectorstore import search as vector_search
from app.rag import selection_explainer

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)

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
    document, storage_path, extension = await ingest_upload(file, folder_id, current_user, db)

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
        id=document.id,
        status=document.status,
        page_count=document.page_count,
        filename=document.filename,
        error_message=document.error_message,
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


def _get_owned_document(db: Session, document_id: uuid.UUID, user_id: uuid.UUID) -> Document:
    document = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


READABLE_STATUSES = (DocumentStatus.embedded, DocumentStatus.ready)


@router.get("/{document_id}/pages", response_model=DocumentPagesResponse)
def get_document_pages(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Every page's extracted text, for the in-app reader (page navigation, in-document
    search, text selection). Available once the document has been indexed."""
    document = _get_owned_document(db, document_id, current_user.id)
    if document.status not in READABLE_STATUSES:
        detail = (
            "This document couldn't be processed, so there's nothing to read."
            if document.status == DocumentStatus.failed
            else "This document isn't ready to read yet."
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    pages = load_pages(document)
    if not pages:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This document's text isn't available.")
    return DocumentPagesResponse(
        document_id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        pages=[
            DocumentPage(page_number=p.get("page_number") or i + 1, text=p.get("text") or "")
            for i, p in enumerate(pages)
        ],
    )


@router.post("/{document_id}/explain", response_model=ExplainSelectionResponse)
def explain_document_selection(
    document_id: uuid.UUID,
    payload: ExplainSelectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Explain text the user selected in the reader, using the text around it and related
    passages from the same document. With `question`, answers a follow-up about it.
    Counts as one AI message against the user's message quota, charged only on success."""
    document = _get_owned_document(db, document_id, current_user.id)
    if document.status not in READABLE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This document isn't ready yet.")
    selection = payload.text.strip()
    if not selection:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select some text first.")
    question = (payload.question or "").strip() or None

    enforce_quota(db, current_user, "message")

    page = get_page(document, payload.page_number) if payload.page_number else None
    page_context = selection_explainer.surrounding_context(page.get("text") or "", selection) if page else ""

    related: list[dict] = []
    try:
        from app.rag.retrieval import hybrid_search  # loads the embedding model on first use

        queries = [question, selection[:500]] if question else [selection[:500]]
        chunks, _info = hybrid_search(queries, current_user.id, [document.id], top_k=6, per_doc_k=6)
        squashed_context = " ".join(page_context.split())
        for c in chunks:
            text = (c.get("text") or "").strip()
            if text and " ".join(text.split())[:200] not in squashed_context:
                meta = c.get("metadata") or {}
                related.append({"text": text, "page_number": meta.get("page_number") or c.get("page_number")})
    except Exception:
        # The text around the selection is usually enough; don't fail over retrieval.
        logger.warning("Related-passage retrieval failed for reader explain on %s", document.id, exc_info=True)

    kind = selection_explainer.classify_selection(selection)
    messages = selection_explainer.build_messages(
        selection=selection,
        kind=kind,
        page_number=payload.page_number,
        page_context=page_context,
        related=related,
        language=payload.language,
        question=question,
        previous_explanation=payload.previous_explanation,
    )
    try:
        result = selection_explainer.explain(messages, follow_up=bool(question), user_id=current_user.id)
    except selection_explainer.ExplainError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    record_usage(db, current_user.id, "message")
    sources = [ExplainSource(page_number=payload.page_number, text=page_context[:300])] if page_context else []
    sources += [
        ExplainSource(page_number=r["page_number"], text=r["text"][:300])
        for r in related[: selection_explainer.MAX_RELATED_PASSAGES]
    ]
    return ExplainSelectionResponse(kind=kind, selected_text=selection, sources=sources, **result)


@router.patch("/{document_id}", response_model=DocumentListItem)
def rename_document(
    document_id: uuid.UUID,
    payload: RenameDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    document = _get_owned_document(db, document_id, current_user.id)
    name = " ".join(payload.filename.split())
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a name.")
    if any(c in name for c in ("/", "\\", "\x00")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Names can't contain slashes.")
    # Keep the file extension so the type icon and media handling stay correct.
    ext = f".{document.file_type}" if document.file_type else ""
    if ext and not name.lower().endswith(ext.lower()):
        name = f"{name}{ext}"
    document.filename = name[:200]
    db.commit()
    db.refresh(document)
    return document


@router.post("/{document_id}/retry", response_model=DocumentStatusResponse)
def retry_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    """Re-run processing for a document that failed. Only `failed` can be retried: a
    document that is still processing must never get a second parse job."""
    document = _get_owned_document(db, document_id, current_user.id)
    if document.status != DocumentStatus.failed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a failed document can be retried.")
    file_path = document.storage_path
    if file_path and not os.path.isfile(file_path):
        download_dir(f"{document.user_id}/{document.id}", Path(file_path).parent)
    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The original file is no longer available. Please upload it (or add the link) again.",
        )
    try:
        delete_vector_chunks(document.id)
    except Exception:
        logger.warning("Couldn't clear old chunks before retrying %s", document.id, exc_info=True)
    document.status = DocumentStatus.uploaded
    document.error_message = None
    db.commit()
    background_tasks.add_task(run_parsing_task, document.id, file_path, document.file_type, True)
    return DocumentStatusResponse(
        id=document.id, status=document.status, page_count=document.page_count, filename=document.filename
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
    if file_path and not os.path.isfile(file_path):
        # Local disk may have been wiped since this was written — restore from R2 if configured.
        download_dir(f"{document.user_id}/{document.id}", Path(file_path).parent)
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
