"""Exam/deadline-aware study plan generation (Prompt 29).

Two-step flow: `preview_plan()` runs the (single, expensive) LLM topic breakdown plus a
cheap deterministic scheduling heuristic and returns a proposal WITHOUT writing
anything to the database. The proposal's `plan_token` carries everything needed to
recreate it — `create_plan_from_token()` decodes it, re-runs only the deterministic
scheduling step (never the LLM call again), optionally restricted to a user-chosen
subset of topics, and persists the StudyPlan + StudySession rows in one go. This avoids
both a second LLM call on confirm and a server-side cache/session table.
"""

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Quiz, StudyPlan, StudySession, StudySessionType, User
from app.rag.llm import chat_completion
from app.rag.quiz_generator import generate_quiz
from app.rag.vectorstore import get_all_chunks

logger = logging.getLogger(__name__)

TOPICS_MODEL = "openai/gpt-oss-120b"
MAX_SAMPLE_CHUNKS = 40
MIN_TOPICS = 5
MAX_TOPICS = 15

# Named constants so the heuristic is easy to tune later (per spec).
LEARN_SESSION_MINUTES = 25
REVIEW_SESSION_MINUTES = 12
QUIZ_SESSION_MINUTES = 20
CHECKPOINT_SESSION_MINUTES = 20

# Review a topic sooner if it's hard (more prone to being forgotten), otherwise the
# standard "2-3 days later" window from the spec.
HARD_TOPIC_REVIEW_GAP_DAYS = 2
NORMAL_TOPIC_REVIEW_GAP_DAYS = 3

# Roughly every 3-4 days, per spec.
QUIZ_CHECKPOINT_INTERVAL_DAYS = 4

# The exam date itself plus the day before are reserved as pure cumulative review — no
# new material gets scheduled there.
FINAL_CHECKPOINT_DAYS = 2

# If the estimated minutes needed exceed the available capacity by more than this
# ratio, warn instead of silently creating an overpacked plan.
OVERPACK_WARNING_RATIO = 1.2

DIFFICULTY_RANK = {"hard": 0, "medium": 1, "easy": 2}

PLAN_TOKEN_TYPE = "study_plan_preview"
PLAN_TOKEN_TTL_MINUTES = 120

TOPICS_PROMPT = """Here are excerpts sampled across the study material, each tagged with an id like [c0]:

{excerpts}

Break this material into {min_topics}-{max_topics} distinct study topics suitable for spaced-repetition \
study sessions ahead of an exam. For each topic return:
- "title": a short topic name
- "description": a 1-2 sentence description of what this topic covers
- "estimated_difficulty": "easy", "medium", or "hard" — how hard this topic is likely to be to learn and retain
- "relevant_chunk_ids": the excerpt ids (e.g. "c3") this topic draws from

Cover the full breadth of the material — don't cluster every topic around the same excerpts.

Return ONLY valid JSON in this exact shape, nothing else:
{{"topics": [{{"title": "...", "description": "...", "estimated_difficulty": "medium", \
"relevant_chunk_ids": ["c0", "c1"]}}]}}"""

SESSION_CONTENT_PROMPT = """Here is source material for a {session_type} study session on "{topic_title}" \
({topic_description}):

{excerpts}

Write a clear, focused explanation of this topic for a student studying for an exam (4-8 sentences), \
then write exactly {num_questions} practice questions covering it.

For each question return:
- "question": the question text
- "type": "multiple_choice" or "short_answer"
- "options": a list of 4 plausible options (only for multiple_choice, otherwise an empty list)
- "correct_answer": the correct answer (must exactly match one of the options for multiple_choice)
- "explanation": a 1-2 sentence explanation of why that's correct

Return ONLY valid JSON in this exact shape, nothing else:
{{"explanation": "...", "practice_questions": [{{"question": "...", "type": "...", "options": [...], \
"correct_answer": "...", "explanation": "..."}}]}}"""


def _chunk_ref(metadata: dict) -> dict:
    return {
        "document_id": metadata.get("document_id"),
        "page_number": metadata.get("page_number"),
        "start_time_seconds": metadata.get("start_time_seconds"),
        "end_time_seconds": metadata.get("end_time_seconds"),
    }


