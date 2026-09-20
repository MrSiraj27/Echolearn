import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.admin.config_service import is_feature_enabled
from app.core.database import SessionLocal, get_db
from app.core.security import get_current_user
from app.core.usage import check_and_record_usage
from app.models import (
    Document,
    DocumentStatus,
    PastPaper,
    PastPaperAnalysisStatus,
    PracticePaper,
    PracticePaperAttempt,
    PracticePaperStatus,
    User,
)
from app.practice.constants import DISCLAIMER
from app.practice.grading import grade_paper
from app.practice.pdf_export import build_paper_pdf
from app.practice.schemas import (
    AttemptResultResponse,
    GeneratePracticePaperRequest,
    GeneratePracticePaperResponse,
    PracticePaperDetail,
    PracticePaperListItem,
    PracticePaperStatusResponse,
    PreviewPatternRequest,
    PreviewPatternResponse,
    SelfGradeRequest,
    SubmitPracticePaperRequest,
)
from app.rag.practice_paper_generator import (
    PaperGenerationError,
    estimate_time_minutes,
    generate_practice_paper,
    resolve_pattern,
)

router = APIRouter(prefix="/practice-papers", tags=["practice-papers"])
logger = logging.getLogger(__name__)

MAX_SOURCE_DOCUMENTS = 20
MAX_TOPICS = 10
MAX_CONCURRENT_GENERATIONS = 2
# A "generating" row older than this is assumed dead (e.g. the server restarted while the
# background task was running) and is reported as failed instead of spinning forever.
STALE_GENERATION_MINUTES = 20


# ---- helpers ----


def _clean_topics(topics: list[str] | None) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for t in topics or []:
        t = re.sub(r"\s+", " ", str(t)).strip()[:80]
        if len(t) < 2 or t.lower() in seen:
            continue
        seen.add(t.lower())
        cleaned.append(t)
    return cleaned[:MAX_TOPICS]


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _get_owned_paper(db: Session, paper_id: uuid.UUID, user_id: uuid.UUID) -> PracticePaper:
    paper = db.query(PracticePaper).filter(PracticePaper.id == paper_id, PracticePaper.user_id == user_id).first()
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Practice paper not found.")
    if paper.status == PracticePaperStatus.generating and _as_utc(paper.created_at) < datetime.now(
        timezone.utc
    ) - timedelta(minutes=STALE_GENERATION_MINUTES):
        paper.status = PracticePaperStatus.failed
        paper.error_message = "Generation took too long and was stopped. Please try generating the paper again."
        db.commit()
    return paper


def _require_ready(paper: PracticePaper) -> dict:
    if paper.status == PracticePaperStatus.generating:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This paper is still being generated.")
    if paper.status != PracticePaperStatus.ready or not paper.generated_content:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This paper couldn't be generated, so it isn't available."
        )
    return paper.generated_content


def _validate_source_documents(db: Session, user: User, document_ids: list[uuid.UUID]) -> None:
    unique_ids = set(document_ids)
    if not unique_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one document.")
    if len(unique_ids) > MAX_SOURCE_DOCUMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Select at most {MAX_SOURCE_DOCUMENTS} documents."
        )
    documents = db.query(Document).filter(Document.id.in_(unique_ids), Document.user_id == user.id).all()
    if len(documents) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more documents not found.")
    if any(d.status not in (DocumentStatus.embedded, DocumentStatus.ready) for d in documents):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="One or more documents are still processing. Try again shortly."
        )
    past_paper_docs = (
        db.query(PastPaper).filter(PastPaper.user_id == user.id, PastPaper.document_id.in_(unique_ids)).count()
    )
    if past_paper_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Past papers are used only to learn the paper's structure - choose your study material as the source.",
        )


def _validate_past_papers(db: Session, user: User, ids: list[uuid.UUID] | None) -> None:
    if not ids:
        return
    unique_ids = set(ids)
    rows = db.query(PastPaper).filter(PastPaper.id.in_(unique_ids), PastPaper.user_id == user.id).all()
    if len(rows) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more past papers not found.")
    if any(r.analysis_status in (PastPaperAnalysisStatus.pending, PastPaperAnalysisStatus.analyzing) for r in rows):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A past paper is still being analysed. Wait for it to finish."
        )


def _resolve(db: Session, user: User, past_ids, override) -> dict:
    try:
        return resolve_pattern(db, user.id, past_ids, override.model_dump() if override else None)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "That structure isn't valid. Use 1-8 sections, each with a supported question type, 1-40 questions "
                "and a mark value above 0 (at most 80 questions in total)."
            ),
        ) from exc


def _public_sections(content: dict) -> list[dict]:
    """The in-app paper view: questions WITHOUT answers, evidence quotes or grounding
    internals (answers are revealed by the attempt/submit flow or the Answer Key PDF)."""
    sections = []
    for section in content["sections"]:
        sections.append(
            {
                "name": section["name"],
                "question_type": section["question_type"],
                "count": section["count"],
                "marks_each": section["marks_each"],
                "instructions": section.get("instructions", ""),
                "questions": [
                    {
                        "id": q["id"],
                        "question_type": q["question_type"],
                        "question_text": q["question_text"],
                        "options": q.get("options") or [],
                        "marks": q["marks"],
                        "topic": q.get("topic") or None,
                        "topic_reason": q.get("topic_reason"),
                        "source_reference": q.get("source_reference"),
                        "source_references": q.get("source_references") or [],
                    }
                    for q in section["questions"]
                ],
            }
        )
    return sections


