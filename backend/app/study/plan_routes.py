import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import (
    Document,
    StudyPlan,
    StudyPlanStatus,
    StudySession,
    StudySessionStatus,
    StudySessionType,
    User,
    Workspace,
    WorkspaceDocument,
)
from app.rag.study_planner import compress_remaining_sessions, create_plan_rows, generate_session_content, preview_plan
from app.study.card_service import create_review_cards
from app.study.schemas import (
    CreateStudyPlanRequest,
    PlanStatusResponse,
    PlanWarning,
    PreviewStudyPlanRequest,
    PreviewStudyPlanResponse,
    SessionContentResponse,
    SessionPreview,
    StudyPlanDetailResponse,
    StudyPlanResponse,
    StudySessionPublic,
    TodaySessionItem,
    TopicPreview,
)

router = APIRouter(prefix="/study-plans", tags=["study-plans"])

# Behind-schedule thresholds for GET /study-plans/{id}/status: "on_track" requires
# having completed everything scheduled up to today; below that, 70% completion of
# what's expected by now still reads as "slightly" rather than "significantly" behind
# — a couple of skipped/missed sessions shouldn't feel alarming, a large backlog should.
SLIGHTLY_BEHIND_RATIO = 0.7


def _resolve_document_ids(db: Session, user: User, document_ids: list[uuid.UUID] | None, workspace_id: uuid.UUID | None) -> list[uuid.UUID]:
    if workspace_id:
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id, Workspace.user_id == user.id).first()
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
        return [
            row.document_id
            for row in db.query(WorkspaceDocument).filter(WorkspaceDocument.workspace_id == workspace_id).all()
        ]

    if document_ids:
        count = db.query(Document).filter(Document.id.in_(document_ids), Document.user_id == user.id).count()
        if count != len(set(document_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more documents not found.")
        return document_ids

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide document_ids or a workspace_id.")


def _get_owned_plan(db: Session, plan_id: uuid.UUID, user_id: uuid.UUID) -> StudyPlan:
    plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id, StudyPlan.user_id == user_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study plan not found.")
    return plan


def _to_plan_response(plan: StudyPlan) -> StudyPlanResponse:
    sessions = plan.sessions
    return StudyPlanResponse(
        id=plan.id,
        title=plan.title,
        exam_date=plan.exam_date,
        document_ids=[uuid.UUID(d) for d in plan.document_ids] if plan.document_ids else None,
        workspace_id=plan.workspace_id,
        daily_study_minutes=plan.daily_study_minutes,
        status=plan.status.value,
        created_at=plan.created_at,
        session_count=len(sessions),
        completed_count=sum(1 for s in sessions if s.status == StudySessionStatus.completed),
    )


@router.post("/preview", response_model=PreviewStudyPlanResponse)
def preview_study_plan(
    payload: PreviewStudyPlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.exam_date <= date.today():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exam date must be in the future.")

    document_ids = _resolve_document_ids(db, current_user, payload.document_ids, payload.workspace_id)
    if not document_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No documents to build a plan from.")

    result = preview_plan(document_ids, current_user.id, payload.title, payload.exam_date, payload.daily_study_minutes)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't generate a study plan from this material right now. Please try again.",
        )

    return PreviewStudyPlanResponse(
        plan_token=result["plan_token"],
        topics=[TopicPreview(**{k: t[k] for k in ("title", "description", "estimated_difficulty")}) for t in result["topics"]],
        sessions=[
            SessionPreview(
                scheduled_date=s["scheduled_date"],
                topic_title=s["topic_title"],
                topic_description=s["topic_description"],
                session_type=s["session_type"],
            )
            for s in result["sessions"]
        ],
        warning=PlanWarning(**result["warning"]) if result["warning"] else None,
    )


@router.post("/", response_model=StudyPlanResponse, status_code=status.HTTP_201_CREATED)
def create_study_plan(
    payload: CreateStudyPlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_ids = None
    if payload.workspace_id or payload.document_ids:
        document_ids = _resolve_document_ids(db, current_user, payload.document_ids, payload.workspace_id)

    try:
        plan = create_plan_rows(
            db, current_user, document_ids, payload.workspace_id, payload.plan_token, payload.reduced_topic_titles
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _to_plan_response(plan)


@router.get("/", response_model=list[StudyPlanResponse])
def list_study_plans(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plans = db.query(StudyPlan).filter(StudyPlan.user_id == current_user.id).order_by(StudyPlan.created_at.desc()).all()
    return [_to_plan_response(p) for p in plans]


@router.get("/today", response_model=list[TodaySessionItem])
def get_today_sessions_all_plans(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Today's scheduled session(s) across ALL of this user's active plans — for the
    dashboard's "Today's Study Session" card, which doesn't know/care which plan."""
    today = date.today()
    rows = (
        db.query(StudySession, StudyPlan)
        .join(StudyPlan, StudyPlan.id == StudySession.plan_id)
        .filter(
            StudyPlan.user_id == current_user.id,
            StudyPlan.status == StudyPlanStatus.active,
            StudySession.scheduled_date == today,
            StudySession.status == StudySessionStatus.pending,
        )
        .order_by(StudyPlan.exam_date.asc())
        .all()
    )
    return [
        TodaySessionItem(plan_id=plan.id, plan_title=plan.title, session=StudySessionPublic.model_validate(session))
        for session, plan in rows
    ]


@router.get("/{plan_id}", response_model=StudyPlanDetailResponse)
def get_study_plan(plan_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = _get_owned_plan(db, plan_id, current_user.id)
    base = _to_plan_response(plan)
    return StudyPlanDetailResponse(**base.model_dump(), sessions=[StudySessionPublic.model_validate(s) for s in plan.sessions])


@router.get("/{plan_id}/today", response_model=list[StudySessionPublic])
def get_today_sessions_for_plan(
    plan_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    plan = _get_owned_plan(db, plan_id, current_user.id)
    today = date.today()
    return [StudySessionPublic.model_validate(s) for s in plan.sessions if s.scheduled_date == today]


def _get_owned_session(db: Session, plan: StudyPlan, session_id: uuid.UUID) -> StudySession:
    session = db.query(StudySession).filter(StudySession.id == session_id, StudySession.plan_id == plan.id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study session not found.")
    return session


@router.post("/{plan_id}/sessions/{session_id}/complete", response_model=StudySessionPublic)
def complete_session(
    plan_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = _get_owned_plan(db, plan_id, current_user.id)
    session = _get_owned_session(db, plan, session_id)
    session.status = StudySessionStatus.completed
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return StudySessionPublic.model_validate(session)


@router.post("/{plan_id}/sessions/{session_id}/skip", response_model=StudySessionPublic)
def skip_session(
    plan_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = _get_owned_plan(db, plan_id, current_user.id)
    session = _get_owned_session(db, plan, session_id)
    session.status = StudySessionStatus.skipped
    db.commit()
    db.refresh(session)
    return StudySessionPublic.model_validate(session)


@router.get("/{plan_id}/sessions/{session_id}/content", response_model=SessionContentResponse)
def get_session_content(
    plan_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = _get_owned_plan(db, plan_id, current_user.id)
    session = _get_owned_session(db, plan, session_id)

    result = generate_session_content(
        session.source_chunks, session.topic_title, session.topic_description, session.session_type.value
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't generate content for this session right now. Please try again.",
        )

    # Also save each practice question as a ReviewCard (Prompt 30 requirement: study
    # session practice questions feed the same spaced-repetition system).
    document_id = next((c.get("document_id") for c in session.source_chunks if c.get("document_id")), None)
    if document_id:
        card_items = [
            {
                "question": q["question"],
                "answer": q["correct_answer"],
                "question_type": q["type"],
                "options": q.get("options"),
            }
            for q in result["practice_questions"]
        ]
        create_review_cards(db, current_user.id, uuid.UUID(document_id), card_items)

    return SessionContentResponse(
        topic_title=session.topic_title,
        topic_description=session.topic_description,
        session_type=session.session_type.value,
        explanation=result["explanation"],
        practice_questions=result["practice_questions"],
    )


@router.get("/{plan_id}/status", response_model=PlanStatusResponse)
def get_plan_status(plan_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = _get_owned_plan(db, plan_id, current_user.id)
    today = date.today()
    sessions = plan.sessions

    # Strictly before today — sessions scheduled for today are still due today, not yet
    # missed, so a plan can't be "behind schedule" before the user has had a chance to
    # do today's session.
    expected_by_now = [s for s in sessions if s.scheduled_date < today]
    completed = [s for s in sessions if s.status == StudySessionStatus.completed]

    expected_count = len(expected_by_now)
    completed_count = len(completed)

    if expected_count == 0:
        plan_status = "on_track"
    else:
        ratio = completed_count / expected_count
        if ratio >= 1.0:
            plan_status = "on_track"
        elif ratio >= SLIGHTLY_BEHIND_RATIO:
            plan_status = "slightly_behind"
        else:
            plan_status = "significantly_behind"

    return PlanStatusResponse(
        status=plan_status, completed_count=completed_count, expected_by_now_count=expected_count, total_count=len(sessions)
    )


@router.post("/{plan_id}/compress", response_model=StudyPlanDetailResponse)
def compress_plan(plan_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = _get_owned_plan(db, plan_id, current_user.id)
    compress_remaining_sessions(db, plan)
    db.refresh(plan)
    base = _to_plan_response(plan)
    return StudyPlanDetailResponse(**base.model_dump(), sessions=[StudySessionPublic.model_validate(s) for s in plan.sessions])


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def abandon_study_plan(plan_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Soft delete: the model already has an explicit "abandoned" status (unlike
    # documents/workspaces, which hard-delete and have no such field), which is the
    # stronger signal here — abandoning a plan should keep its completed-session
    # history inspectable rather than destroying it.
    plan = _get_owned_plan(db, plan_id, current_user.id)
    plan.status = StudyPlanStatus.abandoned
    db.commit()
