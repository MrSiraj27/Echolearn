import os
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.admin.audit import log_admin_action
from app.admin.system_schemas import (
    BlockedUserItem,
    FailedJob,
    JobHealthResponse,
    ProviderStat,
    PurposeBreakdown,
    StorageResponse,
    StuckJob,
    TopUser,
    UsageOverviewResponse,
    UserStorageItem,
)
from app.core.database import get_db
from app.core.security import get_current_admin
from app.documents.background import run_parsing_task
from app.models import APICallLog, Document, DocumentStatus, User
from app.rag.vectorstore import delete_document as delete_vector_chunks

router = APIRouter(prefix="/admin/system", tags=["admin-system"], dependencies=[Depends(get_current_admin)])

# How long a document can sit in an in-progress status before we consider the
# background job silently stuck/failed.
STUCK_THRESHOLD_MINUTES = {
    "uploaded": 15,
    "parsing": 15,
    "embedded": 15,
}


@router.get("/usage-overview", response_model=UsageOverviewResponse)
def usage_overview(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    all_recent = db.query(APICallLog).filter(APICallLog.created_at >= month_start).all()

    def _tz(dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    calls_today = sum(1 for c in all_recent if _tz(c.created_at) >= today_start)
    calls_this_week = sum(1 for c in all_recent if _tz(c.created_at) >= week_start)
    calls_this_month = len(all_recent)

    by_provider: dict[str, list[APICallLog]] = defaultdict(list)
    for c in all_recent:
        by_provider[c.provider].append(c)

    provider_stats = []
    for provider, calls in by_provider.items():
        errors = sum(1 for c in calls if not c.success)
        durations = [c.duration_ms for c in calls if c.duration_ms is not None]
        provider_stats.append(
            ProviderStat(
                provider=provider,
                total_calls=len(calls),
                error_count=errors,
                error_rate=round(100 * errors / len(calls), 1) if calls else 0.0,
                avg_duration_ms=round(sum(durations) / len(durations), 1) if durations else None,
            )
        )

    purpose_counts = Counter(c.endpoint_or_purpose for c in all_recent)
    purpose_breakdown = [
        PurposeBreakdown(purpose=p, count=n) for p, n in sorted(purpose_counts.items(), key=lambda x: -x[1])
    ]

    user_counts = Counter(c.user_id for c in all_recent if c.user_id)
    top_users = []
    for user_id, count in user_counts.most_common(10):
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            top_users.append(TopUser(user_id=user.id, email=user.email, call_count=count))

    return UsageOverviewResponse(
        calls_today=calls_today,
        calls_this_week=calls_this_week,
        calls_this_month=calls_this_month,
        provider_stats=provider_stats,
        purpose_breakdown=purpose_breakdown,
        top_users=top_users,
    )


@router.get("/job-health", response_model=JobHealthResponse)
def job_health(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    in_progress = (
        db.query(Document)
        .filter(Document.status.in_([DocumentStatus.uploaded, DocumentStatus.parsing, DocumentStatus.embedded]))
        .all()
    )

    stuck_jobs = []
    for doc in in_progress:
        created_at = doc.created_at if doc.created_at.tzinfo else doc.created_at.replace(tzinfo=timezone.utc)
        minutes = (now - created_at).total_seconds() / 60
        threshold = STUCK_THRESHOLD_MINUTES.get(doc.status.value, 15)
        if minutes >= threshold:
            user = db.query(User).filter(User.id == doc.user_id).first()
            stuck_jobs.append(
                StuckJob(
                    document_id=doc.id,
                    filename=doc.filename,
                    user_email=user.email if user else "unknown",
                    status=doc.status.value,
                    stuck_for_minutes=round(minutes, 1),
                )
            )

    failed = db.query(Document).filter(Document.status == DocumentStatus.failed).order_by(Document.created_at.desc()).limit(50).all()
    failed_jobs = []
    for doc in failed:
        user = db.query(User).filter(User.id == doc.user_id).first()
        failed_jobs.append(
            FailedJob(
                document_id=doc.id, filename=doc.filename, user_email=user.email if user else "unknown", created_at=doc.created_at
            )
        )

    return JobHealthResponse(stuck_jobs=stuck_jobs, failed_jobs=failed_jobs)


@router.post("/documents/{document_id}/retry-processing", status_code=status.HTTP_204_NO_CONTENT)
def retry_document_processing(
    document_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    try:
        delete_vector_chunks(document.id)
    except Exception:
        pass

    document.status = DocumentStatus.uploaded
    log_admin_action(
        db,
        admin.id,
        "document.retry_processing",
        target_id=str(document.id),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    background_tasks.add_task(run_parsing_task, document.id, document.storage_path, document.file_type)


@router.get("/storage", response_model=StorageResponse)
def storage_overview(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    documents = db.query(Document).all()
    by_user: dict[uuid.UUID, list[Document]] = defaultdict(list)
    for doc in documents:
        by_user[doc.user_id].append(doc)

    total_bytes = 0
    items = []
    for user_id, docs in by_user.items():
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            continue
        user_bytes = 0
        for doc in docs:
            try:
                if doc.storage_path and os.path.isfile(doc.storage_path):
                    user_bytes += os.path.getsize(doc.storage_path)
            except OSError:
                pass
        total_bytes += user_bytes
        items.append(UserStorageItem(user_id=user.id, email=user.email, document_count=len(docs), bytes_used=user_bytes))

    items.sort(key=lambda i: i.bytes_used, reverse=True)
    return StorageResponse(total_bytes=total_bytes, by_user=items)


@router.get("/blocked-users", response_model=list[BlockedUserItem])
def blocked_users(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_blocked.is_(True)).order_by(User.blocked_at.desc()).all()
    items = []
    for user in users:
        blocked_by_name = None
        if user.blocked_by:
            blocker = db.query(User).filter(User.id == user.blocked_by).first()
            blocked_by_name = blocker.name if blocker else None
        items.append(
            BlockedUserItem(
                id=user.id,
                name=user.name,
                email=user.email,
                blocked_reason=user.blocked_reason,
                blocked_at=user.blocked_at,
                blocked_by_name=blocked_by_name or "System",
                is_auto_blocked=user.blocked_by is None,
            )
        )
    return items
