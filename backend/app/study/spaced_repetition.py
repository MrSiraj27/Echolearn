"""SM-2 spaced-repetition scheduling (Prompt 30) — the standard algorithm, implemented
exactly per its well-documented formulas rather than approximated. See
https://en.wikipedia.org/wiki/SuperMemo#Description_of_SM-2_algorithm for the reference
formulas this mirrors.
"""

from datetime import date, datetime, timedelta, timezone

from app.models import ReviewCardState

# Cards due today, capped at this many per session (frontend adjustable per-user via
# User.daily_review_cap — this is only the app-wide fallback/default).
DEFAULT_DAILY_CARD_CAP = 25
MIN_DAILY_CARD_CAP = 5
MAX_DAILY_CARD_CAP = 50

MIN_EASE_FACTOR = 1.3


def update_card_after_review(card_state: ReviewCardState, quality: int) -> ReviewCardState:
    """Mutates and returns `card_state` per the standard SM-2 update rule.

    quality: 0-5 standard SM-2 rating (frontend only ever sends 1/3/5 for
    Forgot/Hard/Easy, but the algorithm itself accepts the full 0-5 range).
    """
    if quality < 3:
        # Any "failing" grade resets progress entirely, regardless of prior streak —
        # SM-2 treats a forgotten card as needing to be relearned from scratch.
        card_state.repetitions = 0
        card_state.interval_days = 1
    else:
        if card_state.repetitions == 0:
            card_state.interval_days = 1
        elif card_state.repetitions == 1:
            card_state.interval_days = 6
        else:
            card_state.interval_days = round(card_state.interval_days * card_state.ease_factor)
        card_state.repetitions += 1

    # EF' = EF + (0.1 - (5-q)*(0.08 + (5-q)*0.02)), floored at 1.3 — the exact SM-2
    # formula. This still runs on a quality<3 answer: a hard fail also drops the ease
    # factor (the card gets scheduled more frequently going forward), it just doesn't
    # affect repetitions/interval the way a pass does.
    card_state.ease_factor = card_state.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    card_state.ease_factor = max(MIN_EASE_FACTOR, card_state.ease_factor)

    card_state.next_review_date = date.today() + timedelta(days=card_state.interval_days)
    card_state.last_reviewed_at = datetime.now(timezone.utc)

    return card_state


def effective_daily_cap(user) -> int:
    cap = getattr(user, "daily_review_cap", None)
    return cap if cap is not None else DEFAULT_DAILY_CARD_CAP


def compute_streak_days(review_dates: set[date]) -> int:
    """Consecutive days (including today if already reviewed, or ending yesterday if
    not yet reviewed today) with at least one card reviewed. `review_dates` is the set
    of distinct calendar dates on which this user has at least one
    ReviewCardState.last_reviewed_at.

    Deliberately NOT "today must be included" — a user who reviewed every day through
    yesterday and simply hasn't opened the app yet today still has an active streak;
    it only breaks once a full day passes with no review at all.
    """
    if not review_dates:
        return 0

    today = date.today()
    if today in review_dates:
        cursor = today
    elif (today - timedelta(days=1)) in review_dates:
        cursor = today - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in review_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
