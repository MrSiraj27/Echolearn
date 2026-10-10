"""Persistence and orchestration for Tutor Mode. The engine is app/rag/tutor_graph.py (pure,
no database); this module loads state, runs the graph, and writes back what changed."""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.languages import Language
from app.core.usage import enforce_quota, record_usage
from app.models import TutorConceptState, TutorSession, TutorTurn, User
from app.rag import language_explainer as lang
from app.rag import tutor_graph as tg
from app.rag.llm import chat_completion
from app.study.card_service import create_review_cards

logger = logging.getLogger(__name__)

TURN_TYPE_BY_KIND = {
    "praise_next_question": "question",
    "praise_advance": "feedback",
    "check_feedback": "check",
    "reveal": "explanation",
    "hint": "hint",
    "skip": "feedback",
}

INTRO = "Let's work on **{topic}** together. I'll ask you questions based on your own notes, and give hints if you need them. You can always tap “Just tell me”."


# ------------------------------------------------------------------ state <-> dict


def ordered_states(db: Session, session: TutorSession) -> list[TutorConceptState]:
    return (
        db.query(TutorConceptState)
        .filter(TutorConceptState.session_id == session.id)
        .order_by(TutorConceptState.concept_index.asc())
        .all()
    )


def state_to_dict(row: TutorConceptState) -> dict:
    return {
        "attempts": row.attempts, "hints_used": row.hints_used, "revealed": row.revealed, "mastered": row.mastered,
        "phase": row.phase, "hint_level": row.hint_level, "current_question": row.current_question,
        "check_attempts": row.check_attempts,
    }


def apply_state(row: TutorConceptState, data: dict) -> None:
    for key in ("attempts", "hints_used", "revealed", "mastered", "phase", "hint_level", "current_question", "check_attempts"):
        setattr(row, key, data[key])


def concepts_of(session: TutorSession) -> list[dict]:
    return (session.plan or {}).get("concepts", [])


def is_finished(session: TutorSession, states: list[TutorConceptState]) -> bool:
    if session.status != "active":
        return False
    return session.turn_count >= session.max_turns or all(s.phase == "done" for s in states)


def progress_of(session: TutorSession, states: list[TutorConceptState]) -> dict:
    concepts = concepts_of(session)
    idx = min(session.current_step, max(len(concepts) - 1, 0))
    current = states[idx] if states else None
    return {
        "concept_index": idx,
        "total_concepts": len(concepts),
        "mastered_count": sum(1 for s in states if s.mastered),
        "revealed_count": sum(1 for s in states if s.revealed),
        "hint_level": current.hint_level if current else 0,
        "phase": current.phase if current else "starter",
        "concepts": [
            {
                "index": s.concept_index, "name": s.concept, "phase": s.phase, "mastered": s.mastered,
                "revealed": s.revealed, "attempts": s.attempts, "hints_used": s.hints_used,
            }
            for s in states
        ],
    }


def serialize_session(db: Session, session: TutorSession, with_turns: bool = True) -> dict:
    states = ordered_states(db, session)
    turns = []
    if with_turns:
        turns = (
            db.query(TutorTurn).filter(TutorTurn.session_id == session.id).order_by(TutorTurn.created_at.asc()).all()
        )
    return {
        "id": session.id, "title": session.title, "topic": session.topic, "level": session.level,
        "language": session.language, "status": session.status, "turn_count": session.turn_count,
        "max_turns": session.max_turns, "document_ids": session.document_ids or [],
        "workspace_id": session.workspace_id, "created_at": session.created_at, "completed_at": session.completed_at,
        "summary": session.summary, "progress": progress_of(session, states),
        "finished": is_finished(session, states), "turns": turns,
    }


def _public_refs(concept: dict) -> list[dict]:
    return [{k: v for k, v in s.items() if k != "source_chunk_id"} for s in concept.get("sources", [])]


# ------------------------------------------------------------------ language helper


def translate_text(text: str, language: str, user_id: uuid.UUID) -> str:
    """Translate a short tutor message into Urdu/Roman Urdu with the shared rules and checks;
    on any failure, return the English text rather than risk a bad rendering."""
    if language == "en":
        return text
    target = Language(language)
    script_rules = lang.URDU_SCRIPT_RULES if target == Language.ur else lang.ROMAN_URDU_SCRIPT_RULES
    system = (
        f"Translate the text into {lang.LANGUAGE_LABELS[target]}.\n{script_rules}\n{lang.SHARED_RULES}\n"
        "Keep **bold** markers. Output only the translation."
    )
    try:
        out = chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": text}],
            model=tg.RESPOND_MODEL, temperature=0.2, purpose="tutor_respond", user_id=user_id, groq_extra=tg.LOW_EFFORT,
        ).strip()
    except Exception:
        logger.warning("Tutor message translation failed", exc_info=True)
        return text
    if not out or lang._script_problem(target, out) or (lang._numbers_in(out) - lang._numbers_in(text)):
        return text
    return out


