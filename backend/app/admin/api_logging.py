import logging
import time
import uuid
from contextlib import contextmanager

from app.core.database import SessionLocal
from app.models import APICallLog

logger = logging.getLogger(__name__)


@contextmanager
def log_api_call(provider: str, purpose: str, user_id: uuid.UUID | None = None):
    """Context manager that times a provider call and writes one APICallLog row —
    success or failure — using its own short-lived DB session so call sites don't need
    to thread a request-scoped session through. Wrap any single provider call site:

        with log_api_call("groq", "chat_answer"):
            ...call the provider...
    """
    start = time.monotonic()
    error_message: str | None = None
    success = True
    try:
        yield
    except Exception as exc:
        success = False
        error_message = str(exc)[:2000]
        raise
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        db = SessionLocal()
        try:
            db.add(
                APICallLog(
                    provider=provider,
                    user_id=user_id,
                    endpoint_or_purpose=purpose,
                    duration_ms=duration_ms,
                    success=success,
                    error_message=error_message,
                )
            )
            db.commit()
        except Exception:
            logger.warning("Failed to write APICallLog row", exc_info=True)
        finally:
            db.close()
