import json
import logging
import threading
import uuid
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.orm import Session

from app.admin.config_service import get_config_value
from app.core.config import settings
from app.core.database import SessionLocal
from app.documents.object_storage import upload_dir
from app.documents.parsers import parse_file
from app.documents.video_url import download_audio_from_url
from app.models import ContentReport, Document, DocumentStatus
from app.rag.chunking import chunk_text
from app.rag.summarizer import generate_document_summary
from app.rag.vectorstore import add_chunks

logger = logging.getLogger(__name__)

# Render's free tier has only 512MB RAM. Parsing/embedding (and Whisper transcription for
# audio/video) each load models and hold buffers that can spike well past what's safe to
# run twice at once — two users uploading around the same time could run their parse jobs
# concurrently and OOM-kill the whole process (every other in-flight document then gets
# stuck "processing" until fail_interrupted_documents() marks it failed on the next
# restart). Serializing to one parse job at a time trades a bit of latency for the second
# uploader for not crashing the server under both of them.
_parse_semaphore = threading.Semaphore(1)

# A job that hangs (rather than cleanly failing) would otherwise hold the semaphore
# forever, silently queuing every later upload behind it indefinitely — including ones
# that would parse almost instantly on their own (e.g. a .pptx queued behind a stuck
# image OCR job). Bounding the wait means a stuck job can only ever block others for a
# few minutes, not the rest of the process's lifetime.
MAX_QUEUE_WAIT_SECONDS = 300


def parsed_text_path(document_dir: Path) -> Path:
    return document_dir / "parsed.json"


def _mark_failed_busy(document_id: uuid.UUID) -> None:
    db: Session = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = DocumentStatus.failed
            db.commit()
    finally:
        db.close()
    logger.error("Document %s timed out waiting for a busy server to free up", document_id)


def run_parsing_task(document_id: uuid.UUID, file_path: str, extension: str) -> None:
    if not _parse_semaphore.acquire(timeout=MAX_QUEUE_WAIT_SECONDS):
        _mark_failed_busy(document_id)
        return
    try:
        _run_parsing_task(document_id, file_path, extension)
    finally:
        _parse_semaphore.release()


def _run_parsing_task(document_id: uuid.UUID, file_path: str, extension: str) -> None:
    db: Session = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error("Document %s not found for parsing", document_id)
            return

        document.status = DocumentStatus.parsing
        db.commit()

        try:
            pages = parse_file(file_path, extension)
        except Exception:
            logger.exception("Failed to parse document %s", document_id)
            document.status = DocumentStatus.failed
            db.commit()
            return

        page_dicts = [
            {
                "page_number": p.page_number,
                "text": p.text,
                "tables": [asdict(t) for t in p.tables],
                "start_time": p.start_time,
                "end_time": p.end_time,
            }
            for p in pages
        ]
        output_path = parsed_text_path(Path(file_path).parent)
        output_path.write_text(json.dumps(page_dicts), encoding="utf-8")

        document.page_count = len(pages)
        db.commit()

        # Back up the original file + parsed text now that both exist on local disk — a
        # no-op unless R2_* is configured (see app/documents/object_storage.py).
        upload_dir(f"{document.user_id}/{document.id}", Path(file_path).parent)

        try:
            full_text = "\n".join(p.text for p in pages).lower()
            keywords = get_config_value("moderation").get("flag_keywords", [])
            matched = next((kw for kw in keywords if kw.lower() in full_text), None)
            if matched:
                db.add(
                    ContentReport(
                        document_id=document.id,
                        reporter_user_id=None,
                        reason="other",
                        details=f"Auto-flagged: matched configured keyword pattern ({matched!r}).",
                        auto_flagged=True,
                    )
                )
                db.commit()
        except Exception:
            logger.exception("Auto-flag keyword check failed for document %s", document_id)

        try:
            chunks = chunk_text(page_dicts, document.id, document.user_id, document.filename)
            add_chunks(document.id, document.user_id, chunks)
        except Exception:
            logger.exception("Failed to embed document %s", document_id)
            document.status = DocumentStatus.failed
            db.commit()
            return

        document.status = DocumentStatus.embedded
        db.commit()

        # Summary/suggested-questions are a nice-to-have on top of a searchable document —
        # a failure here shouldn't block the document from being usable in chat.
        try:
            summary_result = generate_document_summary(document.id)
            if summary_result:
                document.summary = summary_result["summary"]
                document.suggested_questions = summary_result["suggested_questions"]
        except Exception:
            logger.exception("Failed to generate summary for document %s", document_id)

        document.status = DocumentStatus.ready
        db.commit()
    finally:
        db.close()


def run_url_ingest_task(document_id: uuid.UUID, url: str) -> None:
    """Download a video/audio URL (YouTube or any yt-dlp-supported site), extract its
    audio, then hand off to the normal parsing pipeline exactly as if it had been an
    uploaded audio file. Holds the same parse semaphore across download+parse (not just
    the parse half) — yt-dlp/ffmpeg download is itself memory/CPU heavy."""
    if not _parse_semaphore.acquire(timeout=MAX_QUEUE_WAIT_SECONDS):
        _mark_failed_busy(document_id)
        return
    try:
        _run_url_ingest_task(document_id, url)
    finally:
        _parse_semaphore.release()


def _run_url_ingest_task(document_id: uuid.UUID, url: str) -> None:
    db: Session = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error("Document %s not found for URL ingest", document_id)
            return

        document.status = DocumentStatus.parsing
        db.commit()

        try:
            dest_dir = Path(settings.STORAGE_PATH) / str(document.user_id) / str(document.id)
            file_path, title = download_audio_from_url(url, dest_dir)
        except Exception:
            logger.exception("Failed to download video from URL for document %s", document_id)
            document.status = DocumentStatus.failed
            db.commit()
            return

        document.filename = f"{title}.wav"
        document.storage_path = file_path
        db.commit()

        # Same reasoning as the upload path in upload_service.py: back up the downloaded
        # audio now, not only after parsing succeeds, so an interruption mid-parse doesn't
        # leave nothing to retry from.
        upload_dir(f"{document.user_id}/{document.id}", Path(file_path).parent)
    finally:
        db.close()

    _run_parsing_task(document_id, file_path, "wav")


def fail_interrupted_documents() -> int:
    """Startup hook: BackgroundTasks don't survive a process restart (a redeploy, a crash,
    Render's free tier spinning down), so any document still in a non-terminal status
    belongs to a job that was killed mid-flight — it would otherwise sit as "processing"
    forever with no way for the user to know it's actually stuck. Mirrors
    app.voice.clone_background.fail_interrupted_jobs."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Document)
            .filter(Document.status.in_([DocumentStatus.uploaded, DocumentStatus.parsing, DocumentStatus.embedded]))
            .all()
        )
        for doc in rows:
            # "embedded" means chunking/embedding already succeeded (only the
            # best-effort summary step was interrupted) — the document is actually
            # already searchable, so promote it rather than discarding usable work.
            doc.status = DocumentStatus.ready if doc.status == DocumentStatus.embedded else DocumentStatus.failed
        db.commit()
        return len(rows)
    except Exception:
        logger.exception("Could not clean up interrupted document processing jobs")
        db.rollback()
        return 0
    finally:
        db.close()
