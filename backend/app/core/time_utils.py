from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_expired(expires_at: datetime) -> bool:
    """Compare against now(UTC), tolerating naive datetimes some DB backends (e.g. SQLite) return."""
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < utcnow()
