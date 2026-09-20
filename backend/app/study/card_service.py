"""Shared ReviewCard creation, used by: quiz generation, StudySession practice-question
generation, and manual "save as flashcard" (Prompt 30 + Prompt 29)."""

import logging
import math
import uuid

from sqlalchemy.orm import Session

from app.models import ReviewCard, ReviewCardState, ReviewQuestionType
from app.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)

# Cosine-similarity threshold above which a candidate question is treated as a
# near-duplicate of an existing card and skipped. Chosen empirically for
# all-MiniLM-L6-v2 (the model app.rag.embeddings already uses): near-identical or
# lightly-reworded questions on this model typically score >0.95, while genuinely
# distinct questions about the same topic/section usually fall in the 0.6-0.85 range.
# 0.92 sits comfortably above that gap, so it catches paraphrase-level duplicates
# (the common case when the same material gets quizzed repeatedly) without discarding
# distinct questions that merely share vocabulary.
DEDUPE_SIMILARITY_THRESHOLD = 0.92

# Bound how many existing questions we embed-compare against per insert, most recent
# first — this is an O(n) scan per candidate, which is fine for a personal flashcard
# deck but shouldn't be allowed to grow unbounded for a very prolific user.
MAX_DEDUPE_CANDIDATES = 500


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _is_near_duplicate(db: Session, user_id: uuid.UUID, question_text: str) -> bool:
    existing = (
        db.query(ReviewCard.question)
        .filter(ReviewCard.user_id == user_id)
        .order_by(ReviewCard.created_at.desc())
        .limit(MAX_DEDUPE_CANDIDATES)
        .all()
    )
    if not existing:
        return False

    texts = [question_text] + [row[0] for row in existing]
    embeddings = get_embeddings(texts)
    candidate_embedding = embeddings[0]

    for other_embedding in embeddings[1:]:
        if _cosine_similarity(candidate_embedding, other_embedding) > DEDUPE_SIMILARITY_THRESHOLD:
            return True
    return False


def create_review_cards(
    db: Session,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    items: list[dict],
    commit: bool = True,
) -> list[ReviewCard]:
    """Insert a ReviewCard (+ initial ReviewCardState) for each item, skipping any that
    look like a near-duplicate of a card this user already has.

    Each item: {"question": str, "answer": str, "question_type": str | None,
    "options": list | None, "source_chunk_id": str | None}.
    """
    created: list[ReviewCard] = []

    for item in items:
        question = (item.get("question") or "").strip()
        answer = (item.get("answer") or "").strip()
        if not question or not answer:
            continue

        try:
            if _is_near_duplicate(db, user_id, question):
                continue
        except Exception:
            # Embedding the dedupe check failed (e.g. model not loaded) — better to save
            # a possible duplicate than to silently drop a card the user is expecting.
            logger.warning("ReviewCard dedupe check failed; inserting anyway", exc_info=True)

        q_type_raw = item.get("question_type") or "short_answer"
        try:
            q_type = ReviewQuestionType(q_type_raw)
        except ValueError:
            q_type = ReviewQuestionType.short_answer

        card = ReviewCard(
            user_id=user_id,
            document_id=document_id,
            question=question,
            answer=answer,
            question_type=q_type,
            options=item.get("options") or None,
            source_chunk_id=item.get("source_chunk_id"),
        )
        db.add(card)
        db.flush()  # populate card.id for the state row below

        db.add(ReviewCardState(review_card_id=card.id, user_id=user_id))
        created.append(card)

    if commit and created:
        db.commit()
        for card in created:
            db.refresh(card)

    return created


def source_chunk_id_for(metadata: dict) -> str | None:
    """Build the composite jump-back identifier from a vectorstore chunk's metadata
    dict (see app.rag.chunking) — page number for paginated documents, timestamp range
    for audio/video transcripts."""
    if metadata.get("start_time_seconds") is not None:
        start = metadata.get("start_time_seconds")
        end = metadata.get("end_time_seconds")
        return f"time:{start}-{end}"
    page_number = metadata.get("page_number")
    if page_number is not None:
        return f"page:{page_number}"
    return None
