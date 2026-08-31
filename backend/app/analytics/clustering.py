import json
import logging

from app.rag.llm import chat_completion

logger = logging.getLogger(__name__)

CLUSTER_MODEL = "openai/gpt-oss-20b"

CLUSTER_PROMPT = """Group these unanswered user questions into 3-5 short, clearly labeled \
themes (a theme is a short label under 8 words describing what the questions have in \
common, e.g. "Pricing details" or "Refund policy"). Every question should belong to \
exactly one theme.

Questions:
{questions}

Return ONLY a JSON array like this, no explanation, no markdown fences:
[{{"theme": "Pricing details", "question_indices": [1, 4, 7]}}]"""


def cluster_unanswered_questions(questions: list[str]) -> list[dict] | None:
    """Group raw unanswered questions into a handful of labeled themes via one LLM call.
    Returns None (caller should fall back to plain frequency grouping) on any failure."""
    if not questions:
        return None

    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    prompt = CLUSTER_PROMPT.format(questions=numbered)

    try:
        raw = chat_completion([{"role": "user", "content": prompt}], model=CLUSTER_MODEL, temperature=0.2, purpose="knowledge_gap_clustering")
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)

        themes: list[dict] = []
        for item in parsed:
            indices = item.get("question_indices", [])
            examples = [questions[i - 1] for i in indices if isinstance(i, int) and 1 <= i <= len(questions)]
            if not examples:
                continue
            themes.append(
                {
                    "theme": str(item.get("theme", "Other"))[:80],
                    "count": len(examples),
                    "example_questions": examples[:5],
                }
            )

        themes.sort(key=lambda t: t["count"], reverse=True)
        return themes or None
    except Exception:
        logger.warning("Knowledge-gap clustering failed, falling back to frequency grouping", exc_info=True)
        return None
