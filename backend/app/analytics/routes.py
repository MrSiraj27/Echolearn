import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.analytics.clustering import cluster_unanswered_questions
from app.analytics.schemas import (
    DocumentPerformanceItem,
    KnowledgeGapTheme,
    OverviewResponse,
    QuestionsOverTimePoint,
    QuizInsightQuestion,
    QuizInsightsResponse,
)
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Document, QueryLog, Quiz, QuizAttempt, User, Workspace, WorkspaceDocument
from app.quizzes.routes import _grade_answer

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _verify_workspace_access(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> Workspace:
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id, Workspace.user_id == user_id).first()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return workspace


def _workspace_document_ids(db: Session, workspace_id: uuid.UUID) -> set[str]:
    return {
        str(row.document_id)
        for row in db.query(WorkspaceDocument).filter(WorkspaceDocument.workspace_id == workspace_id).all()
    }


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    workspace_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if workspace_id:
        _verify_workspace_access(db, workspace_id, current_user.id)

    log_query = db.query(QueryLog).filter(QueryLog.user_id == current_user.id)
    if workspace_id:
        log_query = log_query.filter(QueryLog.workspace_id == workspace_id)
    logs = log_query.all()

    if workspace_id:
        total_documents = len(_workspace_document_ids(db, workspace_id))
    else:
        total_documents = db.query(Document).filter(Document.user_id == current_user.id).count()

    quiz_attempts = db.query(QuizAttempt).filter(QuizAttempt.user_id == current_user.id).all()
    avg_quiz_score = round(sum(a.score for a in quiz_attempts) / len(quiz_attempts), 1) if quiz_attempts else None

    doc_counter: Counter = Counter()
    for log in logs:
        for doc_id in log.document_ids or []:
            doc_counter[doc_id] += 1
    most_active_document = None
    if doc_counter:
        top_doc_id = doc_counter.most_common(1)[0][0]
        doc = db.query(Document).filter(Document.id == top_doc_id).first()
        most_active_document = doc.filename if doc else None

    since = datetime.now(timezone.utc) - timedelta(days=30)
    daily_counts: dict[str, int] = defaultdict(int)
    for log in logs:
        created_at = log.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at >= since:
            daily_counts[created_at.date().isoformat()] += 1

    questions_over_time = [
        QuestionsOverTimePoint(date=d, count=c) for d, c in sorted(daily_counts.items())
    ]

    return OverviewResponse(
        total_questions_asked=len(logs),
        total_documents=total_documents,
        total_quizzes_taken=len(quiz_attempts),
        avg_quiz_score=avg_quiz_score,
        most_active_document=most_active_document,
        questions_over_time=questions_over_time,
    )


@router.get("/knowledge-gaps", response_model=list[KnowledgeGapTheme])
def get_knowledge_gaps(
    workspace_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if workspace_id:
        _verify_workspace_access(db, workspace_id, current_user.id)

    query = db.query(QueryLog).filter(QueryLog.user_id == current_user.id, QueryLog.was_answered.is_(False))
    if workspace_id:
        query = query.filter(QueryLog.workspace_id == workspace_id)
    logs = query.order_by(QueryLog.created_at.desc()).limit(200).all()

    if not logs:
        return []

    questions = [log.question for log in logs]

    themes = cluster_unanswered_questions(questions)
    if themes:
        return [KnowledgeGapTheme(**t) for t in themes]

    # Fallback: group by exact normalized text frequency (no LLM available/failed).
    normalized_counts = Counter(q.strip().lower() for q in questions)
    seen: set[str] = set()
    grouped: list[KnowledgeGapTheme] = []
    for q in questions:
        key = q.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        grouped.append(KnowledgeGapTheme(theme=q, count=normalized_counts[key], example_questions=[q]))
    grouped.sort(key=lambda g: g.count, reverse=True)
    return grouped[:10]


@router.get("/document-performance", response_model=list[DocumentPerformanceItem])
def get_document_performance(
    workspace_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if workspace_id:
        _verify_workspace_access(db, workspace_id, current_user.id)
        doc_ids = _workspace_document_ids(db, workspace_id)
        documents = (
            db.query(Document).filter(Document.id.in_([uuid.UUID(d) for d in doc_ids])).all() if doc_ids else []
        )
    else:
        documents = db.query(Document).filter(Document.user_id == current_user.id).all()

    log_query = db.query(QueryLog).filter(QueryLog.user_id == current_user.id)
    if workspace_id:
        log_query = log_query.filter(QueryLog.workspace_id == workspace_id)
    logs = log_query.all()

    referenced: Counter = Counter()
    not_found: Counter = Counter()
    for log in logs:
        for doc_id in log.document_ids or []:
            if log.was_answered:
                referenced[doc_id] += 1
            else:
                not_found[doc_id] += 1

    quizzes = db.query(Quiz).filter(Quiz.user_id == current_user.id).all()
    quiz_scores_by_doc: dict[str, list[float]] = defaultdict(list)
    for quiz in quizzes:
        attempts = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).all()
        if not attempts:
            continue
        avg = sum(a.score for a in attempts) / len(attempts)
        for doc_id in quiz.document_ids:
            quiz_scores_by_doc[doc_id].append(avg)

    items = []
    for doc in documents:
        doc_id_str = str(doc.id)
        scores = quiz_scores_by_doc.get(doc_id_str, [])
        items.append(
            DocumentPerformanceItem(
                document_id=doc.id,
                filename=doc.filename,
                times_referenced=referenced.get(doc_id_str, 0),
                times_not_found=not_found.get(doc_id_str, 0),
                quiz_avg_score=round(sum(scores) / len(scores), 1) if scores else None,
            )
        )
    items.sort(key=lambda i: i.times_referenced, reverse=True)
    return items


@router.get("/quiz-insights", response_model=QuizInsightsResponse)
def get_quiz_insights(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    quizzes = db.query(Quiz).filter(Quiz.user_id == current_user.id).all()

    results: list[QuizInsightQuestion] = []
    for quiz in quizzes:
        attempts = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).all()
        if not attempts:
            continue

        question_by_id = {q["id"]: q for q in quiz.questions}
        wrong_counts: Counter = Counter()
        attempt_counts: Counter = Counter()

        for attempt in attempts:
            for q_id, question in question_by_id.items():
                submitted = attempt.answers.get(q_id)
                if submitted is None:
                    continue
                attempt_counts[q_id] += 1
                if not _grade_answer(question, submitted):
                    wrong_counts[q_id] += 1

        for q_id, question in question_by_id.items():
            attempted = attempt_counts.get(q_id, 0)
            wrong = wrong_counts.get(q_id, 0)
            if attempted == 0 or wrong == 0:
                continue
            results.append(
                QuizInsightQuestion(
                    quiz_id=quiz.id,
                    quiz_title=quiz.title,
                    question_id=q_id,
                    question=question["question"],
                    times_wrong=wrong,
                    times_attempted=attempted,
                    wrong_rate=round(100 * wrong / attempted, 1),
                )
            )

    results.sort(key=lambda r: r.wrong_rate, reverse=True)
    return QuizInsightsResponse(questions=results[:20])
