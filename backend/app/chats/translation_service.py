"""Cache + quota wrapper around the language explainer, shared by the explain route and
the auto-explain step of the chat stream so both behave identically."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.languages import ExplainMode, Language
from app.core.usage import enforce_quota, record_usage
from app.models import Message, MessageTranslation, User
from app.rag.language_explainer import explain_message

USAGE_EVENT = "language_explain"


def get_cached_translation(
    db: Session, message_id: uuid.UUID, language: Language, mode: ExplainMode
) -> MessageTranslation | None:
    return (
        db.query(MessageTranslation)
        .filter(
            MessageTranslation.message_id == message_id,
            MessageTranslation.language == language.value,
            MessageTranslation.mode == mode.value,
        )
        .first()
    )


def explain_with_cache(
    db: Session, user: User, message: Message, language: Language, mode: ExplainMode
) -> tuple[MessageTranslation, bool]:
    """Return (translation, was_cached).

    A cache hit costs nothing. Otherwise the quota is checked BEFORE generating
    (HTTPException 429 if exhausted) but only charged AFTER the result is stored, so a
    failed generation never uses up the user's allowance."""
    cached = get_cached_translation(db, message.id, language, mode)
    if cached:
        return cached, True

    enforce_quota(db, user, USAGE_EVENT)

    result = explain_message(message, language, mode, user_id=user.id)

    row = MessageTranslation(
        message_id=message.id,
        language=language.value,
        mode=mode.value,
        text=result.text,
        fidelity_warning=result.fidelity_warning,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request for the same message/language/mode stored it first.
        db.rollback()
        existing = get_cached_translation(db, message.id, language, mode)
        if existing:
            return existing, True
        raise

    record_usage(db, user.id, USAGE_EVENT)
    return row, False