def _safe_filename(title: str) -> str:
    return re.sub(r"[^\w\-]+", "_", title).strip("_")[:60] or "practice_paper"


# ---- generation task ----


def run_generation_task(paper_id: uuid.UUID) -> None:
    db: Session = SessionLocal()
    try:
        paper = db.query(PracticePaper).filter(PracticePaper.id == paper_id).first()
        if not paper:
            return
        try:
            content = generate_practice_paper(
                user_id=paper.user_id,
                document_ids=[uuid.UUID(d) for d in paper.document_ids],
                pattern_config=paper.pattern_config,
                title=paper.title,
                important_topics=paper.important_topics or [],
                recurring_topics=paper.pattern_config.get("recurring_topics_mentioned", []),
                time_allowed_minutes=paper.time_allowed_minutes,
            )
            db.expire_all()
            paper = db.query(PracticePaper).filter(PracticePaper.id == paper_id).first()
            if not paper:
                return
            paper.generated_content = content
            paper.time_allowed_minutes = content["time_allowed_minutes"]
            paper.status = PracticePaperStatus.ready
            paper.error_message = None
        except PaperGenerationError as exc:
            db.rollback()
            paper = db.query(PracticePaper).filter(PracticePaper.id == paper_id).first()
            if not paper:
                return
            paper.status = PracticePaperStatus.failed
            paper.error_message = str(exc)
        except Exception:
            logger.exception("Practice paper generation crashed for %s", paper_id)
            db.rollback()
            paper = db.query(PracticePaper).filter(PracticePaper.id == paper_id).first()
            if not paper:
                return
            paper.status = PracticePaperStatus.failed
            paper.error_message = "Something went wrong while generating this paper. Please try again."
        db.commit()
    finally:
        db.close()


# ---- routes ----


