import json
import logging

from app.rag.llm import chat_completion

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = "openai/gpt-oss-120b"
CLASSIFY_MODEL = "openai/gpt-oss-20b"

VALID_TEMPLATES = {"stats", "timeline", "comparison", "summary"}

AUTO_TEMPLATE_PROMPT = """Given this document context and request, pick the single best-fitting \
infographic template:
- "stats": the content is full of numbers/metrics/figures worth highlighting
- "timeline": the content describes a chronological sequence of events or stages
- "comparison": the content compares two things (products, options, entities)
- "summary": anything else — a general set of key points

Context:
{context}

Request: {instruction}

Return ONLY one word: stats, timeline, comparison, or summary."""

_SCHEMAS = {
    "stats": {
        "prompt": """Extract data for a STATS infographic ONLY from the context below. Do not invent \
statistics or facts not present in the context.

Context:
{context}

Request: {instruction}

Return ONLY valid JSON (no markdown fences, no explanation) matching exactly this shape:
{{"title": str, "subtitle": str, "stats": [{{"label": str, "value": str, "icon_hint": str}}], "takeaway": str}}
- "stats" must have 3 to 6 items.
- "icon_hint" must be one of: money, users, time, growth, default — pick whichever best fits each stat.
- "value" should be the number/metric itself (e.g. "42%", "$1.2M", "3,000 users").""",
        "required": {"title", "subtitle", "stats", "takeaway"},
        "list_key": "stats",
        "list_item_required": {"label", "value", "icon_hint"},
        "min_items": 3,
        "max_items": 6,
    },
    "timeline": {
        "prompt": """Extract data for a TIMELINE infographic ONLY from the context below. Do not invent \
events or facts not present in the context.

Context:
{context}

Request: {instruction}

Return ONLY valid JSON (no markdown fences, no explanation) matching exactly this shape:
{{"title": str, "events": [{{"date_or_stage": str, "label": str, "description": str}}]}}
- "events" must have 3 to 8 items, in chronological order.
- "description" must be a single short sentence.""",
        "required": {"title", "events"},
        "list_key": "events",
        "list_item_required": {"date_or_stage", "label", "description"},
        "min_items": 3,
        "max_items": 8,
    },
    "comparison": {
        "prompt": """Extract data for a COMPARISON infographic ONLY from the context below. Do not invent \
facts not present in the context.

Context:
{context}

Request: {instruction}

Return ONLY valid JSON (no markdown fences, no explanation) matching exactly this shape:
{{"title": str, "item_a_name": str, "item_b_name": str, \
"rows": [{{"aspect": str, "item_a_value": str, "item_b_value": str}}], "verdict": str}}
- "rows" must have 3 to 6 items.
- "verdict" is a single optional takeaway sentence — use an empty string if there isn't a clear one.""",
        "required": {"title", "item_a_name", "item_b_name", "rows"},
        "list_key": "rows",
        "list_item_required": {"aspect", "item_a_value", "item_b_value"},
        "min_items": 3,
        "max_items": 6,
    },
    "summary": {
        "prompt": """Extract data for a SUMMARY infographic ONLY from the context below. Do not invent \
facts not present in the context.

Context:
{context}

Request: {instruction}

Return ONLY valid JSON (no markdown fences, no explanation) matching exactly this shape:
{{"title": str, "key_points": [{{"heading": str, "detail": str}}], "takeaway": str}}
- "key_points" must have 3 to 5 items.
- "detail" should be short (one sentence).""",
        "required": {"title", "key_points", "takeaway"},
        "list_key": "key_points",
        "list_item_required": {"heading", "detail"},
        "min_items": 3,
        "max_items": 5,
    },
}


def _parse_json(raw: str) -> dict | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip().strip("`").strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None


def _validate(data: dict, schema: dict) -> bool:
    if not isinstance(data, dict):
        return False
    if not schema["required"].issubset(data.keys()):
        return False
    items = data.get(schema["list_key"])
    if not isinstance(items, list) or not (schema["min_items"] <= len(items) <= schema["max_items"] + 2):
        return False
    for item in items:
        if not isinstance(item, dict) or not schema["list_item_required"].issubset(item.keys()):
            return False
    return True


def pick_template(context: str, instruction: str) -> str:
    prompt = AUTO_TEMPLATE_PROMPT.format(context=context[:4000], instruction=instruction or "Summarize this document")
    try:
        raw = chat_completion([{"role": "user", "content": prompt}], model=CLASSIFY_MODEL, temperature=0.0, purpose="infographic_template_pick")
        choice = raw.strip().lower().strip(".")
        if choice in VALID_TEMPLATES:
            return choice
    except Exception:
        logger.warning("Infographic template classification failed, defaulting to summary", exc_info=True)
    return "summary"


def extract_infographic_data(chunks: list[dict], instruction: str, template: str) -> tuple[str, dict] | None:
    """Extract structured data for the given (or auto-picked) infographic template. Returns
    (resolved_template, data) or None if extraction failed validation after a retry."""
    context = "\n\n".join(c["text"] for c in chunks)

    if template == "auto":
        template = pick_template(context, instruction)
    if template not in VALID_TEMPLATES:
        template = "summary"

    schema = _SCHEMAS[template]
    prompt = schema["prompt"].format(context=context, instruction=instruction or "Summarize the key information")

    for attempt in range(2):
        try:
            raw = chat_completion([{"role": "user", "content": prompt}], model=EXTRACTION_MODEL, temperature=0.2, purpose="infographic_extraction")
        except Exception:
            logger.exception("Infographic extraction LLM call failed")
            return None

        data = _parse_json(raw)
        if data and _validate(data, schema):
            # Trim to the max item count in case the model overshoots.
            data[schema["list_key"]] = data[schema["list_key"]][: schema["max_items"]]
            return template, data

        logger.warning("Infographic extraction attempt %d produced invalid JSON/schema, retrying", attempt + 1)
        prompt = (
            schema["prompt"].format(context=context, instruction=instruction or "Summarize the key information")
            + "\n\nIMPORTANT: your previous response was not valid JSON matching the required shape exactly. "
            "Return ONLY the JSON object, nothing else — no markdown fences, no commentary."
        )

    return None
