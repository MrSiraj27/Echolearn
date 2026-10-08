import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.chats.schemas import ExplainMessageRequest, ExplainMessageResponse
from app.chats.translation_service import explain_with_cache
from app.core.database import get_db
from app.core.languages import EXPLAIN_TARGETS
from app.core.security import block_if_impersonating, get_current_user
from app.models import Chat, Message, MessageRole, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("/{chat_id}/messages/{message_id}/explain", response_model=ExplainMessageResponse)
async def explain_message_in_language(
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: ExplainMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    """Explain one assistant answer in Urdu or Roman Urdu. Cached per (message, language,
    mode); only a NEW generation uses quota."""
    if payload.language not in EXPLAIN_TARGETS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose Urdu or Roman Urdu.")

    # The chat must belong to the caller, and the message to that chat.
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found.")
    message = db.query(Message).filter(Message.id == message_id, Message.chat_id == chat.id).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    if message.role != MessageRole.assistant or message.content_type != "text":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only text answers can be explained.")

    try:
        # The LLM calls are blocking, so keep them off the event loop.
        translation, cached = await run_in_threadpool(
            explain_with_cache, db, current_user, message, payload.language, payload.mode
        )
    except HTTPException:
        raise  # quota (429) keeps its own message and reset time
    except Exception:
        logger.exception("Language explanation failed for message %s", message_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't generate the explanation right now. Please try again.",
        )

    return ExplainMessageResponse(
        text=translation.text,
        language=payload.language,
        mode=payload.mode,
        fidelity_warning=translation.fidelity_warning,
        cached=cached,
    )
