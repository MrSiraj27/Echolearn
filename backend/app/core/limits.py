"""Effective quota resolution — every quota check anywhere in the app must go through
`get_effective_limits()` rather than reading `user.plan.limits` directly, so a per-user
override in `custom_limits` is never accidentally bypassed."""

from app.models import User

LIMITS_SCHEMA_DEFAULTS: dict = {
    "max_documents": None,
    "max_file_size_mb": None,
    "max_audio_video_minutes": None,
    "messages_per_window": None,
    "message_window_hours": 5,
    "max_workspaces": None,
    "quiz_generations_per_month": None,
    "tts_uses_per_day": None,
    "diagrams_infographics_per_month": None,
    "max_storage_mb": None,
    "priority_processing": False,
}


def get_effective_limits(user: User) -> dict:
    """Merge the user's plan limits with their custom_limits override, key by key —
    any key present in custom_limits (even if null, meaning "explicitly unlimited")
    wins over the plan's value for that key."""
    limits = dict(LIMITS_SCHEMA_DEFAULTS)

    plan = getattr(user, "plan", None)
    if plan and plan.limits:
        limits.update(plan.limits)

    if user.custom_limits:
        for key, value in user.custom_limits.items():
            limits[key] = value

    return limits
