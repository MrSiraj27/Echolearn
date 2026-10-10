import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.languages import Language
from app.core.limits import get_effective_limits
from app.core.security import block_if_impersonating, get_current_user
from app.core.usage import enforce_quota
from app.models import TutorConceptState, TutorSession, TutorTurn, User, Workspace, WorkspaceDocument
from app.practice.paper_routes import _validate_source_documents
from app.rag import language_explainer as lang
from app.rag import tutor_graph as tg
from app.tutor import service
from app.tutor.schemas import (
    CreateTutorSessionRequest,
    TutorActionResponse,
    TutorMessageRequest,
    TutorSessionListItem,
    TutorSessionResponse,
    TutorTurnResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tutor", tags=["tutor"])


def _get_owned(db: Session, session_id: uuid.UUID, user_id: uuid.UUID, lock: bool = False) -> TutorSession:
    query = db.query(TutorSession).filter(TutorSession.id == session_id, TutorSession.user_id == user_id)
    if lock:
        query = query.with_for_update()  # two quick taps must not apply the same turn twice
    session = query.first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor session not found.")
    return session


def _turn_response(turn: TutorTurn) -> TutorTurnResponse:
    return TutorTurnResponse.model_validate(turn, from_attributes=True)


def _session_response(db: Session, session: TutorSession) -> TutorSessionResponse:
    return TutorSessionResponse(**service.serialize_session(db, session))


# ---------------------------------------------------------------- create


@router.post("/sessions", response_model=TutorSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: CreateTutorSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    limits = get_effective_limits(current_user)
    language = payload.language or (
        current_user.preferred_language if current_user.preferred_language in ("ur", "roman_ur") else "en"
    )
    try:
        Language(language)
    except ValueError:
        language = "en"

    if payload.level not in (limits.get("tutor_levels_allowed") or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"The {payload.level.replace('_', '-')} level isn't available on your plan. Upgrade to use it.",
        )
    if language not in (limits.get("tutor_languages_allowed") or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tutoring in this language isn't available on your plan. Upgrade to use it.",
        )

    if payload.workspace_id:
        workspace = db.query(Workspace).filter(Workspace.id == payload.workspace_id, Workspace.user_id == current_user.id).first()
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
        document_ids = [
            r.document_id for r in db.query(WorkspaceDocument).filter(WorkspaceDocument.workspace_id == workspace.id).all()
        ]
    else:
        document_ids = list(dict.fromkeys(payload.document_ids))
    _validate_source_documents(db, current_user, document_ids)  # ownership + readiness for every id

    enforce_quota(db, current_user, "tutor_session")  # fail fast, before any model call

    cap = limits.get("tutor_max_turns_per_session")
    max_turns = min(tg.DEFAULT_MAX_TURNS, cap) if cap else tg.DEFAULT_MAX_TURNS

    try:
        session = service.create_session(
            db, current_user, payload.topic.strip(), document_ids, payload.workspace_id, payload.level, language, max_turns
        )
    except tg.TutorNotCovered as exc:
        # A polite refusal: nothing was created and no quota was used.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except tg.TutorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return _session_response(db, session)


# ---------------------------------------------------------------- read / delete


@router.get("/sessions", response_model=list[TutorSessionListItem])
def list_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = (
        db.query(TutorSession)
        .filter(TutorSession.user_id == current_user.id)
        .order_by(TutorSession.created_at.desc())
        .limit(100)
        .all()
    )
    out = []
    for s in sessions:
        mastered = db.query(TutorConceptState).filter(
            TutorConceptState.session_id == s.id, TutorConceptState.mastered.is_(True)
        ).count()
        out.append(TutorSessionListItem(
            id=s.id, title=s.title, topic=s.topic, level=s.level, status=s.status, turn_count=s.turn_count,
            mastered_count=mastered, total_concepts=len(service.concepts_of(s)), created_at=s.created_at,
        ))
    return out


@router.get("/sessions/{session_id}", response_model=TutorSessionResponse)
def get_session(session_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Full transcript + progress; this is also how a reloaded page resumes mid-session."""
    return _session_response(db, _get_owned(db, session_id, current_user.id))


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    session = _get_owned(db, session_id, current_user.id)
    db.query(TutorTurn).filter(TutorTurn.session_id == session.id).delete()
    db.query(TutorConceptState).filter(TutorConceptState.session_id == session.id).delete()
    db.delete(session)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- one turn (JSON actions)


def _run_simple_action(
    db: Session, user: User, session: TutorSession, action: str, content: str | None = None
) -> TutorActionResponse:
    ctx = service.prepare_turn(db, user, session, action, content)
    try:
        state = tg.get_tutor_graph().invoke(service.graph_input(ctx, defer_generation=False))
    except tg.TutorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except Exception:
        logger.exception("Tutor %s failed for session %s", action, session.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="The tutor couldn't respond just now. Please try again."
        )
    text, _replaced = service.finalize_text(ctx, state["decision"], state.get("response_text"))
    turn = service.commit_turn(db, ctx, state, text)
    return TutorActionResponse(turn=_turn_response(turn), session=_session_response(db, session))


@router.post("/sessions/{session_id}/hint", response_model=TutorActionResponse)
def request_hint(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    """The next rung of the hint ladder for the current question, without needing an answer."""
    return _run_simple_action(db, current_user, _get_owned(db, session_id, current_user.id, lock=True), "hint")


@router.post("/sessions/{session_id}/just-tell-me", response_model=TutorActionResponse)
def just_tell_me(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    """Always available: the full explanation now, then one short check question."""
    return _run_simple_action(db, current_user, _get_owned(db, session_id, current_user.id, lock=True), "just_tell_me")


@router.post("/sessions/{session_id}/skip", response_model=TutorActionResponse)
def skip_concept(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    """Skip the current concept (counts as not mastered)."""
    return _run_simple_action(db, current_user, _get_owned(db, session_id, current_user.id, lock=True), "skip")


@router.post("/sessions/{session_id}/end", response_model=TutorActionResponse)
def end_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    """Finish: summary, and flashcards for the concepts that need another look."""
    session = _get_owned(db, session_id, current_user.id, lock=True)
    if session.status == "abandoned":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This session was abandoned.")
    try:
        session = service.end_session(db, current_user, session)
    except Exception:
        logger.exception("Ending tutor session %s failed", session_id)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Couldn't finish the session just now. Please try again."
        )
    last = (
        db.query(TutorTurn).filter(TutorTurn.session_id == session.id).order_by(TutorTurn.created_at.desc()).first()
    )
    return TutorActionResponse(turn=_turn_response(last) if last else None, session=_session_response(db, session))


# ---------------------------------------------------------------- one turn (SSE)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/sessions/{session_id}/message")
async def send_message(
    session_id: uuid.UUID,
    payload: TutorMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    """Grade the student's answer and stream the tutor's reply. Ends with a `done` event:
    {verdict, hint_level, concept_index, total_concepts, mastered_count, ...}."""
    session = _get_owned(db, session_id, current_user.id, lock=True)
    # "Explain it simply" / "I don't know" is a request for help, not an answer to grade.
    action = "explain" if tg.is_explain_request(payload.content) else "answer"
    ctx = service.prepare_turn(db, current_user, session, action, payload.content)

    async def event_stream():
        try:
            # evaluate (model call 1) + decide; the reply itself is generated below, streamed
            state = await run_in_threadpool(
                lambda: tg.get_tutor_graph().invoke(service.graph_input(ctx, defer_generation=True))
            )
        except tg.TutorError:
            # Unusable model output twice: a neutral message, nothing saved, no turn charged.
            yield _sse("token", {"content": "Let's try that again. Could you say your answer once more?"})
            yield _sse("done", {"retry": True})
            return
        except Exception:
            logger.exception("Tutor evaluate failed for session %s", session_id)
            yield _sse("token", {"content": "Let's try that again. Could you say your answer once more?"})
            yield _sse("done", {"retry": True})
            return

        decision = state["decision"]
        messages = state.get("response_messages") or []
        text = ""

        if messages and session.language == "en":
            iterator = tg.stream_text(messages, current_user.id)
            while True:  # one network read at a time, off the event loop
                piece = await run_in_threadpool(next, iterator, None)
                if piece is None:
                    break
                text += piece
                yield _sse("token", {"content": piece})
        elif messages:
            # Urdu / Roman Urdu: generate whole, check script and Hindi, then send in pieces.
            raw = await run_in_threadpool(tg.generate_text, messages, current_user.id)
            target = Language(session.language)
            problem = lang._script_problem(target, raw)
            text = raw if not problem else ""
            for i in range(0, len(text), 40):
                yield _sse("token", {"content": text[i : i + 40]})

        final_text, replaced = service.finalize_text(ctx, decision, text or None)
        if replaced or final_text != text:
            yield _sse("replace", {"content": final_text})

        turn = service.commit_turn(db, ctx, state, final_text)
        full = service.serialize_session(db, session, with_turns=False)
        progress = full["progress"]
        yield _sse("done", {
            "turn_id": str(turn.id),
            "verdict": decision.get("verdict"),
            "hint_level": decision.get("hint_level"),
            "concept_index": progress["concept_index"],
            "total_concepts": progress["total_concepts"],
            "mastered_count": progress["mastered_count"],
            "revealed_count": progress["revealed_count"],
            "phase": progress["phase"],
            "turn_type": turn.turn_type,
            "source_refs": turn.source_refs or [],
            "finished": full["finished"],
            "turn_count": full["turn_count"],
            "max_turns": full["max_turns"],
        })

    return StreamingResponse(event_stream(), media_type="text/event-stream")

