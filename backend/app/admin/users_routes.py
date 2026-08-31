import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.admin.audit import log_admin_action
from app.admin.plans_schemas import PlanLimits
from app.admin.users_schemas import (
    ActivityItem,
    AdminChatSummary,
    AdminDocumentSummary,
    AdminQueryLogItem,
    AdminQuizAttemptSummary,
    AdminUserDetail,
    AdminUserListItem,
    BlockUserRequest,
    DeleteUserRequest,
    ImpersonateResponse,
    QuotaUsageItem,
    RecentErrorItem,
    UpdateCustomLimitsRequest,
    UpdateNotesRequest,
    UpdateUserPlanRequest,
    UserLimitsResponse,
)
from app.core.database import get_db
from app.core.limits import get_effective_limits
from app.core.security import create_impersonation_token, get_current_admin, require_role
from app.core.usage import rolling_quota_usage
from app.documents.storage import delete_document_files
from app.models import (
    APICallLog,
    Chat,
    Document,
    Message,
    Plan,
    QueryLog,
    Quiz,
    QuizAttempt,
    RateLimitViolation,
    UsageEvent,
    User,
    Workspace,
)
from app.rag.vectorstore import delete_document as delete_vector_chunks

router = APIRouter(prefix="/admin/users", tags=["admin-users"], dependencies=[Depends(get_current_admin)])


def _get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@router.get("/", response_model=list[AdminUserListItem])
def list_users(
    q: str | None = Query(None, description="Search by name or email"),
    is_verified: bool | None = Query(None),
    is_admin: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like)))
    if is_verified is not None:
        query = query.filter(User.is_verified == is_verified)
    if is_admin is not None:
        query = query.filter(User.is_admin == is_admin)

    users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for user in users:
        doc_count = db.query(Document).filter(Document.user_id == user.id).count()
        message_count = (
            db.query(Message).join(Chat, Chat.id == Message.chat_id).filter(Chat.user_id == user.id).count()
        )
        last_message = (
            db.query(Message.created_at)
            .join(Chat, Chat.id == Message.chat_id)
            .filter(Chat.user_id == user.id)
            .order_by(Message.created_at.desc())
            .first()
        )
        items.append(
            AdminUserListItem(
                id=user.id,
                name=user.name,
                email=user.email,
                is_verified=user.is_verified,
                is_blocked=user.is_blocked,
                is_admin=user.is_admin,
                created_at=user.created_at,
                last_active=last_message[0] if last_message else None,
                document_count=doc_count,
                message_count=message_count,
            )
        )
    return items


@router.get("/{user_id}", response_model=AdminUserDetail)
def get_user_detail(user_id: uuid.UUID, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)

    documents = db.query(Document).filter(Document.user_id == user.id).order_by(Document.created_at.desc()).all()
    chats = db.query(Chat).filter(Chat.user_id == user.id).order_by(Chat.created_at.desc()).all()
    chat_summaries = []
    for chat in chats:
        count = db.query(Message).filter(Message.chat_id == chat.id).count()
        chat_summaries.append(
            AdminChatSummary(id=chat.id, title=chat.title, message_count=count, created_at=chat.created_at)
        )

    workspaces = db.query(Workspace).filter(Workspace.user_id == user.id).all()

    attempts = (
        db.query(QuizAttempt, Quiz.title)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .filter(QuizAttempt.user_id == user.id)
        .order_by(QuizAttempt.taken_at.desc())
        .limit(20)
        .all()
    )
    quiz_summaries = [
        AdminQuizAttemptSummary(quiz_title=title, score=attempt.score, taken_at=attempt.taken_at)
        for attempt, title in attempts
    ]

    recent_logs = (
        db.query(QueryLog).filter(QueryLog.user_id == user.id).order_by(QueryLog.created_at.desc()).limit(20).all()
    )

    blocked_by_name = None
    if user.blocked_by:
        blocker = db.query(User).filter(User.id == user.blocked_by).first()
        blocked_by_name = blocker.name if blocker else None
    elif user.is_blocked:
        blocked_by_name = "System"

    plan = db.query(Plan).filter(Plan.id == user.plan_id).first() if user.plan_id else None

    return AdminUserDetail(
        id=user.id,
        name=user.name,
        email=user.email,
        is_verified=user.is_verified,
        is_blocked=user.is_blocked,
        blocked_reason=user.blocked_reason,
        blocked_at=user.blocked_at,
        blocked_by_name=blocked_by_name,
        is_admin=user.is_admin,
        admin_role=user.admin_role,
        admin_notes=user.admin_notes,
        created_at=user.created_at,
        plan_id=user.plan_id,
        plan_name=plan.name if plan else None,
        documents=[
            AdminDocumentSummary(id=d.id, filename=d.filename, status=d.status.value, created_at=d.created_at)
            for d in documents
        ],
        chats=chat_summaries,
        workspace_names=[w.name for w in workspaces],
        quiz_attempts=quiz_summaries,
        recent_queries=[
            AdminQueryLogItem(question=log.question, was_answered=log.was_answered, created_at=log.created_at)
            for log in recent_logs
        ],
    )


