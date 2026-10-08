import hashlib
import json
import logging
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.limits import get_effective_limits
from app.core.security import block_if_impersonating, get_current_user
from app.core.usage import enforce_quota, record_usage
from app.documents.object_storage import download_file, upload_file
from app.models import Document, RevisionSheet, RevisionSheetStatus, User, WorkspaceDocument, Workspace
from app.practice.paper_routes import _validate_source_documents
from app.rag.revision_sheet import RevisionSheetError, generate_revision_sheet
from app.revision.pdf import build_revision_pdf
from app.revision.schemas import (
    CreateRevisionSheetRequest,
    CreateRevisionSheetResponse,
    RevisionSheetListItem,
    RevisionSheetResponse,
    RevisionSheetStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/revision-sheets", tags=["revision-sheets"])

USAGE_EVENT = "revision_sheet"
MAX_TOPICS = 8
STALE_MINUTES = 15  # a job older than this is assumed dead (e.g. the server restarted)
MAX_CONCURRENT_PER_USER = 1

# Cap how many sheets the whole server builds at once: each one makes ~10-15 LLM calls and a
# PDF render, and the free hosts are small. Others wait their turn (up to the timeout below).
_generation_slots = threading.BoundedSemaphore(2)
SLOT_WAIT_SECONDS = 300


def _safe_filename(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_")[:60] or "revision_sheet"


def _sheet_dir(user_id: uuid.UUID) -> Path:
    return Path(settings.STORAGE_PATH) / str(user_id) / "revision"


def _storage_key(user_id: uuid.UUID, sheet_id: uuid.UUID) -> str:
    return f"{user_id}/revision/{sheet_id}.pdf"


def _get_owned(db: Session, sheet_id: uuid.UUID, user_id: uuid.UUID) -> RevisionSheet:
    sheet = db.query(RevisionSheet).filter(RevisionSheet.id == sheet_id, RevisionSheet.user_id == user_id).first()
    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision sheet not found.")
    return sheet


def _clean_topics(topics: list[str] | None) -> list[str]:
    seen: dict[str, str] = {}
    for topic in topics or []:
        cleaned = re.sub(r"\s+", " ", topic).strip()[:60]
        if cleaned:
            seen.setdefault(cleaned.lower(), cleaned)
    return list(seen.values())[:MAX_TOPICS]


def _content_hash(user_id: uuid.UUID, documents: list[Document], topics: list[str], language: str, pages: int, weak: bool) -> str:
    """Identical requests share one result. Documents are identified by id + upload time, so
    re-uploading a changed file (a new document) never reuses an old sheet."""
    payload = {
        "user": str(user_id),
        "docs": sorted(f"{d.id}:{d.created_at.isoformat()}" for d in documents),
        "topics": sorted(t.lower() for t in topics),
        "language": language,
        "pages": pages,
        "weak": weak,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _resolve_documents(db: Session, user: User, payload: CreateRevisionSheetRequest) -> list[uuid.UUID]:
    if payload.workspace_id:
        workspace = db.query(Workspace).filter(Workspace.id == payload.workspace_id, Workspace.user_id == user.id).first()
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
        ids = [
            row.document_id
            for row in db.query(WorkspaceDocument).filter(WorkspaceDocument.workspace_id == workspace.id).all()
        ]
    else:
        ids = list(dict.fromkeys(payload.document_ids))
    # Ownership + readiness are enforced here for every id: another user's document ids are
    # rejected exactly like unknown ones.
    _validate_source_documents(db, user, ids)
    return ids


def _enforce_plan(user: User, payload: CreateRevisionSheetRequest) -> None:
    limits = get_effective_limits(user)
    max_pages = limits.get("revision_sheet_max_pages")
    if max_pages is not None and payload.page_target > max_pages:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your plan allows revision sheets up to {max_pages} page(s). Upgrade for longer sheets.",
        )
    if (payload.language != "en" or payload.include_weak_spots) and not limits.get("revision_sheet_advanced"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Urdu / Roman Urdu / bilingual sheets and weak-spot mode are available on paid plans. Upgrade to use them.",
        )


# ---------------------------------------------------------------- background job


def _fail(db: Session, sheet_id: uuid.UUID, message: str) -> None:
    db.rollback()
    sheet = db.query(RevisionSheet).filter(RevisionSheet.id == sheet_id).first()
    if sheet:
        sheet.status = RevisionSheetStatus.failed
        sheet.error_message = message
        db.commit()


def run_generation_task(sheet_id: uuid.UUID) -> None:
    db: Session = SessionLocal()
    got_slot = _generation_slots.acquire(timeout=SLOT_WAIT_SECONDS)
    try:
        if not got_slot:
            _fail(db, sheet_id, "The server is busy right now. Please try again in a minute.")
            return
        sheet = db.query(RevisionSheet).filter(RevisionSheet.id == sheet_id).first()
        if not sheet:
            return
        user = db.query(User).filter(User.id == sheet.user_id).first()
        sheet.status = RevisionSheetStatus.generating
        db.commit()

        try:
            doc_ids = [uuid.UUID(d) for d in sheet.document_ids]
            names = {str(d.id): d.filename for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()}
            result = generate_revision_sheet(
                db=db,
                user=user,
                title=sheet.title,
                document_ids=doc_ids,
                doc_names=names,
                topics=sheet.topics or [],
                language=sheet.language,
                page_target=sheet.page_target,
                include_weak_spots=sheet.include_weak_spots,
            )
            content = result.content
            pdf_bytes, pages, dropped = build_revision_pdf(content)
            if dropped:
                content["warnings"].append(f"{dropped} lower-priority item(s) were left out to fit {content['page_target']} page(s).")
            content["pages"] = pages
            content["dropped_items"] = dropped

            path = _sheet_dir(sheet.user_id) / f"{sheet.id}.pdf"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(pdf_bytes)
            upload_file(_storage_key(sheet.user_id, sheet.id), str(path))  # best-effort backup; no-op without R2

            db.expire_all()
            sheet = db.query(RevisionSheet).filter(RevisionSheet.id == sheet_id).first()
            if not sheet:
                return
            sheet.content = content
            sheet.pdf_path = str(path)
            sheet.status = RevisionSheetStatus.ready
            sheet.error_message = None
            db.commit()
            # Charged only now, after a fully successful generation: a failure never uses quota.
            record_usage(db, sheet.user_id, USAGE_EVENT)
        except RevisionSheetError as exc:
            _fail(db, sheet_id, str(exc))
        except Exception:
            logger.exception("Revision sheet generation crashed for %s", sheet_id)
            _fail(db, sheet_id, "Something went wrong while generating this sheet. Please try again.")
    finally:
        if got_slot:
            _generation_slots.release()
        db.close()


def fail_interrupted_sheets() -> int:
    """Called at startup: a sheet still queued/generating belongs to a process that no longer
    exists (a restart killed it). Mark it failed so the UI stops spinning; no quota was charged."""
    db = SessionLocal()
    try:
        stuck = (
            db.query(RevisionSheet)
            .filter(RevisionSheet.status.in_([RevisionSheetStatus.queued, RevisionSheetStatus.generating]))
            .all()
        )
        for sheet in stuck:
            sheet.status = RevisionSheetStatus.failed
            sheet.error_message = "This was interrupted by a server restart. Please generate it again."
        db.commit()
        return len(stuck)
    finally:
        db.close()


# ---------------------------------------------------------------- routes


@router.post("/", response_model=CreateRevisionSheetResponse, status_code=status.HTTP_202_ACCEPTED)
def create_sheet(
    payload: CreateRevisionSheetRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    topics = _clean_topics(payload.topics)
    document_ids = _resolve_documents(db, current_user, payload)
    _enforce_plan(current_user, payload)

    documents = db.query(Document).filter(Document.id.in_(document_ids)).all()
    content_hash = _content_hash(
        current_user.id, documents, topics, payload.language, payload.page_target, payload.include_weak_spots
    )

    # Same request as an existing finished sheet -> return it; no generation, no quota.
    cached = (
        None
        if payload.regenerate
        else db.query(RevisionSheet)
        .filter(
            RevisionSheet.user_id == current_user.id,
            RevisionSheet.content_hash == content_hash,
            RevisionSheet.status == RevisionSheetStatus.ready,
        )
        .order_by(RevisionSheet.created_at.desc())
        .first()
    )
    if cached:
        return CreateRevisionSheetResponse(id=cached.id, status=cached.status.value, cached=True)

    in_flight = (
        db.query(RevisionSheet)
        .filter(
            RevisionSheet.user_id == current_user.id,
            RevisionSheet.status.in_([RevisionSheetStatus.queued, RevisionSheetStatus.generating]),
            RevisionSheet.created_at >= datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES),
        )
        .count()
    )
    if in_flight >= MAX_CONCURRENT_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You already have a revision sheet being generated. Wait for it to finish first.",
        )

    enforce_quota(db, current_user, USAGE_EVENT)  # recorded only after a successful generation

    title = (payload.title or "").strip()
    if not title:
        first = sorted(d.filename for d in documents)[0]
        stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", first)
        title = f"Revision sheet - {stem}" + (f" +{len(documents) - 1} more" if len(documents) > 1 else "")

    sheet = RevisionSheet(
        user_id=current_user.id,
        title=title[:120],
        document_ids=[str(d) for d in document_ids],
        workspace_id=payload.workspace_id,
        topics=topics or None,
        language=payload.language,
        page_target=payload.page_target,
        include_weak_spots=payload.include_weak_spots,
        status=RevisionSheetStatus.queued,
        content_hash=content_hash,
    )
    db.add(sheet)
    db.commit()
    db.refresh(sheet)

    background_tasks.add_task(run_generation_task, sheet.id)
    return CreateRevisionSheetResponse(id=sheet.id, status=sheet.status.value, cached=False)


@router.get("/", response_model=list[RevisionSheetListItem])
def list_sheets(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(RevisionSheet)
        .filter(RevisionSheet.user_id == current_user.id)
        .order_by(RevisionSheet.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        RevisionSheetListItem(
            id=r.id, title=r.title, status=r.status.value, language=r.language, page_target=r.page_target,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/{sheet_id}/status", response_model=RevisionSheetStatusResponse)
def sheet_status(sheet_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sheet = _get_owned(db, sheet_id, current_user.id)
    return RevisionSheetStatusResponse(id=sheet.id, status=sheet.status.value, error_message=sheet.error_message)


@router.get("/{sheet_id}", response_model=RevisionSheetResponse)
def get_sheet(sheet_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sheet = _get_owned(db, sheet_id, current_user.id)
    return RevisionSheetResponse(
        id=sheet.id, title=sheet.title, status=sheet.status.value, language=sheet.language,
        page_target=sheet.page_target, include_weak_spots=sheet.include_weak_spots, topics=sheet.topics,
        content=sheet.content, error_message=sheet.error_message, created_at=sheet.created_at,
    )


@router.get("/{sheet_id}/download")
def download_sheet(sheet_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sheet = _get_owned(db, sheet_id, current_user.id)
    if sheet.status != RevisionSheetStatus.ready or not sheet.content:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This revision sheet isn't ready yet.")

    path = _sheet_dir(sheet.user_id) / f"{sheet.id}.pdf"
    if not path.exists():
        # The host's disk may have been wiped by a restart: restore from backup if there is
        # one, otherwise rebuild the PDF from the stored content (always possible).
        path.parent.mkdir(parents=True, exist_ok=True)
        if not download_file(_storage_key(sheet.user_id, sheet.id), str(path)):
            data, _pages, _dropped = build_revision_pdf(sheet.content)
            path.write_bytes(data)
    return Response(
        content=path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(sheet.title)}.pdf"'},
    )


@router.delete("/{sheet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sheet(
    sheet_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    sheet = _get_owned(db, sheet_id, current_user.id)
    path = _sheet_dir(sheet.user_id) / f"{sheet.id}.pdf"
    db.delete(sheet)
    db.commit()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Couldn't remove %s", path, exc_info=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