@router.post("/preview-pattern", response_model=PreviewPatternResponse)
def preview_pattern(
    payload: PreviewPatternRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Resolves the paper structure WITHOUT generating anything (Step 4 of the flow)."""
    _validate_past_papers(db, current_user, payload.based_on_past_paper_ids)
    resolved = _resolve(db, current_user, payload.based_on_past_paper_ids, payload.custom_pattern_override)
    return PreviewPatternResponse(
        pattern_config=resolved["config"],
        pattern_source=resolved["source"],
        pattern_note=resolved["note"],
        estimated_time_minutes=estimate_time_minutes(resolved["config"]),
        recurring_topics=resolved["recurring_topics"],
        past_paper_summary=resolved["past_paper_summary"],
        section_confidence=resolved.get("section_confidence"),
    )


@router.post("/generate", response_model=GeneratePracticePaperResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_paper(
    payload: GeneratePracticePaperRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not is_feature_enabled("quiz_generation_enabled"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Practice paper generation is temporarily unavailable."
        )
    if payload.time_allowed_minutes is not None and not (5 <= payload.time_allowed_minutes <= 600):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Time allowed must be between 5 and 600 minutes."
        )

    _validate_source_documents(db, current_user, payload.document_ids)
    _validate_past_papers(db, current_user, payload.based_on_past_paper_ids)
    resolved = _resolve(db, current_user, payload.based_on_past_paper_ids, payload.custom_pattern_override)

    in_flight = (
        db.query(PracticePaper)
        .filter(
            PracticePaper.user_id == current_user.id,
            PracticePaper.status == PracticePaperStatus.generating,
            PracticePaper.created_at >= datetime.now(timezone.utc) - timedelta(minutes=STALE_GENERATION_MINUTES),
        )
        .count()
    )
    if in_flight >= MAX_CONCURRENT_GENERATIONS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You already have papers being generated. Wait for them to finish first.",
        )

    # Generating a paper is heavier than a quiz but shares the quiz-generation quota so no
    # new plan/limit schema is needed.
    check_and_record_usage(db, current_user, "quiz_generation")

    config = dict(resolved["config"])
    config["recurring_topics_mentioned"] = resolved["recurring_topics"]

    paper = PracticePaper(
        user_id=current_user.id,
        title=payload.title,
        document_ids=[str(d) for d in dict.fromkeys(payload.document_ids)],
        based_on_past_paper_ids=[str(p) for p in payload.based_on_past_paper_ids] if payload.based_on_past_paper_ids else None,
        important_topics=_clean_topics(payload.important_topics) or None,
        pattern_config=config,
        pattern_source=resolved["source"],
        pattern_note=resolved["note"],
        time_allowed_minutes=payload.time_allowed_minutes,
        status=PracticePaperStatus.generating,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    background_tasks.add_task(run_generation_task, paper.id)
    return GeneratePracticePaperResponse(id=paper.id, status=paper.status.value)


def _list_item(paper: PracticePaper) -> PracticePaperListItem:
    config = paper.pattern_config or {}
    return PracticePaperListItem(
        id=paper.id,
        title=paper.title,
        status=paper.status.value,
        pattern_source=paper.pattern_source,
        pattern_note=paper.pattern_note,
        total_marks=config.get("total_marks"),
        total_questions=config.get("total_questions"),
        time_allowed_minutes=paper.time_allowed_minutes,
        error_message=paper.error_message,
        created_at=paper.created_at,
    )


@router.get("/", response_model=list[PracticePaperListItem])
def list_papers(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    papers = (
        db.query(PracticePaper)
        .filter(PracticePaper.user_id == current_user.id)
        .order_by(PracticePaper.created_at.desc())
        .all()
    )
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_GENERATION_MINUTES)
    changed = False
    for paper in papers:
        if paper.status == PracticePaperStatus.generating and _as_utc(paper.created_at) < cutoff:
            paper.status = PracticePaperStatus.failed
            paper.error_message = "Generation took too long and was stopped. Please try generating the paper again."
            changed = True
    if changed:
        db.commit()
    return [_list_item(p) for p in papers]


@router.get("/{paper_id}/status", response_model=PracticePaperStatusResponse)
def get_paper_status(paper_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = _get_owned_paper(db, paper_id, current_user.id)
    return PracticePaperStatusResponse(id=paper.id, status=paper.status.value, error_message=paper.error_message)


@router.get("/{paper_id}", response_model=PracticePaperDetail)
def get_paper(paper_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = _get_owned_paper(db, paper_id, current_user.id)
    content = _require_ready(paper)
    return PracticePaperDetail(
        id=paper.id,
        title=paper.title,
        status=paper.status.value,
        disclaimer=DISCLAIMER,
        pattern_source=paper.pattern_source,
        pattern_note=paper.pattern_note,
        pattern_config=paper.pattern_config,
        time_allowed_minutes=paper.time_allowed_minutes,
        time_estimated=bool(content.get("time_estimated")),
        total_marks=content.get("total_marks"),
        total_questions=content.get("total_questions"),
        important_topics=paper.important_topics,
        topic_coverage=content.get("topic_coverage", []),
        sections=_public_sections(content),
        created_at=paper.created_at,
    )


@router.get("/{paper_id}/export")
def export_paper(
    paper_id: uuid.UUID,
    format: str = Query("pdf"),
    variant: str = Query("question"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if format != "pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="format must be 'pdf'.")
    if variant not in ("question", "answer_key"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="variant must be 'question' or 'answer_key'.")

    paper = _get_owned_paper(db, paper_id, current_user.id)
    content = _require_ready(paper)
    pdf_bytes = build_paper_pdf(paper.title, content, variant)
    suffix = "answer_key" if variant == "answer_key" else "question_paper"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(paper.title)}_{suffix}.pdf"'},
    )


def _attempt_response(attempt: PracticePaperAttempt) -> AttemptResultResponse:
    r = attempt.results
    return AttemptResultResponse(
        attempt_id=attempt.id,
        marks_obtained=r["marks_obtained"],
        total_marks=r["total_marks"],
        score_percent=r["score_percent"],
        pending_self_grade_count=r["pending_self_grade_count"],
        results=r["results"],
    )


@router.post("/{paper_id}/submit", response_model=AttemptResultResponse)
def submit_paper(
    paper_id: uuid.UUID,
    payload: SubmitPracticePaperRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    paper = _get_owned_paper(db, paper_id, current_user.id)
    content = _require_ready(paper)

    graded = grade_paper(content, payload.answers, payload.self_marks)
    attempt = PracticePaperAttempt(
        paper_id=paper.id,
        user_id=current_user.id,
        answers=payload.answers,
        results={**graded, "self_marks": payload.self_marks or {}},
        score=graded["score_percent"],
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return _attempt_response(attempt)


@router.post("/{paper_id}/attempts/{attempt_id}/self-grade", response_model=AttemptResultResponse)
def self_grade_attempt(
    paper_id: uuid.UUID,
    attempt_id: uuid.UUID,
    payload: SelfGradeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Second step for subjective questions: the student sends back the marks THEY awarded
    themselves after comparing with the model answer (clamped to each question's marks)."""
    paper = _get_owned_paper(db, paper_id, current_user.id)
    content = _require_ready(paper)
    attempt = (
        db.query(PracticePaperAttempt)
        .filter(
            PracticePaperAttempt.id == attempt_id,
            PracticePaperAttempt.paper_id == paper.id,
            PracticePaperAttempt.user_id == current_user.id,
        )
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    merged_marks = {**(attempt.results.get("self_marks") or {}), **payload.self_marks}
    graded = grade_paper(content, attempt.answers, merged_marks)
    attempt.results = {**graded, "self_marks": merged_marks}
    attempt.score = graded["score_percent"]
    db.commit()
    db.refresh(attempt)
    return _attempt_response(attempt)


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paper(paper_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = _get_owned_paper(db, paper_id, current_user.id)
    db.delete(paper)
    db.commit()