@router.post("/{user_id}/verify", status_code=status.HTTP_204_NO_CONTENT)
def verify_user(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    user.is_verified = True
    log_admin_action(
        db, admin.id, "user.verify", target_id=str(user.id), ip_address=request.client.host if request.client else None
    )
    db.commit()


@router.post("/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT)
def block_user(
    user_id: uuid.UUID,
    payload: BlockUserRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    if user.is_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block an admin account.")
    user.is_blocked = True
    user.blocked_reason = payload.reason
    user.blocked_at = datetime.now(timezone.utc)
    user.blocked_by = admin.id
    log_admin_action(
        db,
        admin.id,
        "user.block",
        target_id=str(user.id),
        details={"reason": payload.reason},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()


@router.post("/{user_id}/unblock", status_code=status.HTTP_204_NO_CONTENT)
def unblock_user(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    user.is_blocked = False
    user.blocked_reason = None
    user.blocked_at = None
    user.blocked_by = None

    # Clear recent violations so the user doesn't immediately re-trigger auto-block.
    db.query(RateLimitViolation).filter(RateLimitViolation.user_id == user.id).delete()

    log_admin_action(
        db, admin.id, "user.unblock", target_id=str(user.id), ip_address=request.client.host if request.client else None
    )
    db.commit()


@router.get("/{user_id}/limits", response_model=UserLimitsResponse)
def get_user_limits(user_id: uuid.UUID, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)
    plan = db.query(Plan).filter(Plan.id == user.plan_id).first() if user.plan_id else None
    effective = get_effective_limits(user)

    usage_items = [QuotaUsageItem(**item) for item in rolling_quota_usage(db, user)]

    doc_count = db.query(Document).filter(Document.user_id == user.id).count()
    workspace_count = db.query(Workspace).filter(Workspace.user_id == user.id).count()
    usage_items.append(
        QuotaUsageItem(
            key="max_documents", label="Documents", limit=effective.get("max_documents"), current_usage=doc_count
        )
    )
    usage_items.append(
        QuotaUsageItem(
            key="max_workspaces",
            label="Workspaces",
            limit=effective.get("max_workspaces"),
            current_usage=workspace_count,
        )
    )

    return UserLimitsResponse(
        plan_id=user.plan_id,
        plan_name=plan.name if plan else None,
        custom_limits=user.custom_limits,
        effective_limits=PlanLimits(**effective),
        usage=usage_items,
    )


@router.patch("/{user_id}/plan", status_code=status.HTTP_204_NO_CONTENT)
def update_user_plan(
    user_id: uuid.UUID,
    payload: UpdateUserPlanRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    plan = db.query(Plan).filter(Plan.id == payload.plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
    user.plan_id = plan.id
    log_admin_action(
        db,
        admin.id,
        "user.plan_change",
        target_id=str(user.id),
        details={"plan_id": str(plan.id), "plan_name": plan.name},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()


@router.patch("/{user_id}/custom-limits", status_code=status.HTTP_204_NO_CONTENT)
def update_user_custom_limits(
    user_id: uuid.UUID,
    payload: UpdateCustomLimitsRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    merged = dict(user.custom_limits or {})
    merged.update(payload.custom_limits)
    user.custom_limits = merged
    log_admin_action(
        db,
        admin.id,
        "user.custom_limits_update",
        target_id=str(user.id),
        details={"custom_limits": payload.custom_limits},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()


@router.delete("/{user_id}/custom-limits", status_code=status.HTTP_204_NO_CONTENT)
def clear_user_custom_limits(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    user.custom_limits = None
    log_admin_action(
        db,
        admin.id,
        "user.custom_limits_clear",
        target_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()


@router.post("/{user_id}/reset-usage", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_usage(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    deleted = db.query(UsageEvent).filter(UsageEvent.user_id == user.id).delete()
    log_admin_action(
        db,
        admin.id,
        "user.reset_usage",
        target_id=str(user.id),
        details={"events_deleted": deleted},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()


@router.patch("/{user_id}/notes", status_code=status.HTTP_204_NO_CONTENT)
def update_notes(
    user_id: uuid.UUID,
    payload: UpdateNotesRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    user.admin_notes = payload.notes
    log_admin_action(
        db, admin.id, "user.notes_update", target_id=str(user.id), ip_address=request.client.host if request.client else None
    )
    db.commit()


@router.post("/{user_id}/impersonate", response_model=ImpersonateResponse)
def impersonate_user(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(require_role("superadmin", "support")),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    if user.is_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot impersonate an admin account.")

    token = create_impersonation_token(user.id, user.email, admin.id)
    log_admin_action(
        db,
        admin.id,
        "user.impersonate_start",
        target_id=str(user.id),
        details={"expires_in_minutes": 10},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return ImpersonateResponse(access_token=token, user_email=user.email)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    payload: DeleteUserRequest,
    request: Request,
    admin: User = Depends(require_role("superadmin")),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    if user.is_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete an admin account.")
    if payload.confirm_email.strip().lower() != user.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email confirmation does not match.")

    document_ids = [d.id for d in db.query(Document.id).filter(Document.user_id == user.id).all()]

    # Log BEFORE executing the delete — the whole point is having a record even though
    # the underlying data will be gone immediately after this.
    log_admin_action(
        db,
        admin.id,
        "user.delete",
        target_id=str(user.id),
        details={"email": user.email, "document_count": len(document_ids)},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    for doc_id in document_ids:
        try:
            delete_document_files(user.id, doc_id)
            delete_vector_chunks(doc_id)
        except Exception:
            pass  # best-effort file/vector cleanup — the DB cascade below is authoritative

    # Workspace and Quiz have no ORM-level cascade from User (they're FKs without
    # ondelete=CASCADE), so delete them explicitly first to avoid an FK violation —
    # each of THEIR children (WorkspaceDocument, QuizAttempt) does cascade correctly.
    for workspace in db.query(Workspace).filter(Workspace.user_id == user.id).all():
        db.delete(workspace)
    for quiz in db.query(Quiz).filter(Quiz.user_id == user.id).all():
        db.delete(quiz)
    db.query(QuizAttempt).filter(QuizAttempt.user_id == user.id).delete()
    db.query(QueryLog).filter(QueryLog.user_id == user.id).delete()
    db.query(APICallLog).filter(APICallLog.user_id == user.id).update({"user_id": None})

    db.delete(user)
    db.commit()


@router.get("/{user_id}/recent-errors", response_model=list[RecentErrorItem])
def recent_errors(user_id: uuid.UUID, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)

    unanswered = (
        db.query(QueryLog)
        .filter(QueryLog.user_id == user.id, QueryLog.was_answered.is_(False))
        .order_by(QueryLog.created_at.desc())
        .limit(20)
        .all()
    )
    failed_calls = (
        db.query(APICallLog)
        .filter(APICallLog.user_id == user.id, APICallLog.success.is_(False))
        .order_by(APICallLog.created_at.desc())
        .limit(20)
        .all()
    )

    items = [
        RecentErrorItem(kind="query", detail=f'Unanswered: "{log.question}"', created_at=log.created_at)
        for log in unanswered
    ]
    items += [
        RecentErrorItem(
            kind="api_call",
            detail=f"{call.provider} / {call.endpoint_or_purpose}: {call.error_message or 'unknown error'}",
            created_at=call.created_at,
        )
        for call in failed_calls
    ]
    items.sort(key=lambda i: i.created_at, reverse=True)
    return items[:20]


@router.get("/{user_id}/recent-activity", response_model=list[ActivityItem])
def recent_activity(user_id: uuid.UUID, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)

    items: list[ActivityItem] = []

    for doc in db.query(Document).filter(Document.user_id == user.id).order_by(Document.created_at.desc()).limit(20).all():
        items.append(ActivityItem(kind="document_upload", detail=doc.filename, created_at=doc.created_at))

    for chat in db.query(Chat).filter(Chat.user_id == user.id).order_by(Chat.created_at.desc()).limit(20).all():
        items.append(
            ActivityItem(kind="chat_created", detail=chat.title or "Untitled chat", created_at=chat.created_at)
        )

    for log in (
        db.query(QueryLog).filter(QueryLog.user_id == user.id).order_by(QueryLog.created_at.desc()).limit(20).all()
    ):
        items.append(
            ActivityItem(
                kind="error" if not log.was_answered else "query",
                detail=log.question,
                created_at=log.created_at,
            )
        )

    items.sort(key=lambda i: i.created_at, reverse=True)
    return items[:40]
