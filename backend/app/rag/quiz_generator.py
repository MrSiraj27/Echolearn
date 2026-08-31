import json
import logging
import uuid

from app.rag.llm import chat_completion
from app.rag.vectorstore import get_all_chunks

logger = logging.getLogger(__name__)

QUIZ_MODEL = "openai/gpt-oss-120b"
MAX_SAMPLE_CHUNKS = 24

QUIZ_PROMPT = """Here are excerpts sampled across one or more documents:

{excerpts}

Generate exactly {num_questions} quiz questions at {difficulty} difficulty, covering a \
broad spread of the material above (don't cluster all questions around one excerpt). \
Question type: {question_type_instruction}

For each question return:
- "question": the question text
- "type": "multiple_choice" or "short_answer"
- "options": a list of 4 plausible options (only for multiple_choice, otherwise an empty list)
- "correct_answer": the correct answer (must exactly match one of the options for multiple_choice)
- "explanation": a 1-2 sentence explanation of why that's correct, referencing the material
- "source_page": the page number (integer) of the excerpt this question is based on
- "source_filename": the filename of the excerpt this question is based on

Return ONLY valid JSON in this exact shape, nothing else:
{{"questions": [{{"question": "...", "type": "...", "options": [...], "correct_answer": "...", \
"explanation": "...", "source_page": 1, "source_filename": "..."}}]}}"""

QUESTION_TYPE_INSTRUCTIONS = {
    "multiple_choice": "All questions must be multiple_choice.",
    "short_answer": "All questions must be short_answer.",
    "mixed": "Mix multiple_choice and short_answer roughly evenly.",
}


def _sample_chunks(chunks: list[dict], max_count: int) -> list[dict]:
    if len(chunks) <= max_count:
        return chunks
    ordered = sorted(chunks, key=lambda c: (c["metadata"].get("document_id", ""), c["metadata"].get("page_number") or 0))
    step = len(ordered) / max_count
    return [ordered[int(i * step)] for i in range(max_count)]


def _validate_questions(data: dict) -> list[dict] | None:
    if not isinstance(data, dict):
        return None
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        return None

    validated = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        if not isinstance(q.get("question"), str) or not q["question"].strip():
            continue
        q_type = q.get("type") if q.get("type") in ("multiple_choice", "short_answer") else "short_answer"
        options = q.get("options") if isinstance(q.get("options"), list) else []
        correct_answer = str(q.get("correct_answer", "")).strip()
        if not correct_answer:
            continue

        validated.append(
            {
                "id": str(uuid.uuid4()),
                "question": q["question"].strip(),
                "type": q_type,
                "options": [str(o).strip() for o in options] if q_type == "multiple_choice" else [],
                "correct_answer": correct_answer,
                "explanation": str(q.get("explanation", "")).strip(),
                "source_page": q.get("source_page") if isinstance(q.get("source_page"), int) else None,
                "source_filename": q.get("source_filename") if isinstance(q.get("source_filename"), str) else None,
            }
        )

    return validated or None


def _parse_quiz_response(raw: str) -> list[dict] | None:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return _validate_questions(data)


def generate_quiz(
    document_ids: list[uuid.UUID],
    num_questions: int = 10,
    difficulty: str = "medium",
    question_type: str = "mixed",
) -> list[dict] | None:
    """Returns a list of validated question dicts, or None if generation failed twice."""
    chunks = get_all_chunks(document_ids[0], document_ids) if document_ids else []
    if not chunks:
        return None

    sample = _sample_chunks(chunks, MAX_SAMPLE_CHUNKS)
    excerpts = "\n\n---\n\n".join(
        f"[{c['metadata'].get('filename')}, page {c['metadata'].get('page_number')}]\n{c['text'][:800]}"
        for c in sample
    )

    prompt = QUIZ_PROMPT.format(
        excerpts=excerpts,
        num_questions=num_questions,
        difficulty=difficulty,
        question_type_instruction=QUESTION_TYPE_INSTRUCTIONS.get(question_type, QUESTION_TYPE_INSTRUCTIONS["mixed"]),
    )

    for attempt in range(2):
        try:
            raw = chat_completion([{"role": "user", "content": prompt}], model=QUIZ_MODEL, temperature=0.5, purpose="quiz_generation")
            questions = _parse_quiz_response(raw)
            if questions:
                return questions[:num_questions]
            logger.warning("Quiz response wasn't valid JSON (attempt %d): %r", attempt + 1, raw[:200])
        except Exception:
            logger.warning("Quiz generation call failed (attempt %d)", attempt + 1, exc_info=True)

    return None