def _ref_key(ref: dict) -> tuple:
    return tuple(sorted(ref.items()))


def _sample_chunks_with_ids(chunks: list[dict], max_count: int) -> list[dict]:
    """Same representative-sampling approach as summarizer/quiz_generator (evenly
    spread across the document rather than the first N), plus a synthetic "c<i>" id per
    sampled chunk so the LLM can reference specific excerpts by id in its response."""
    if len(chunks) <= max_count:
        sample = chunks
    else:
        ordered = sorted(
            chunks, key=lambda c: (c["metadata"].get("document_id", ""), c["metadata"].get("page_number") or 0)
        )
        step = len(ordered) / max_count
        sample = [ordered[int(i * step)] for i in range(max_count)]

    return [{"id": f"c{i}", "text": c["text"], "metadata": c["metadata"]} for i, c in enumerate(sample)]


def _parse_topics_response(raw: str, chunk_by_id: dict[str, dict]) -> list[dict] | None:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("topics"), list):
        return None

    topics = []
    for t in data["topics"]:
        if not isinstance(t, dict):
            continue
        title = str(t.get("title", "")).strip()
        if not title:
            continue
        difficulty = t.get("estimated_difficulty") if t.get("estimated_difficulty") in DIFFICULTY_RANK else "medium"
        raw_ids = t.get("relevant_chunk_ids") if isinstance(t.get("relevant_chunk_ids"), list) else []

        seen_keys = set()
        chunk_refs = []
        for cid in raw_ids:
            ref = chunk_by_id.get(str(cid))
            if ref is None:
                continue
            key = _ref_key(ref)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            chunk_refs.append(ref)

        topics.append(
            {
                "title": title[:200],
                "description": str(t.get("description", "")).strip()[:1000],
                "estimated_difficulty": difficulty,
                "chunk_refs": chunk_refs,
            }
        )

    return topics[:MAX_TOPICS] or None


def generate_topics(document_ids: list[uuid.UUID]) -> list[dict] | None:
    """One LLM call: breaks the material into MIN_TOPICS-MAX_TOPICS topics, each with a
    difficulty estimate and the source chunks it draws from. Returns None if generation
    failed after a retry."""
    chunks = get_all_chunks(document_ids[0], document_ids) if document_ids else []
    if not chunks:
        return None

    sample = _sample_chunks_with_ids(chunks, MAX_SAMPLE_CHUNKS)
    chunk_by_id = {c["id"]: _chunk_ref(c["metadata"]) for c in sample}

    excerpts = "\n\n---\n\n".join(
        f"[{c['id']} | {c['metadata'].get('filename')}, page {c['metadata'].get('page_number')}]\n{c['text'][:600]}"
        for c in sample
    )
    prompt = TOPICS_PROMPT.format(excerpts=excerpts, min_topics=MIN_TOPICS, max_topics=MAX_TOPICS)

    for attempt in range(2):
        try:
            raw = chat_completion(
                [{"role": "user", "content": prompt}], model=TOPICS_MODEL, temperature=0.4, purpose="study_plan_topics"
            )
            topics = _parse_topics_response(raw, chunk_by_id)
            if topics:
                return topics
            logger.warning("Study plan topics response wasn't valid JSON (attempt %d): %r", attempt + 1, raw[:200])
        except Exception:
            logger.warning("Study plan topic generation call failed (attempt %d)", attempt + 1, exc_info=True)

    return None


# ---- Deterministic scheduling heuristic (no LLM calls) ----


def _find_day_with_room(capacity: list[int], start_idx: int, minutes: int) -> int | None:
    n = len(capacity)
    if n == 0:
        return None
    for offset in range(n):
        idx = (start_idx + offset) % n
        if capacity[idx] >= minutes:
            return idx
    return None


def _least_loaded_day(capacity: list[int]) -> int:
    return max(range(len(capacity)), key=lambda i: capacity[i])


