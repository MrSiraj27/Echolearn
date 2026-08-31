import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.admin.config_service import is_feature_enabled
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.usage import check_and_record_usage
from app.models import Document, Quiz, QuizAttempt, User
from app.quizzes.schemas import (
    GenerateQuizRequest,
    QuestionResult,
    QuizListItem,
    QuizQuestionPublic,
    QuizResponse,
    SubmitQuizRequest,
    SubmitQuizResponse,
)
from app.rag.quiz_generator import generate_quiz

router = APIRouter(prefix="/quizzes", tags=["quizzes"])

VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_QUESTION_TYPES = {"multiple_choice", "short_answer", "mixed"}


def _derive_quiz_title(filenames: list[str]) -> str:
    if not filenames:
        return "Quiz"
    if len(filenames) == 1:
        stem = filenames[0].rsplit(".", 1)[0]
        return f"Quiz: {stem}"
    return f"Quiz: {filenames[0].rsplit('.', 1)[0]} + {len(filenames) - 1} more"


def _to_public_questions(questions: list[dict]) -> list[QuizQuestionPublic]:
    return [
        QuizQuestionPublic(id=q["id"], question=q["question"], type=q["type"], options=q.get("options", []))
        for q in questions
    ]


@router.post("/generate", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
def create_quiz(
    payload: GenerateQuizRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not is_feature_enabled("quiz_generation_enabled"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Quiz generation is temporarily unavailable.")
    if not payload.document_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one document.")
    if not (1 <= payload.num_questions <= 25):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="num_questions must be between 1 and 25.")
    if payload.difficulty not in VALID_DIFFICULTIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"difficulty must be one of {VALID_DIFFICULTIES}.")
    if payload.question_type not in VALID_QUESTION_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"question_type must be one of {VALID_QUESTION_TYPES}.")

    check_and_record_usage(db, current_user, "quiz_generation")

    documents = (
        db.query(Document)
        .filter(Document.id.in_(payload.document_ids), Document.user_id == current_user.id)
        .all()
    )
    if len(documents) != len(set(payload.document_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more documents not found.")

    questions = generate_quiz(
        document_ids=payload.document_ids,
        num_questions=payload.num_questions,
        difficulty=payload.difficulty,
        question_type=payload.question_type,
    )
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't generate a quiz from this document right now. Please try again.",
        )

    quiz = Quiz(
        user_id=current_user.id,
        document_ids=[str(d) for d in payload.document_ids],
        title=payload.title or _derive_quiz_title([d.filename for d in documents]),
        questions=questions,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    return QuizResponse(
        id=quiz.id,
        title=quiz.title,
        document_ids=[uuid.UUID(d) for d in quiz.document_ids],
        questions=_to_public_questions(quiz.questions),
        created_at=quiz.created_at,
    )


@router.get("/", response_model=list[QuizListItem])
def list_quizzes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    quizzes = db.query(Quiz).filter(Quiz.user_id == current_user.id).order_by(Quiz.created_at.desc()).all()

    items = []
    for quiz in quizzes:
        attempts = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).all()
        best_score = max((a.score for a in attempts), default=None)
        items.append(
            QuizListItem(
                id=quiz.id,
                title=quiz.title,
                question_count=len(quiz.questions),
                created_at=quiz.created_at,
                best_score=best_score,
                attempt_count=len(attempts),
            )
        )
    return items


def _get_owned_quiz(db: Session, quiz_id: uuid.UUID, user_id: uuid.UUID) -> Quiz:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.user_id == user_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    return quiz


@router.get("/{quiz_id}", response_model=QuizResponse)
def get_quiz(
    quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = _get_owned_quiz(db, quiz_id, current_user.id)
    return QuizResponse(
        id=quiz.id,
        title=quiz.title,
        document_ids=[uuid.UUID(d) for d in quiz.document_ids],
        questions=_to_public_questions(quiz.questions),
        created_at=quiz.created_at,
    )


def _grade_answer(question: dict, submitted: str | None) -> bool:
    if submitted is None:
        return False
    if question["type"] == "multiple_choice":
        return submitted.strip().lower() == question["correct_answer"].strip().lower()
    # Short answer: lenient case-insensitive substring/equality match rather than exact —
    # LLM-graded free text is out of scope here, so reward a reasonably close answer.
    submitted_norm = submitted.strip().lower()
    correct_norm = question["correct_answer"].strip().lower()
    return submitted_norm == correct_norm or (len(submitted_norm) > 3 and submitted_norm in correct_norm) or (
        len(correct_norm) > 3 and correct_norm in submitted_norm
    )


@router.post("/{quiz_id}/submit", response_model=SubmitQuizResponse)
def submit_quiz(
    quiz_id: uuid.UUID,
    payload: SubmitQuizRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = _get_owned_quiz(db, quiz_id, current_user.id)

    results = []
    correct_count = 0
    for question in quiz.questions:
        submitted = payload.answers.get(question["id"])
        is_correct = _grade_answer(question, submitted)
        if is_correct:
            correct_count += 1
        results.append(
            QuestionResult(
                id=question["id"],
                question=question["question"],
                type=question["type"],
                options=question.get("options", []),
                submitted_answer=submitted,
                correct_answer=question["correct_answer"],
                is_correct=is_correct,
                explanation=question.get("explanation", ""),
                source_page=question.get("source_page"),
                source_filename=question.get("source_filename"),
            )
        )

    total = len(quiz.questions)
    score = round(100 * correct_count / total, 1) if total else 0.0

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=current_user.id,
        answers=payload.answers,
        score=score,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return SubmitQuizResponse(
        attempt_id=attempt.id, score=score, total=total, correct_count=correct_count, results=results
    )
