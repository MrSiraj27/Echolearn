import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.security import get_current_user
from app.documents.background import run_parsing_task
from app.documents.parsers import AUDIO_VIDEO_EXTENSIONS
from app.documents.storage import delete_document_files
from app.documents.upload_service import ingest_upload
from app.models import Document, DocumentStatus, PastPaper, PastPaperAnalysisStatus, User
from app.practice.schemas import PastPaperResponse, PastPaperStatusResponse
from app.rag.pattern_analyzer import analyze_past_paper, merge_patterns
from app.rag.vectorstore import delete_document as delete_vector_chunks

router = APIRouter(prefix="/past-papers", tags=["past-papers"])
logger = logging.getLogger(__name__)

MAX_PAST_PAPERS_PER_USER = 10


def run_past_paper_pipeline(
    past_paper_id: uuid.UUID, document_id: uuid.UUID, user_id: uuid.UUID, storage_path: str, extension: str
) -> None:
    """One background task that chains the two stages: (1) the normal document
    parse/chunk/embed pipeline, then (2) structure analysis of the parsed text. Chaining
    them in a single task means the analysis can never start before the text exists."""
    try:
        run_parsing_task(document_id, storage_path, extension)
    except Exception:
        logger.exception("Parsing failed for past paper document %s", document_id)

    db: Session = SessionLocal()
    try:
        past_paper = db.query(PastPaper).filter(PastPaper.id == past_paper_id).first()
        if not past_paper:
            return  # deleted while parsing
        document = db.query(Document).filter(Document.id == document_id).first()
        if document is None or document.status not in (DocumentStatus.embedded, DocumentStatus.ready):
            past_paper.analysis_status = PastPaperAnalysisStatus.failed
            past_paper.error_message = "We couldn't read this file. Try a text-based PDF, DOCX or TXT version."
            db.commit()
            return

        past_paper.analysis_status = PastPaperAnalysisStatus.analyzing
        db.commit()

        try:
            pattern = analyze_past_paper(document_id, user_id)
        except Exception:
            logger.exception("Past paper analysis crashed for %s", past_paper_id)
            pattern = None

        db.expire_all()
        past_paper = db.query(PastPaper).filter(PastPaper.id == past_paper_id).first()
        if not past_paper:
            return
        if pattern:
            past_paper.extracted_pattern = pattern
            past_paper.analysis_status = PastPaperAnalysisStatus.ready
            past_paper.error_message = None
        else:
            past_paper.analysis_status = PastPaperAnalysisStatus.failed
            past_paper.error_message = (
                "We couldn't detect a clear exam structure in this file. You can still set the structure yourself."
            )
        db.commit()
    finally:
        db.close()


def _summary(pattern: dict | None) -> str | None:
    if not pattern:
        return None
    merged = merge_patterns([pattern])
    return merged["summary"] if merged else None


def _to_response(past_paper: PastPaper, document: Document | None) -> PastPaperResponse:
    return PastPaperResponse(
        id=past_paper.id,
        document_id=past_paper.document_id,
        filename=document.filename if document else "(deleted file)",
        exam_name=past_paper.exam_name,
        analysis_status=past_paper.analysis_status.value,
        error_message=past_paper.error_message,
        extracted_pattern=past_paper.extracted_pattern,
        pattern_summary=_summary(past_paper.extracted_pattern),
        created_at=past_paper.created_at,
    )


def _get_owned(db: Session, past_paper_id: uuid.UUID, user_id: uuid.UUID) -> PastPaper:
    past_paper = db.query(PastPaper).filter(PastPaper.id == past_paper_id, PastPaper.user_id == user_id).first()
    if not past_paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Past paper not found.")
    return past_paper


@router.post("/upload", response_model=PastPaperResponse, status_code=status.HTTP_201_CREATED)
async def upload_past_paper(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    exam_name: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    extension = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if extension in AUDIO_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Upload the past paper as a PDF, DOCX, TXT or image file."
        )
    if db.query(PastPaper).filter(PastPaper.user_id == current_user.id).count() >= MAX_PAST_PAPERS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You can keep up to {MAX_PAST_PAPERS_PER_USER} past papers. Delete one to add another.",
        )

    # Same validation, quotas and storage as POST /documents/upload.
    document, storage_path, extension = await ingest_upload(file, None, current_user, db)

    past_paper = PastPaper(
        user_id=current_user.id,
        document_id=document.id,
        exam_name=(exam_name or "").strip()[:120] or None,
        analysis_status=PastPaperAnalysisStatus.pending,
    )
    db.add(past_paper)
    db.commit()
    db.refresh(past_paper)

    background_tasks.add_task(run_past_paper_pipeline, past_paper.id, document.id, current_user.id, storage_path, extension)
    return _to_response(past_paper, document)


@router.get("/", response_model=list[PastPaperResponse])
def list_past_papers(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(PastPaper, Document)
        .outerjoin(Document, Document.id == PastPaper.document_id)
        .filter(PastPaper.user_id == current_user.id)
        .order_by(PastPaper.created_at.desc())
        .all()
    )
    return [_to_response(pp, doc) for pp, doc in rows]


@router.get("/{past_paper_id}/status", response_model=PastPaperStatusResponse)
def get_past_paper_status(
    past_paper_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    past_paper = _get_owned(db, past_paper_id, current_user.id)
    document = db.query(Document).filter(Document.id == past_paper.document_id).first()
    return PastPaperStatusResponse(
        id=past_paper.id,
        analysis_status=past_paper.analysis_status.value,
        document_status=document.status.value if document else None,
        error_message=past_paper.error_message,
        extracted_pattern=past_paper.extracted_pattern,
        pattern_summary=_summary(past_paper.extracted_pattern),
    )


@router.delete("/{past_paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_past_paper(
    past_paper_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Deletes the analysis and the underlying uploaded file (the upload only exists for
    this purpose). Deleting the document cascades to the past_papers row in the DB."""
    past_paper = _get_owned(db, past_paper_id, current_user.id)
    document = db.query(Document).filter(Document.id == past_paper.document_id).first()
    if document:
        delete_document_files(current_user.id, document.id)
        try:
            delete_vector_chunks(document.id)
        except Exception:
            logger.warning("Couldn't delete vectors for past paper document %s", document.id, exc_info=True)
        db.delete(document)
    else:
        db.delete(past_paper)
    db.commit()