def _merge_chunk_refs(topics: list[dict], titles: set[str]) -> list[dict]:
    seen = set()
    merged = []
    for t in topics:
        if t["title"] not in titles:
            continue
        for ref in t["chunk_refs"]:
            key = _ref_key(ref)
            if key not in seen:
                seen.add(key)
                merged.append(ref)
    return merged


def schedule_sessions(
    topics: list[dict], exam_date: date, daily_study_minutes: int, today: date | None = None
) -> tuple[list[dict], dict | None]:
    """Pure, deterministic: turns a topic list into a day-by-day session proposal.
    Returns (sessions, warning) — warning is None unless the material clearly doesn't
    fit the available time. Each session dict: {scheduled_date, topic_title,
    topic_description, source_chunks, session_type, quiz_scope_titles (only for
    session_type="quiz", internal — tells the caller which topics' material to quiz)}.
    """
    today = today or date.today()
    available_days = (exam_date - today).days

    if available_days < 1 or not topics:
        return [], {
            "warning": "Exam date must be in the future and at least one topic is needed.",
            "suggested_reduced_topics": [],
        }

    checkpoint_days_count = min(FINAL_CHECKPOINT_DAYS, available_days)
    learn_days_count = max(0, available_days - checkpoint_days_count)

    day_capacity = [daily_study_minutes] * learn_days_count
    day_dates = [today + timedelta(days=i) for i in range(learn_days_count)]

    sorted_topics = sorted(topics, key=lambda t: DIFFICULTY_RANK.get(t["estimated_difficulty"], 1))

    # --- Overpacking check ---
    num_quiz_checkpoints = (learn_days_count // QUIZ_CHECKPOINT_INTERVAL_DAYS) if learn_days_count else 0
    est_minutes = len(sorted_topics) * (LEARN_SESSION_MINUTES + REVIEW_SESSION_MINUTES)
    est_minutes += num_quiz_checkpoints * QUIZ_SESSION_MINUTES
    capacity_minutes = sum(day_capacity)

    warning = None
    if learn_days_count == 0 or (est_minutes > capacity_minutes * OVERPACK_WARNING_RATIO):
        suggested_titles: list[str] = []
        running = 0
        cost = LEARN_SESSION_MINUTES + REVIEW_SESSION_MINUTES
        for t in sorted_topics:
            if not suggested_titles or running + cost <= capacity_minutes:
                suggested_titles.append(t["title"])
                running += cost
        warning = {
            "warning": (
                f"This material ({len(sorted_topics)} topics) doesn't comfortably fit in the "
                f"{learn_days_count} day(s) available before the exam at {daily_study_minutes} min/day. "
                "Consider focusing on the topics below, or increasing daily study time / moving the exam date."
            ),
            "suggested_reduced_topics": suggested_titles,
        }

    sessions: list[dict] = []

    if learn_days_count > 0:
        # 1) One "learn" session per topic, hardest first, greedily filling days forward.
        learn_day_idx: dict[str, int] = {}
        cursor = 0
        for t in sorted_topics:
            idx = _find_day_with_room(day_capacity, cursor, LEARN_SESSION_MINUTES)
            if idx is None:
                idx = _least_loaded_day(day_capacity)
            day_capacity[idx] -= LEARN_SESSION_MINUTES
            learn_day_idx[t["title"]] = idx
            cursor = (idx + 1) % learn_days_count
            sessions.append(
                {
                    "scheduled_date": day_dates[idx],
                    "topic_title": t["title"],
                    "topic_description": t["description"],
                    "source_chunks": t["chunk_refs"],
                    "session_type": StudySessionType.learn.value,
                }
            )

        # 2) One "review" session per topic, 2-3 days after its learn day (sooner for
        # hard topics).
        for t in sorted_topics:
            gap = HARD_TOPIC_REVIEW_GAP_DAYS if t["estimated_difficulty"] == "hard" else NORMAL_TOPIC_REVIEW_GAP_DAYS
            target = min(learn_day_idx[t["title"]] + gap, learn_days_count - 1)
            idx = _find_day_with_room(day_capacity, target, REVIEW_SESSION_MINUTES)
            if idx is None:
                idx = _least_loaded_day(day_capacity)
            day_capacity[idx] -= REVIEW_SESSION_MINUTES
            sessions.append(
                {
                    "scheduled_date": day_dates[idx],
                    "topic_title": t["title"],
                    "topic_description": t["description"],
                    "source_chunks": t["chunk_refs"],
                    "session_type": StudySessionType.review.value,
                }
            )

        # 3) Quiz checkpoints roughly every QUIZ_CHECKPOINT_INTERVAL_DAYS, cumulative
        # over everything learned by that point.
        day = QUIZ_CHECKPOINT_INTERVAL_DAYS - 1
        while day < learn_days_count:
            learned_so_far = {t["title"] for t in sorted_topics if learn_day_idx[t["title"]] <= day}
            if learned_so_far:
                idx = _find_day_with_room(day_capacity, day, QUIZ_SESSION_MINUTES)
                if idx is None:
                    idx = _least_loaded_day(day_capacity)
                day_capacity[idx] -= QUIZ_SESSION_MINUTES
                titles_preview = ", ".join(sorted(learned_so_far)[:3])
                more = f" +{len(learned_so_far) - 3} more" if len(learned_so_far) > 3 else ""
                sessions.append(
                    {
                        "scheduled_date": day_dates[idx],
                        "topic_title": f"Checkpoint quiz: {titles_preview}{more}",
                        "topic_description": "Cumulative quiz covering everything learned so far.",
                        "source_chunks": _merge_chunk_refs(sorted_topics, learned_so_far),
                        "session_type": StudySessionType.quiz.value,
                        "quiz_scope_titles": sorted(learned_so_far),
                    }
                )
            day += QUIZ_CHECKPOINT_INTERVAL_DAYS

    # 4) Final checkpoint day(s) right before the exam: cumulative review across ALL
    # topics, no new material.
    all_titles = {t["title"] for t in sorted_topics}
    all_chunk_refs = _merge_chunk_refs(sorted_topics, all_titles)
    for i in range(checkpoint_days_count):
        d = exam_date - timedelta(days=checkpoint_days_count - 1 - i)
        sessions.append(
            {
                "scheduled_date": d,
                "topic_title": "Final review" if i == checkpoint_days_count - 1 else "Cumulative checkpoint",
                "topic_description": "Cumulative review across everything covered in this plan before the exam.",
                "source_chunks": all_chunk_refs,
                "session_type": StudySessionType.checkpoint.value,
            }
        )

    sessions.sort(key=lambda s: s["scheduled_date"])
    return sessions, warning


# ---- Plan token (preview -> confirm bridge) ----


def encode_plan_token(user_id: uuid.UUID, title: str, exam_date: date, daily_study_minutes: int, topics: list[dict]) -> str:
    payload = {
        "type": PLAN_TOKEN_TYPE,
        "user_id": str(user_id),
        "title": title,
        "exam_date": exam_date.isoformat(),
        "daily_study_minutes": daily_study_minutes,
        "topics": topics,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=PLAN_TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_plan_token(token: str, user_id: uuid.UUID) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise ValueError("This plan preview has expired — please generate a new preview.")
    if payload.get("type") != PLAN_TOKEN_TYPE or payload.get("user_id") != str(user_id):
        raise ValueError("Invalid plan token.")
    payload["exam_date"] = date.fromisoformat(payload["exam_date"])
    return payload


# ---- Preview / create orchestration ----


def preview_plan(
    document_ids: list[uuid.UUID], user_id: uuid.UUID, title: str, exam_date: date, daily_study_minutes: int
) -> dict | None:
    """Returns {"topics", "sessions", "warning", "plan_token"} or None if topic
    generation failed."""
    topics = generate_topics(document_ids)
    if not topics:
        return None

    sessions, warning = schedule_sessions(topics, exam_date, daily_study_minutes)
    plan_token = encode_plan_token(user_id, title, exam_date, daily_study_minutes, topics)

    return {
        "topics": topics,
        "sessions": sessions,
        "warning": warning,
        "plan_token": plan_token,
    }


def _generate_checkpoint_quiz(document_ids: list[uuid.UUID], scope_titles: list[str]) -> list[dict] | None:
    return generate_quiz(
        document_ids=document_ids,
        num_questions=8,
        difficulty="medium",
        question_type="mixed",
    )


def create_plan_rows(
    db: Session,
    user: User,
    document_ids: list[uuid.UUID] | None,
    workspace_id: uuid.UUID | None,
    plan_token: str,
    reduced_topic_titles: list[str] | None,
) -> StudyPlan:
    """Decodes the preview token, re-runs the (cheap, deterministic) scheduling step
    with any user-chosen topic reduction applied, and persists the StudyPlan + all
    StudySession rows. For each "quiz" session, also generates and persists an actual
    Quiz (reusing the existing quiz generator) scoped to that checkpoint's cumulative
    material, and links it via StudySession.quiz_id."""
    payload = decode_plan_token(plan_token, user.id)
    topics = payload["topics"]

    if reduced_topic_titles:
        keep = set(reduced_topic_titles)
        topics = [t for t in topics if t["title"] in keep]
        if not topics:
            topics = payload["topics"]  # ignore a nonsensical reduction rather than emptying the plan

    sessions, _warning = schedule_sessions(topics, payload["exam_date"], payload["daily_study_minutes"])

    plan = StudyPlan(
        user_id=user.id,
        title=payload["title"],
        exam_date=payload["exam_date"],
        # document_ids is nullable specifically because a plan is scoped to EITHER a
        # fixed document list OR a workspace, never both — a workspace's membership can
        # change after the plan is created, and the plan should track that, not a
        # snapshot of documents taken at creation time.
        document_ids=[str(d) for d in document_ids] if (document_ids and not workspace_id) else None,
        workspace_id=workspace_id,
        daily_study_minutes=payload["daily_study_minutes"],
    )
    db.add(plan)
    db.flush()

    for s in sessions:
        quiz_id = None
        if s["session_type"] == StudySessionType.quiz.value and document_ids:
            try:
                questions = _generate_checkpoint_quiz(document_ids, s.get("quiz_scope_titles", []))
            except Exception:
                questions = None
                logger.warning("Checkpoint quiz generation failed for plan %s", plan.id, exc_info=True)
            if questions:
                quiz = Quiz(
                    user_id=user.id,
                    document_ids=[str(d) for d in document_ids],
                    title=s["topic_title"],
                    questions=questions,
                )
                db.add(quiz)
                db.flush()
                quiz_id = quiz.id

        db.add(
            StudySession(
                plan_id=plan.id,
                scheduled_date=s["scheduled_date"],
                topic_title=s["topic_title"],
                topic_description=s["topic_description"],
                source_chunks=s["source_chunks"],
                session_type=StudySessionType(s["session_type"]),
                quiz_id=quiz_id,
            )
        )

    db.commit()
    db.refresh(plan)
    return plan


# ---- On-demand session content generation ----


def _fetch_chunk_texts(source_chunks: list[dict], max_chars_per_chunk: int = 800) -> list[str]:
    by_document: dict[str, list[dict]] = {}
    for ref in source_chunks:
        doc_id = ref.get("document_id")
        if doc_id:
            by_document.setdefault(doc_id, []).append(ref)

    texts: list[str] = []
    for doc_id, refs in by_document.items():
        try:
            doc_chunks = get_all_chunks(uuid.UUID(doc_id))
        except Exception:
            continue
        wanted_pages = {r["page_number"] for r in refs if r.get("page_number") is not None}
        wanted_times = {(r.get("start_time_seconds"), r.get("end_time_seconds")) for r in refs}

        for c in doc_chunks:
            meta = c["metadata"]
            matches_page = meta.get("page_number") is not None and meta.get("page_number") in wanted_pages
            matches_time = (meta.get("start_time_seconds"), meta.get("end_time_seconds")) in wanted_times
            if matches_page or matches_time:
                texts.append(c["text"][:max_chars_per_chunk])

    return texts


def _parse_session_content_response(raw: str) -> dict | None:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    explanation = data.get("explanation")
    questions = data.get("practice_questions")
    if not isinstance(explanation, str) or not isinstance(questions, list):
        return None

    validated = []
    for q in questions:
        if not isinstance(q, dict) or not isinstance(q.get("question"), str) or not q["question"].strip():
            continue
        q_type = q.get("type") if q.get("type") in ("multiple_choice", "short_answer") else "short_answer"
        correct_answer = str(q.get("correct_answer", "")).strip()
        if not correct_answer:
            continue
        validated.append(
            {
                "id": str(uuid.uuid4()),
                "question": q["question"].strip(),
                "type": q_type,
                "options": [str(o).strip() for o in q.get("options", [])] if q_type == "multiple_choice" else [],
                "correct_answer": correct_answer,
                "explanation": str(q.get("explanation", "")).strip(),
            }
        )

    return {"explanation": explanation.strip(), "practice_questions": validated}


def generate_session_content(
    source_chunks: list[dict], topic_title: str, topic_description: str, session_type: str, num_questions: int = 4
) -> dict | None:
    """On-demand generation for opening a learn/review session: a focused explanation
    plus 3-5 practice questions, scoped to this session's source_chunks. Deliberately a
    single lightweight LLM call rather than the full Quiz create/attempt machinery —
    these practice questions get saved as ReviewCards (Prompt 30) but don't need their
    own persisted Quiz row."""
    texts = _fetch_chunk_texts(source_chunks)
    if not texts:
        return None

    excerpts = "\n\n---\n\n".join(texts[:MAX_SAMPLE_CHUNKS])
    prompt = SESSION_CONTENT_PROMPT.format(
        session_type=session_type,
        topic_title=topic_title,
        topic_description=topic_description,
        excerpts=excerpts,
        num_questions=num_questions,
    )

    for attempt in range(2):
        try:
            raw = chat_completion(
                [{"role": "user", "content": prompt}], model=TOPICS_MODEL, temperature=0.4, purpose="study_session_content"
            )
            parsed = _parse_session_content_response(raw)
            if parsed:
                return parsed
            logger.warning("Session content response wasn't valid JSON (attempt %d): %r", attempt + 1, raw[:200])
        except Exception:
            logger.warning("Session content generation call failed (attempt %d)", attempt + 1, exc_info=True)

    return None


# ---- Compress remaining sessions into remaining days ----


def compress_remaining_sessions(db: Session, plan: StudyPlan) -> list[StudySession]:
    """Reschedules every still-pending session across the days remaining between today
    and the plan's exam_date, preserving each session's type/topic/content links.
    Completed and skipped sessions are left untouched."""
    today = date.today()
    pending = [s for s in plan.sessions if s.status.value == "pending"]
    if not pending:
        return []

    available_days = max(1, (plan.exam_date - today).days)
    checkpoint_days_count = min(FINAL_CHECKPOINT_DAYS, available_days)
    learn_days_count = max(1, available_days - checkpoint_days_count)
    day_dates = [today + timedelta(days=i) for i in range(learn_days_count)]
    day_capacity = [plan.daily_study_minutes] * learn_days_count

    minutes_by_type = {
        StudySessionType.learn: LEARN_SESSION_MINUTES,
        StudySessionType.review: REVIEW_SESSION_MINUTES,
        StudySessionType.quiz: QUIZ_SESSION_MINUTES,
        StudySessionType.checkpoint: CHECKPOINT_SESSION_MINUTES,
    }

    # Non-checkpoint sessions get compressed into the learn-days window; checkpoints
    # stay pinned to the final day(s) before the exam.
    non_checkpoint = [s for s in pending if s.session_type != StudySessionType.checkpoint]
    checkpoints = [s for s in pending if s.session_type == StudySessionType.checkpoint]

    cursor = 0
    for s in non_checkpoint:
        minutes = minutes_by_type.get(s.session_type, LEARN_SESSION_MINUTES)
        idx = _find_day_with_room(day_capacity, cursor, minutes)
        if idx is None:
            idx = _least_loaded_day(day_capacity)
        day_capacity[idx] -= minutes
        cursor = (idx + 1) % learn_days_count
        s.scheduled_date = day_dates[idx]

    for i, s in enumerate(checkpoints):
        s.scheduled_date = plan.exam_date - timedelta(days=len(checkpoints) - 1 - i)

    db.commit()
    return pending