# ------------------------------------------------------------------ create


def create_session(
    db: Session, user: User, topic: str, document_ids: list[uuid.UUID], workspace_id: uuid.UUID | None,
    level: str, language: str, max_turns: int,
) -> TutorSession:
    """Builds the plan (raises tg.TutorNotCovered / tg.TutorError), then stores the session
    and its first tutor message. Quota is charged only after all of that succeeds."""
    enforce_quota(db, user, "tutor_session")
    plan = tg.build_plan(user.id, document_ids, topic, level)
    concepts = plan["concepts"]

    session = TutorSession(
        user_id=user.id, title=f"Tutor: {topic}"[:120], document_ids=[str(d) for d in document_ids],
        workspace_id=workspace_id, topic=topic, level=level, language=language, status="active",
        turn_count=0, max_turns=max_turns, plan=plan, current_step=0,
    )
    db.add(session)
    db.flush()
    for i, concept in enumerate(concepts):
        db.add(TutorConceptState(
            session_id=session.id, concept_index=i, concept=concept["name"],
            source_chunk_ids=[s.get("source_chunk_id") for s in concept["sources"]],
            phase="starter", hint_level=0, current_question=concept["starter_question"] if i == 0 else None,
        ))

    first = concepts[0]
    text = f"{INTRO.format(topic=topic)}\n\n**{first['starter_question']}**"
    text = translate_text(text, language, user.id)
    db.add(TutorTurn(
        session_id=session.id, step_index=0, role="tutor", content=text, turn_type="question", hint_level=0,
        source_refs=_public_refs(first),
    ))
    db.commit()
    db.refresh(session)
    record_usage(db, user.id, "tutor_session")  # only now that everything succeeded
    return session


# ------------------------------------------------------------------ one turn


@dataclass
class TurnContext:
    session: TutorSession
    user: User
    action: str
    content: str | None
    idx: int
    concept: dict
    next_concept: dict | None
    row: TutorConceptState
    cstate: dict


