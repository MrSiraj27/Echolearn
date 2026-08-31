import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.admin.audit import log_admin_action
from app.admin.moderation_schemas import AbuseSignal, ContentReportItem, ModerationActionRequest
from app.core.database import get_db
from app.core.rate_limit import snapshot_attempts
from app.core.security import get_current_admin
from app.documents.page_content import load_pages
from app.documents.storage import delete_document_files
from app.models import ContentReport, Document, User
from app.rag.vectorstore import delete_document as delete_vector_chunks

router = APIRouter(prefix="/admin/moderation", tags=["admin-moderation"], dependencies=[Depends(get_current_admin)])


@router.get("/reports", response_model=list[ContentReportItem])
def list_reports(
    status_filter: str | None = None,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(ContentReport)
    if status_filter:
        query = query.filter(ContentReport.status == status_filter)
    reports = query.order_by(ContentReport.created_at.desc()).all()

    items = []
    for report in reports:
        document = db.query(Document).filter(Document.id == report.document_id).first()
        if not document:
            continue
        owner = db.query(User).filter(User.id == document.user_id).first()
        reporter = db.query(User).filter(User.id == report.reporter_user_id).first() if report.reporter_user_id else None

        preview = None
        try:
            pages = load_pages(document)
            if pages:
                preview = (pages[0].get("text") or "")[:500]
        except Exception:
            preview = None

        items.append(
            ContentReportItem(
                id=report.id,
                document_id=document.id,
                document_filename=document.filename,
                document_owner_email=owner.email if owner else "unknown",
                reporter_email=reporter.email if reporter else None,
                reason=report.reason,
                details=report.details,
                status=report.status,
                auto_flagged=report.auto_flagged,
                created_at=report.created_at,
                text_preview=preview,
            )
        )
    return items


@router.post("/reports/{report_id}/action", status_code=status.HTTP_204_NO_CONTENT)
def action_report(
    report_id: uuid.UUID,
    payload: ModerationActionRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    report = db.query(ContentReport).filter(ContentReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    if payload.action not in ("dismiss", "remove_document", "suspend_user"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action.")

    document = db.query(Document).filter(Document.id == report.document_id).first()
    ip = request.client.host if request.client else None

    if payload.action == "dismiss":
        report.status = "dismissed"

    elif payload.action == "remove_document":
        if document:
            try:
                delete_document_files(document.user_id, document.id)
                delete_vector_chunks(document.id)
            except Exception:
                pass
            db.delete(document)
        report.status = "actioned"

    elif payload.action == "suspend_user":
        if document:
            owner = db.query(User).filter(User.id == document.user_id).first()
            if owner and not owner.is_admin:
                owner.is_blocked = True
                owner.blocked_reason = "Blocked via moderation action"
                owner.blocked_at = datetime.now(timezone.utc)
                owner.blocked_by = admin.id
        report.status = "actioned"

    log_admin_action(
        db,
        admin.id,
        f"moderation.{payload.action}",
        target_id=str(report.id),
        details={"notes": payload.notes, "document_id": str(report.document_id)},
        ip_address=ip,
    )
    db.commit()


@router.get("/abuse-signals", response_model=list[AbuseSignal])
def abuse_signals(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    attempts = snapshot_attempts()
    now = time.time()
    window = 15 * 60

    # Keys look like "login:email@example.com" or "voice:<user-uuid>" — surface anyone
    # who's hit the rate limit repeatedly in the last window, regardless of which
    # limiter tripped.
    signals: list[AbuseSignal] = []
    for key, timestamps in attempts.items():
        recent = [t for t in timestamps if now - t < window]
        if len(recent) < 5:
            continue
        identifier = key.split(":", 1)[1] if ":" in key else key

        user = None
        try:
            user = db.query(User).filter(User.id == uuid.UUID(identifier)).first()
        except ValueError:
            user = db.query(User).filter(User.email == identifier).first()

        if not user:
            continue

        signals.append(
            AbuseSignal(
                user_id=user.id,
                email=user.email,
                violation_count=len(recent),
                last_violation_at=datetime.fromtimestamp(max(recent), tz=timezone.utc),
            )
        )

    signals.sort(key=lambda s: s.violation_count, reverse=True)
    return signals
