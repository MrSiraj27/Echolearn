import json
import logging
import uuid

from app.rag.llm import chat_completion
from app.rag.vectorstore import get_all_chunks

logger = logging.getLogger(__name__)

SUMMARY_MODEL = "openai/gpt-oss-120b"
MAX_SAMPLE_CHUNKS = 10

SUMMARY_PROMPT = """Here are excerpts from a document (sampled across its length):

{excerpts}

Summarize this document in 3-5 sentences, then generate exactly 5 example questions a \
reader might ask about it. If the document is very short, generate as many sensible, \
distinct questions as it can support (at least 2-3), rather than inventing repetitive or \
generic ones.

Return ONLY valid JSON in this exact shape, nothing else:
{{"summary": "...", "suggested_questions": ["...", "..."]}}"""


def _sample_chunks(chunks: list[dict], max_count: int) -> list[dict]:
    """Pick chunks spread evenly across the document rather than the first N, so a long
    document's summary isn't skewed toward its opening section."""
    if len(chunks) <= max_count:
        return chunks

    # Sort by page number (falling back to original order) for a stable, sequential sample.
    ordered = sorted(chunks, key=lambda c: (c["metadata"].get("page_number") or 0))
    step = len(ordered) / max_count
    return [ordered[int(i * step)] for i in range(max_count)]


def _parse_summary_response(raw: str) -> dict | None:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None
    summary = data.get("summary")
    questions = data.get("suggested_questions")
    if not isinstance(summary, str) or not isinstance(questions, list):
        return None

    return {
        "summary": summary.strip(),
        "suggested_questions": [str(q).strip() for q in questions if str(q).strip()],
    }


def generate_document_summary(document_id: uuid.UUID) -> dict | None:
    """Returns {"summary": str, "suggested_questions": list[str]} or None if generation
    failed after a retry (caller should leave the document without a summary rather than
    fail the whole embedding pipeline over this)."""
    chunks = get_all_chunks(document_id)
    if not chunks:
        return None

    sample = _sample_chunks(chunks, MAX_SAMPLE_CHUNKS)
    excerpts = "\n\n---\n\n".join(c["text"][:1000] for c in sample)
    prompt = SUMMARY_PROMPT.format(excerpts=excerpts)

    for attempt in range(2):
        try:
            raw = chat_completion([{"role": "user", "content": prompt}], model=SUMMARY_MODEL, temperature=0.3, purpose="summary")
            parsed = _parse_summary_response(raw)
            if parsed:
                return parsed
            logger.warning("Summary response wasn't valid JSON (attempt %d): %r", attempt + 1, raw[:200])
        except Exception:
            logger.warning("Summary generation call failed (attempt %d)", attempt + 1, exc_info=True)

    return None