def prepare_turn(db: Session, user: User, session: TutorSession, action: str, content: str | None) -> TurnContext:
    if session.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This session has ended.")
    states = ordered_states(db, session)
    if is_finished(session, states):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This session is complete. Finish it to see your summary.",
        )
    concepts = concepts_of(session)
    idx = session.current_step
    if idx >= len(concepts):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This session is complete.")
    if action == "answer" and not (content or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Write an answer first.")
    if action != "skip":
        # Every turn that calls the model also counts toward the plan's normal message limit,
        # so a session can't be used to bypass it. Charged only after the turn succeeds.
        enforce_quota(db, user, "message")
    row = states[idx]
    return TurnContext(
        session=session, user=user, action=action, content=(content or "").strip() or None, idx=idx,
        concept=concepts[idx], next_concept=concepts[idx + 1] if idx + 1 < len(concepts) else None,
        row=row, cstate=state_to_dict(row),
    )


def graph_input(ctx: TurnContext, defer_generation: bool) -> dict:
    return {
        "user_id": str(ctx.user.id), "language": ctx.session.language, "action": ctx.action,
        "student_message": ctx.content or "", "concept": ctx.concept, "next_concept": ctx.next_concept,
        "cstate": ctx.cstate, "defer_generation": defer_generation,
    }


def _ensure_question(text: str, question: str | None, language: str) -> str:
    """The reply must end by asking the exact validated question. If the model dropped or
    reworded it (English only; other languages are translated), append it."""
    if not question or language != "en":
        return text
    if question.strip().lower() in text.lower():
        return text
    return f"{text}\n\n**{question}**"


def finalize_text(ctx: TurnContext, decision: dict, raw_text: str | None) -> tuple[str, bool]:
    """(final reply, replaced). Falls back to a deterministic grounded message if the model's
    text broke a rule or couldn't be produced."""
    asked = decision.get("question") if decision["kind"] in ("praise_next_question", "reveal") else decision.get("next_question")
    if not raw_text:
        text = tg.safe_fallback_text(decision, ctx.concept)
        if decision["kind"] == "skip" and decision.get("next_question"):
            text = f"{text}\n\n**{decision['next_question']}**"
        return text, False
    extra = " ".join([ctx.content or "", asked or "", decision.get("next_question") or ""])
    if not tg.text_is_grounded(raw_text, ctx.concept, extra):
        logger.info("Tutor reply broke the grounding rule; using the safe fallback")
        text = tg.safe_fallback_text(decision, ctx.concept)
        if decision.get("next_question") and decision["kind"] in ("praise_advance", "check_feedback"):
            text = f"{text}\n\n**{decision['next_question']}**"
        return text, True
    return _ensure_question(raw_text, asked, ctx.session.language), False


def commit_turn(db: Session, ctx: TurnContext, state: dict, text: str) -> TutorTurn:
    """Persist one finished turn: the student's message, the tutor's reply and the new state."""
    session, decision = ctx.session, state["decision"]
    evaluation = state.get("evaluation")
    refs = _public_refs(ctx.concept)

    if ctx.action == "answer":
        db.add(TutorTurn(
            session_id=session.id, step_index=ctx.idx, role="student", content=ctx.content or "",
            verdict=(evaluation or {}).get("verdict"),
        ))
    tutor_type = "answer_reveal" if ctx.action == "just_tell_me" else TURN_TYPE_BY_KIND.get(decision["kind"], "feedback")
    turn = TutorTurn(
        session_id=session.id, step_index=ctx.idx, role="tutor", content=text, turn_type=tutor_type,
        hint_level=decision.get("hint_level"), verdict=decision.get("verdict"), source_refs=refs,
    )
    db.add(turn)

    apply_state(ctx.row, state["cstate"])
    session.turn_count += 1

    if decision.get("advance") and ctx.next_concept is not None:
        session.current_step = ctx.idx + 1
        nxt = db.query(TutorConceptState).filter(
            TutorConceptState.session_id == session.id, TutorConceptState.concept_index == ctx.idx + 1
        ).first()
        if nxt:
            nxt.phase = "starter"
            nxt.hint_level = 0
            nxt.current_question = ctx.next_concept["starter_question"]
    db.commit()
    db.refresh(turn)

    if ctx.action != "skip":
        record_usage(db, ctx.user.id, "message")  # charged only after a successful turn
    return turn


# ------------------------------------------------------------------ end + cards


def end_session(db: Session, user: User, session: TutorSession) -> TutorSession:
    """Generate the summary, turn revealed / not-mastered concepts into ReviewCards (deduped by
    the shared card service), and complete the session. Safe to call twice."""
    if session.status == "completed" and session.summary:
        return session

    states = ordered_states(db, session)
    concepts = concepts_of(session)
    touched = [
        i for i, s in enumerate(states)
        if s.attempts > 0 or s.hints_used > 0 or s.revealed or s.mastered or s.phase == "done"
    ]
    state_dicts = [state_to_dict(states[i]) for i in touched]
    summary = tg.get_tutor_graph().invoke({
        "user_id": str(user.id), "language": session.language, "action": "end",
        "concepts": [concepts[i] for i in touched], "states": state_dicts,
    })["summary"]

    # Cards for concepts that were revealed or not mastered; never for mastered ones.
    cards_added = 0
    by_document: dict[str, list[dict]] = {}
    for i in touched:
        s, c = states[i], concepts[i]
        if s.mastered or not c.get("sources"):
            continue
        src = c["sources"][0]
        if not src.get("document_id"):
            continue
        by_document.setdefault(src["document_id"], []).append({
            "question": c["starter_question"],
            "answer": f"{c['key_idea']} " + "; ".join(c["expected_points"]),
            "question_type": "short_answer",
            "source_chunk_id": src.get("source_chunk_id"),
        })
    for document_id, items in by_document.items():
        try:
            cards_added += len(create_review_cards(db, user.id, uuid.UUID(document_id), items, commit=True))
        except Exception:
            logger.warning("Couldn't create review cards for tutor session %s", session.id, exc_info=True)
            db.rollback()

    summary["cards_added"] = cards_added
    mastered = sum(1 for s in states if s.mastered)
    summary["mastered_count"] = mastered
    summary["total_concepts"] = len(concepts)

    session.summary = summary
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    lines = [f"You mastered {mastered} of {len(concepts)} concepts."]
    if cards_added:
        lines.append(f"I added {cards_added} flashcard{'s' if cards_added != 1 else ''} to your Daily Review for the ones to revisit.")
    db.add(TutorTurn(
        session_id=session.id, step_index=session.current_step, role="tutor", content=" ".join(lines), turn_type="summary",
    ))
    db.commit()
    db.refresh(session)
    return session
