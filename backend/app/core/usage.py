from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.admin.audit import log_admin_action
from app.admin.config_service import get_config_value
from app.core.limits import get_effective_limits
from app.models import RateLimitViolation, UsageEvent, User

# Maps each usage event type to the effective-limits key that caps it, and the size of
# its rolling window. "message" uses a configurable window (message_window_hours);
# everything else has a fixed window baked into the plan schema.
_EVENT_CONFIG: dict[str, dict] = {
    "message": {"limit_key": "messages_per_window", "window_hours_key": "message_window_hours", "label": "message"},
    "quiz_generation": {"limit_key": "quiz_generations_per_month", "window_days": 30, "label": "quiz generation"},
    "tts_use": {"limit_key": "tts_uses_per_day", "window_days": 1, "label": "text-to-speech"},
    "diagram_infographic": {
        "limit_key": "diagrams_infographics_per_month",
        "window_days": 30,
        "label": "diagram/infographic generation",
    },
}


def _window_for(event_type: str, limits: dict) -> timedelta:
    config = _EVENT_CONFIG[event_type]
    if "window_hours_key" in config:
        return timedelta(hours=limits.get(config["window_hours_key"]) or 5)
    return timedelta(days=config["window_days"])


def _human_remaining(delta_seconds: float) -> str:
    seconds = max(0, delta_seconds)
    total_minutes = int(seconds // 60) + (1 if seconds % 60 else 0)
    if total_minutes < 60:
        return f"{total_minutes} minute{'s' if total_minutes != 1 else ''}"
    hours, minutes = divmod(total_minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h" if hours else f"{days}d"


def _maybe_auto_block(db: Session, user: User) -> None:
    """Called right after logging a rate-limit violation. If this user has racked up
    more violations than the configured threshold within the configured window,
    block them automatically."""
    abuse_config = get_config_value("abuse_detection")
    if not abuse_config.get("auto_block_enabled", True):
        return
    if user.is_blocked:
        return

    threshold = abuse_config.get("auto_block_rate_limit_violations_threshold", 10)
    window_minutes = abuse_config.get("auto_block_violation_window_minutes", 60)
    window_start = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

    violation_count = (
        db.query(RateLimitViolation)
        .filter(RateLimitViolation.user_id == user.id, RateLimitViolation.created_at >= window_start)
        .count()
    )
    if violation_count <= threshold:
        return

    now = datetime.now(timezone.utc)
    user.is_blocked = True
    user.blocked_reason = "Auto-blocked: excessive rate limit violations"
    user.blocked_by = None
    user.blocked_at = now
    log_admin_action(
        db,
        admin_user_id=None,
        action="user.auto_block",
        target_id=str(user.id),
        details={"violation_count": violation_count, "window_minutes": window_minutes},
    )


def check_and_record_usage(db: Session, user: User, event_type: str) -> None:
    """Enforce the rolling-window quota for `event_type` and, if allowed, record this
    usage event. Raises HTTPException(429) if the user is over their limit — the detail
    message tells them when they'll be able to try again, computed from the oldest
    in-window event."""
    if event_type not in _EVENT_CONFIG:
        raise ValueError(f"Unknown usage event_type: {event_type}")

    config = _EVENT_CONFIG[event_type]
    limits = get_effective_limits(user)
    limit = limits.get(config["limit_key"])

    if limit is not None:
        window = _window_for(event_type, limits)
        window_start = datetime.now(timezone.utc) - window

        events_in_window = (
            db.query(UsageEvent)
            .filter(
                UsageEvent.user_id == user.id,
                UsageEvent.event_type == event_type,
                UsageEvent.created_at >= window_start,
            )
            .order_by(UsageEvent.created_at.asc())
            .all()
        )

        if len(events_in_window) >= limit:
            db.add(RateLimitViolation(user_id=user.id, event_type=event_type))
            _maybe_auto_block(db, user)
            db.commit()

            oldest = events_in_window[0]
            oldest_created = oldest.created_at if oldest.created_at.tzinfo else oldest.created_at.replace(
                tzinfo=timezone.utc
            )
            reset_at = oldest_created + window
            remaining_seconds = (reset_at - datetime.now(timezone.utc)).total_seconds()

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"You've reached your {config['label']} limit. You can send another "
                    f"{config['label']} in {_human_remaining(remaining_seconds)}."
                ),
            )

    db.add(UsageEvent(user_id=user.id, event_type=event_type))
    db.commit()


ROLLING_QUOTA_LABELS = {
    "message": "Messages",
    "quiz_generation": "Quiz generations",
    "tts_use": "Text-to-speech uses",
    "diagram_infographic": "Diagrams & infographics",
}


def rolling_quota_usage(db: Session, user: User) -> list[dict]:
    """Current usage vs. effective limit for every rolling-window quota type (messages,
    quiz generations, TTS uses, diagrams/infographics) — shared by the admin per-user
    limits view and the user-facing GET /users/me/usage endpoint."""
    limits = get_effective_limits(user)
    now = datetime.now(timezone.utc)
    results = []

    for event_type, config in _EVENT_CONFIG.items():
        limit = limits.get(config["limit_key"])
        window = _window_for(event_type, limits)
        window_start = now - window

        events = (
            db.query(UsageEvent)
            .filter(
                UsageEvent.user_id == user.id,
                UsageEvent.event_type == event_type,
                UsageEvent.created_at >= window_start,
            )
            .order_by(UsageEvent.created_at.asc())
            .all()
        )

        resets_in_seconds = None
        resets_in_human = None
        if events:
            oldest_created = events[0].created_at if events[0].created_at.tzinfo else events[0].created_at.replace(
                tzinfo=timezone.utc
            )
            reset_at = oldest_created + window
            resets_in_seconds = max(0, int((reset_at - now).total_seconds()))
            resets_in_human = _human_remaining(resets_in_seconds)

        results.append(
            {
                "key": config["limit_key"],
                "label": ROLLING_QUOTA_LABELS[event_type],
                "limit": limit,
                "current_usage": len(events),
                "resets_in_seconds": resets_in_seconds,
                "resets_in_human": resets_in_human,
            }
        )

    return results
