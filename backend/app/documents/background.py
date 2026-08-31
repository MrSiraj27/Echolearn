import json
import logging
import uuid
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.orm import Session

from app.admin.config_service import get_config_value
from app.core.config import settings
from app.core.database import SessionLocal
from app.documents.parsers import parse_file
from app.documents.video_url import download_audio_from_url
from app.models import ContentReport, Document, DocumentStatus
from app.rag.chunking import chunk_text
from app.rag.summarizer import generate_document_summary
from app.rag.vectorstore import add_chunks

logger = logging.getLogger(__name__)


def parsed_text_path(document_dir: Path) -> Path:
    return document_dir / "parsed.json"


def run_parsing_task(document_id: uuid.UUID, file_path: str, extension: str) -> None:
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
    uploaded audio file."""
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
    finally:
        db.close()

    run_parsing_task(document_id, file_path, "wav")
