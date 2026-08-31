import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, status

_DEFAULT_WINDOW_SECONDS = 15 * 60
_DEFAULT_MAX_ATTEMPTS = 5

_attempts: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def check_rate_limit(
    key: str, max_attempts: int = _DEFAULT_MAX_ATTEMPTS, window_seconds: int = _DEFAULT_WINDOW_SECONDS
) -> None:
    """Raise 429 if `key` has exceeded `max_attempts` within `window_seconds`.

    Different call sites use their own effective namespace by prefixing `key`
    (e.g. "login:email" vs "voice:user_id"), so one shared store works for all of them.
    """
    now = time.time()
    with _lock:
        recent = [t for t in _attempts[key] if now - t < window_seconds]
        if len(recent) >= max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please try again later.",
            )
        recent.append(now)
        _attempts[key] = recent


def snapshot_attempts() -> dict[str, list[float]]:
    """Read-only snapshot of the in-memory attempt store, for the admin abuse-signals
    view. This is a lightweight proxy for real rate-limit-violation logging — it reflects
    attempts recorded since the process last restarted, not a persistent history."""
    with _lock:
        return {k: list(v) for k, v in _attempts.items()}
