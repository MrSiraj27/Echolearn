import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Document, ReviewCard, ReviewCardState, User
from app.study.card_service import create_review_cards
from app.study.schemas import (
    ManualReviewCardCreate,
    ReviewCardPublic,
    ReviewCardWithState,
    ReviewSettingsResponse,
    ReviewSettingsUpdate,
    ReviewStatsResponse,
    SubmitReviewRequest,
    SubmitReviewResponse,
    TodayReviewResponse,
)
from app.study.spaced_repetition import (
    compute_streak_days,
    effective_daily_cap,
    update_card_after_review,
)

review_router = APIRouter(prefix="/review", tags=["review"])
review_cards_router = APIRouter(prefix="/review-cards", tags=["review"])

# "Mastered" / "struggling" thresholds (Prompt 30, GET /review/stats). Chosen so they
# track the SM-2 state directly rather than needing separate bookkeeping:
#   - mastered: repetitions >= 5 (reviewed successfully five times in a row) AND
#     ease_factor >= 2.5 (at/above the starting ease — never had to be slowed down) —
#     i.e. a card that's been consistently easy for a while.
#   - struggling: ease_factor has dropped meaningfully below the 2.5 starting point
#     (repeated low-quality grades), OR the card has been forgotten at least once after
#     being seen (repetitions reset to 0 but it HAS been reviewed before) — either
#     signal means this card needs more attention.
MASTERED_MIN_REPETITIONS = 5
MASTERED_MIN_EASE_FACTOR = 2.5
STRUGGLING_MAX_EASE_FACTOR = 2.0


@review_cards_router.post("/", response_model=ReviewCardPublic, status_code=status.HTTP_201_CREATED)
def create_manual_review_card(
    payload: ManualReviewCardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """A user saving any AI chat answer (or anything else) as a flashcard."""
    document = (
        db.query(Document).filter(Document.id == payload.document_id, Document.user_id == current_user.id).first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    created = create_review_cards(
        db,
        user_id=current_user.id,
        document_id=payload.document_id,
        items=[
            {
                "question": payload.question,
                "answer": payload.answer,
                "question_type": payload.question_type,
                "options": payload.options,
            }
        ],
    )
    if not created:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A near-identical flashcard already exists.",
        )
    return created[0]


@review_router.get("/today", response_model=TodayReviewResponse)
def get_today_review(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cap = effective_daily_cap(current_user)
    today = date.today()

    due_query = (
        db.query(ReviewCardState, ReviewCard)
        .join(ReviewCard, ReviewCard.id == ReviewCardState.review_card_id)
        .filter(ReviewCardState.user_id == current_user.id, ReviewCardState.next_review_date <= today)
    )

    total_due = due_query.count()

    # Most-overdue-first (oldest next_review_date first), then lowest ease factor
    # (the shakiest cards) first among equally-overdue cards.
    rows = due_query.order_by(ReviewCardState.next_review_date.asc(), ReviewCardState.ease_factor.asc()).limit(cap).all()

    cards = [
        ReviewCardWithState(
            id=card.id,
            document_id=card.document_id,
            question=card.question,
            answer=card.answer,
            question_type=card.question_type.value,
            options=card.options,
            source_chunk_id=card.source_chunk_id,
            ease_factor=state.ease_factor,
            interval_days=state.interval_days,
            repetitions=state.repetitions,
            next_review_date=state.next_review_date,
        )
        for state, card in rows
    ]

    return TodayReviewResponse(cards=cards, total_due=total_due, capped_at=cap)


def _get_owned_card_state(db: Session, card_id: uuid.UUID, user_id: uuid.UUID) -> ReviewCardState:
    state = (
        db.query(ReviewCardState)
        .filter(ReviewCardState.review_card_id == card_id, ReviewCardState.user_id == user_id)
        .first()
    )
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review card not found.")
    return state


@review_router.post("/{card_id}/submit", response_model=SubmitReviewResponse)
def submit_review(
    card_id: uuid.UUID,
    payload: SubmitReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    state = _get_owned_card_state(db, card_id, current_user.id)
    update_card_after_review(state, payload.quality)
    db.commit()
    db.refresh(state)
    return SubmitReviewResponse(next_review_date=state.next_review_date, interval_days=state.interval_days)


@review_router.get("/stats", response_model=ReviewStatsResponse)
def get_review_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    states = db.query(ReviewCardState).filter(ReviewCardState.user_id == current_user.id).all()

    total_cards = len(states)
    cards_mastered = sum(
        1 for s in states if s.repetitions >= MASTERED_MIN_REPETITIONS and s.ease_factor >= MASTERED_MIN_EASE_FACTOR
    )
    cards_struggling = sum(
        1
        for s in states
        if s.ease_factor < STRUGGLING_MAX_EASE_FACTOR or (s.repetitions == 0 and s.last_reviewed_at is not None)
    )

    review_dates = {s.last_reviewed_at.date() for s in states if s.last_reviewed_at is not None}
    streak = compute_streak_days(review_dates)

    return ReviewStatsResponse(
        current_streak_days=streak,
        total_cards=total_cards,
        cards_mastered=cards_mastered,
        cards_struggling=cards_struggling,
    )


@review_router.get("/settings", response_model=ReviewSettingsResponse)
def get_review_settings(current_user: User = Depends(get_current_user)):
    return ReviewSettingsResponse(daily_cap=effective_daily_cap(current_user))


@review_router.patch("/settings", response_model=ReviewSettingsResponse)
def update_review_settings(
    payload: ReviewSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.daily_review_cap = payload.daily_cap
    db.commit()
    return ReviewSettingsResponse(daily_cap=payload.daily_cap)


def has_pending_reviews(db: Session, user: User) -> bool:
    """True if cards are due today AND none have been reviewed yet today — used by
    GET /users/me/usage so the frontend can show a one-shot daily nudge rather than a
    persistent nag once the user has already started today's reviews."""
    today = date.today()
    due_exists = (
        db.query(ReviewCardState.id)
        .filter(ReviewCardState.user_id == user.id, ReviewCardState.next_review_date <= today)
        .first()
        is not None
    )
    if not due_exists:
        return False

    reviewed_today = (
        db.query(ReviewCardState.id)
        .filter(
            ReviewCardState.user_id == user.id,
            ReviewCardState.last_reviewed_at >= datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
        )
        .first()
        is not None
    )
    return not reviewed_today
