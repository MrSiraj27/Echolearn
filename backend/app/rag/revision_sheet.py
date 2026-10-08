"""Revision sheet generation: turn selected documents into a compact, exam-ready cheat sheet.

Pipeline (map-reduce, so long documents never exceed the model's context and free-tier
limits are respected):

  1. gather   - sample chunks spread across ALL selected documents (not top-k for one query),
                plus extra chunks for any focus topics the student typed.
  2. map      - small model extracts candidate items (definitions, formulas, facts, key points,
                processes) from batches of chunks as strict JSON. Every item is tied to the
                chunk it came from and is VERIFIED against that chunk's text (numbers, formulas).
  3. weak     - optional "Watch out" items from the student's own wrong quiz answers and
                hard flashcards (never invented: a student with no history gets none).
  4. reduce   - the main model dedupes, ranks and trims to a page budget. It picks items by
                ID, it does NOT rewrite them, so a fact on the sheet is always verbatim
                extracted-and-verified text and cannot drift in this step.
  5. language - optional Urdu / Roman Urdu / bilingual rendering, with the same script,
                Hindi-vocabulary and number checks as chat explanations.

Accuracy is the top requirement: a wrong formula on a cheat sheet is worse than a missing one,
so anything that cannot be verified against the source text is left out.
"""

import json
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.core.languages import Language
from app.practice.json_utils import extract_json
from app.rag import language_explainer as lang
from app.rag.llm import chat_completion
from app.rag.vectorstore import get_all_chunks, search_multi_document

logger = logging.getLogger(__name__)

# The gpt-oss models are "reasoning" models: at their default effort a large prompt can use
# the whole token budget thinking and come back EMPTY. Low effort is plenty for extraction,
# ranking and translation, and is much faster.
LOW_EFFORT = {"reasoning_effort": "low"}
MAP_WORKERS = 3  # extraction batches are independent, so run a few at once

MAP_MODEL = "openai/gpt-oss-20b"
REDUCE_MODEL = "openai/gpt-oss-120b"

# How many items fit a page (compact, two-column A4) - see the PDF layout in app/revision/pdf.py.
PAGE_ITEM_BUDGET = {1: 22, 2: 48}
MAX_SOURCE_CHUNKS = {1: 30, 2: 48}
MAP_BATCH_CHUNKS = 6
CHUNK_CHARS = 1100
MAX_WEAK_ITEMS = {1: 5, 2: 9}
SELF_CHECK_QUESTIONS = 4
MIN_ITEMS_BEFORE_SHORT_WARNING = 8
TRANSLATE_BATCH_LINES = 18

# Section order on the sheet, and the item "kind" each holds.
SECTION_ORDER = ["definitions", "formulas", "key_points", "facts", "process", "watch_out"]
KIND_TO_SECTION = {
    "definition": "definitions",
    "formula": "formulas",
    "key_point": "key_points",
    "fact": "facts",
    "process": "process",
    "watch_out": "watch_out",
}

SECTION_HEADINGS = {
    "en": {
        "definitions": "Definitions",
        "formulas": "Formulas",
        "key_points": "Key points",
        "facts": "Facts & dates",
        "process": "Processes",
        "watch_out": "Watch out",
        "self_check": "Self-check",
        "answers": "Answers",
    },
    "ur": {
        "definitions": "تعریفات",
        "formulas": "فارمولے",
        "key_points": "اہم نکات",
        "facts": "حقائق اور تاریخیں",
        "process": "مراحل",
        "watch_out": "خیال رکھیں",
        "self_check": "خود جانچ",
        "answers": "جوابات",
    },
    "roman_ur": {
        "definitions": "Taareefaat",
        "formulas": "Formule",
        "key_points": "Aham nukaat",
        "facts": "Haqaaiq aur taareekhein",
        "process": "Marahil",
        "watch_out": "Khayal rakhein",
        "self_check": "Khud jaanch",
        "answers": "Jawabaat",
    },
}


class RevisionSheetError(Exception):
    """A failure with a message that is safe to show the student."""


@dataclass
class SheetResult:
    content: dict
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ small helpers


def _fmt_time(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _numbers(text: str) -> set[str]:
    return lang._numbers_in(text)


def _norm(text: str) -> str:
    """Lower-case, no whitespace, common maths symbols unified - for comparing formulas."""
    text = text.lower().replace("×", "*").replace("·", "*").replace("−", "-").replace("÷", "/")
    return re.sub(r"\s+", "", text)


def _formula_supported(expression: str, source_text: str) -> bool:
    """Is this formula really in the source? Exact (whitespace-insensitive) match, or at
    least 80% of its symbols/words present in the source - tolerant of F=ma vs F = m × a,
    but not of an invented formula."""
    expr, src = _norm(expression), _norm(source_text)
    if not expr:
        return False
    if expr in src:
        return True
    tokens = re.findall(r"[a-z]+|\d+(?:\.\d+)?", expression.lower())
    if not tokens:
        return False
    src_tokens = set(re.findall(r"[a-z]+|\d+(?:\.\d+)?", source_text.lower()))
    return sum(t in src_tokens for t in tokens) / len(tokens) >= 0.8


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


# ------------------------------------------------------------------ 1. gather


@dataclass
class SourceChunk:
    id: str
    text: str
    ref: str  # shown on the sheet, e.g. "p.12", "14:32" or "D2 p.12"
    doc_id: str
    filename: str
    page: int | None
    time: float | None
    priority: bool = False


def _sample_evenly(chunks: list[dict], count: int) -> list[dict]:
    if len(chunks) <= count:
        return chunks
    ordered = sorted(chunks, key=lambda c: (c["metadata"].get("page_number") or 0, c["metadata"].get("start_time_seconds") or 0))
    step = len(ordered) / count
    return [ordered[int(i * step)] for i in range(count)]


def gather_material(
    user_id: uuid.UUID,
    document_ids: list[uuid.UUID],
    doc_tags: dict[str, str],
    topics: list[str],
    page_target: int,
) -> list[SourceChunk]:
    """Chunks spread across every selected document (equal share each), with chunks for
    the student's focus topics first. Page/slide/timestamp is kept for every chunk."""
    limit = MAX_SOURCE_CHUNKS[page_target]
    multi = len(document_ids) > 1

    def to_source(chunk: dict, priority: bool) -> SourceChunk | None:
        meta = chunk["metadata"]
        text = _clean(chunk["text"])
        if len(text) < 40:
            return None
        doc_id = str(meta.get("document_id"))
        page = meta.get("page_number")
        t = meta.get("start_time_seconds")
        base = _fmt_time(t) if t is not None else (f"p.{page}" if page is not None else "")
        if not base:
            return None
        tag = doc_tags.get(doc_id, "")
        ref = f"{tag} {base}".strip() if multi and tag else base
        return SourceChunk(
            id="", text=text[:CHUNK_CHARS], ref=ref, doc_id=doc_id, filename=meta.get("filename") or "",
            page=page, time=t, priority=priority,
        )

    selected: list[SourceChunk] = []
    seen: set[tuple[str, str]] = set()

    def add(chunk: dict, priority: bool) -> None:
        source = to_source(chunk, priority)
        if not source:
            return
        key = (source.doc_id, source.text[:80])
        if key in seen:
            return
        seen.add(key)
        selected.append(source)

    # Focus topics first: retrieval per topic across all selected documents.
    for topic in topics:
        try:
            for chunk in search_multi_document(topic, user_id, document_ids, top_k=4, per_doc_k=2):
                add(chunk, True)
        except Exception:
            logger.warning("Topic retrieval failed for %r", topic, exc_info=True)

    # Then an even spread: each document gets an equal share of what's left.
    remaining = max(limit - len(selected), 0)
    per_doc = max(remaining // max(len(document_ids), 1), 1)
    for doc_id in document_ids:
        try:
            chunks = get_all_chunks(doc_id)
        except Exception:
            logger.warning("Could not read chunks for document %s", doc_id, exc_info=True)
            continue
        for chunk in _sample_evenly(chunks, per_doc):
            add(chunk, False)

    if not selected:
        raise RevisionSheetError("We couldn't read any text from the selected documents.")

    selected = selected[: max(limit, len(topics) * 8)]
    for i, chunk in enumerate(selected, start=1):
        chunk.id = f"c{i}"
    return selected


# ------------------------------------------------------------------ 2. map

MAP_PROMPT = """You are extracting exam-revision material from document excerpts.

Excerpts, each tagged with an id:

{excerpts}

Extract ONLY what is explicitly stated in the excerpts. Use no outside knowledge. Keep every item short (a definition is at most 25 words). Copy formulas, numbers and dates exactly as written. Skip anything that is not worth revising.

Return ONLY valid JSON in exactly this shape (empty lists are fine):
{{"definitions": [{{"term": "...", "definition": "...", "chunk": "c1"}}],
"formulas": [{{"name": "...", "expression": "...", "when_to_use": "...", "chunk": "c1"}}],
"facts_dates": [{{"fact": "...", "chunk": "c1"}}],
"key_points": [{{"topic": "...", "point": "...", "chunk": "c1"}}],
"processes": [{{"name": "...", "steps": ["...", "..."], "chunk": "c1"}}]}}
"chunk" must be the id of the excerpt the item came from."""


def _map_batch(batch: list[SourceChunk], user_id: uuid.UUID) -> dict | None:
    excerpts = "\n\n".join(f"[{c.id}]\n{c.text}" for c in batch)
    prompt = MAP_PROMPT.format(excerpts=excerpts)
    for _ in range(2):  # retry once on malformed JSON, per the spec
        try:
            raw = chat_completion(
                [{"role": "user", "content": prompt}],
                model=MAP_MODEL, temperature=0.1, purpose="revision_sheet", user_id=user_id, groq_extra=LOW_EFFORT,
            )
        except Exception:
            logger.warning("Revision map call failed", exc_info=True)
            continue
        data = extract_json(raw)
        if data is not None:
            return data
    return None


def _as_items(data: dict, chunks_by_id: dict[str, SourceChunk]) -> list[dict]:
    """Normalise one batch's JSON into verified item dicts. Anything malformed, without a
    valid source chunk, or not supported by that chunk's text is dropped."""
    items: list[dict] = []

    def source_for(entry: dict) -> SourceChunk | None:
        return chunks_by_id.get(str(entry.get("chunk", "")).strip())

    def numbers_ok(text: str, chunk: SourceChunk) -> bool:
        return _numbers(text) <= _numbers(chunk.text)

    def base(kind: str, chunk: SourceChunk) -> dict:
        return {
            "kind": kind, "ref": chunk.ref, "doc_id": chunk.doc_id, "page": chunk.page, "t": chunk.time,
            "priority": chunk.priority, "weak": False, "chunk_id": chunk.id,
        }

    for entry in data.get("definitions") or []:
        chunk = source_for(entry) if isinstance(entry, dict) else None
        term, definition = _clean(entry.get("term")) if chunk else "", _clean(entry.get("definition")) if chunk else ""
        if chunk and term and definition and numbers_ok(definition, chunk):
            items.append({**base("definition", chunk), "term": term, "definition": definition})

    for entry in data.get("formulas") or []:
        chunk = source_for(entry) if isinstance(entry, dict) else None
        if not chunk:
            continue
        name, expression = _clean(entry.get("name")), _clean(entry.get("expression"))
        when = _clean(entry.get("when_to_use"))
        # A formula must really be in the source - this is the check that matters most.
        if expression and _formula_supported(expression, chunk.text) and numbers_ok(f"{expression} {when}", chunk):
            items.append({**base("formula", chunk), "name": name or "Formula", "expression": expression, "when_to_use": when})

    for entry in data.get("facts_dates") or []:
        chunk = source_for(entry) if isinstance(entry, dict) else None
        fact = _clean(entry.get("fact")) if chunk else ""
        if chunk and fact and numbers_ok(fact, chunk):
            items.append({**base("fact", chunk), "fact": fact})

    for entry in data.get("key_points") or []:
        chunk = source_for(entry) if isinstance(entry, dict) else None
        point = _clean(entry.get("point")) if chunk else ""
        if chunk and point and numbers_ok(point, chunk):
            items.append({**base("key_point", chunk), "topic": _clean(entry.get("topic")), "point": point})

    for entry in data.get("processes") or []:
        chunk = source_for(entry) if isinstance(entry, dict) else None
        steps = [_clean(s) for s in (entry.get("steps") or [])] if chunk and isinstance(entry.get("steps"), list) else []
        steps = [s for s in steps if s]
        if chunk and len(steps) >= 2 and numbers_ok(" ".join(steps), chunk):
            items.append({**base("process", chunk), "name": _clean(entry.get("name")) or "Process", "steps": steps[:8]})

    return items


def extract_items(chunks: list[SourceChunk], user_id: uuid.UUID, warnings: list[str]) -> list[dict]:
    by_id = {c.id: c for c in chunks}
    items: list[dict] = []
    skipped = 0
    batches = [chunks[start : start + MAP_BATCH_CHUNKS] for start in range(0, len(chunks), MAP_BATCH_CHUNKS)]
    with ThreadPoolExecutor(max_workers=MAP_WORKERS) as pool:
        results = list(pool.map(lambda batch: _map_batch(batch, user_id), batches))
    for batch, data in zip(batches, results):
        if data is None:
            skipped += 1  # skip a bad batch rather than fail the whole sheet
            continue
        items.extend(_as_items(data, {c.id: c for c in batch}))
    if skipped:
        warnings.append(f"{skipped} part(s) of your material couldn't be read, so the sheet may miss some topics.")
    return _dedupe(items)


def _item_key(item: dict) -> str:
    text = item.get("term") or item.get("name") or item.get("fact") or item.get("point") or item.get("topic") or ""
    return f"{item['kind']}:{re.sub(r'[^a-z0-9]+', '', text.lower())[:60]}"


def _dedupe(items: list[dict]) -> list[dict]:
    """Drop repeats of the same term/fact, keeping the first (priority items sort first)."""
    seen: set[str] = set()
    out = []
    for item in sorted(items, key=lambda i: not i["priority"]):
        key = _item_key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


# ------------------------------------------------------------------ 3. weak spots


def collect_weak_spots(db, user, document_ids: list[uuid.UUID], doc_tags: dict[str, str], limit: int) -> list[dict]:
    """The student's real trouble spots: quiz answers they got wrong and flashcards the
    spaced-repetition scheduler marked hard (ease factor pushed down by 'forgot' ratings).

    Each item comes from material that is already tied to a document page, and keeps that
    page as its source. A brand-new student has no history and so gets no items - nothing is
    ever invented. Unanswered chat questions are document gaps, not weak spots, and are NOT used."""
    from app.models import Quiz, QuizAttempt, ReviewCard, ReviewCardState
    from app.quizzes.routes import _grade_answer

    wanted = {str(d) for d in document_ids}
    multi = len(document_ids) > 1
    items: list[dict] = []

    def ref_for(doc_id: str, page) -> str | None:
        if page is None:
            return None
        base = f"p.{page}"
        tag = doc_tags.get(doc_id, "")
        return f"{tag} {base}".strip() if multi and tag else base

    def add(point: str, doc_id: str, page) -> None:
        ref = ref_for(doc_id, page)
        point = _clean(point)
        if ref and point:
            items.append({
                "kind": "watch_out", "point": point[:260], "ref": ref, "doc_id": doc_id, "page": page,
                "t": None, "priority": False, "weak": True, "chunk_id": None,
            })

    # 1) Hard flashcards (lowest ease first).
    cards = (
        db.query(ReviewCard, ReviewCardState)
        .join(ReviewCardState, ReviewCardState.review_card_id == ReviewCard.id)
        .filter(
            ReviewCard.user_id == user.id,
            ReviewCard.document_id.in_([uuid.UUID(d) for d in wanted]),
            ReviewCardState.last_reviewed_at.isnot(None),
            ReviewCardState.ease_factor < 2.3,
        )
        .order_by(ReviewCardState.ease_factor.asc())
        .limit(limit * 2)
        .all()
    )
    for card, _state in cards:
        page = None
        if card.source_chunk_id and card.source_chunk_id.startswith("page:"):
            digits = re.sub(r"\D", "", card.source_chunk_id.split(":", 1)[1])
            page = int(digits) if digits else None
        add(f"{card.question} - {card.answer}", str(card.document_id), page)

    # 2) Quiz questions answered wrongly in recent attempts.
    attempts = (
        db.query(QuizAttempt).filter(QuizAttempt.user_id == user.id).order_by(QuizAttempt.taken_at.desc()).limit(30).all()
    )
    for attempt in attempts:
        quiz = db.query(Quiz).filter(Quiz.id == attempt.quiz_id).first()
        if not quiz or not wanted.intersection({str(d) for d in quiz.document_ids or []}):
            continue
        answers = attempt.answers if isinstance(attempt.answers, dict) else {}
        for question in quiz.questions or []:
            submitted = answers.get(question.get("id"))
            if submitted is None or _grade_answer(question, submitted):
                continue
            doc_id = next((d for d in (str(x) for x in quiz.document_ids) if d in wanted), None)
            add(f"{question.get('question', '')} - {question.get('correct_answer', '')}", doc_id or "", question.get("source_page"))

    seen: set[str] = set()
    unique = []
    for item in items:
        key = re.sub(r"[^a-z0-9]+", "", item["point"].lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:limit]


# ------------------------------------------------------------------ 4. reduce

REDUCE_PROMPT = """You are building a compact exam cheat sheet for a student.

Below are candidate items extracted from their study material, as JSON. Each has an "id".

{items}

Choose and order the best {budget} items at most:
- Remove duplicates and near-duplicates (keep the clearest one).
- Rank by importance: items with "priority": true first, then the most central, most examinable concepts.
- Prefer a balanced mix of definitions, formulas, key points, facts and processes.
Group the chosen items into sections. Refer to items ONLY by their id. Do NOT rewrite, add or change any item.

Also write {num_questions} short self-check recall questions for the student, each answerable from one chosen item (give that item's id in "item"). The question and answer must use only facts from that item.

Return ONLY valid JSON in exactly this shape:
{{"sections": [{{"type": "definitions|formulas|key_points|facts|process", "items": ["i1", "i2"]}}],
"self_check": [{{"question": "...", "answer": "...", "item": "i1"}}]}}"""


def _item_text(item: dict) -> str:
    kind = item["kind"]
    if kind == "definition":
        return f"{item['term']} {item['definition']}"
    if kind == "formula":
        return f"{item['name']} {item['expression']} {item.get('when_to_use', '')}"
    if kind == "fact":
        return item["fact"]
    if kind == "key_point":
        return f"{item.get('topic', '')} {item['point']}"
    if kind == "process":
        return f"{item['name']} {' '.join(item['steps'])}"
    return item["point"]


def _llm_view(item: dict) -> dict:
    keep = {k: v for k, v in item.items() if k in ("id", "kind", "term", "definition", "name", "expression", "when_to_use", "fact", "topic", "point", "steps")}
    if item["priority"]:
        keep["priority"] = True
    return keep


def _fallback_order(items: list[dict]) -> list[dict]:
    """Deterministic ranking used when the reduce model fails: priority first, then a
    round-robin across kinds so no single kind swamps the page."""
    by_kind: dict[str, list[dict]] = {}
    for item in sorted(items, key=lambda i: not i["priority"]):
        by_kind.setdefault(item["kind"], []).append(item)
    ordered: list[dict] = []
    while any(by_kind.values()):
        for kind in list(by_kind):
            if by_kind[kind]:
                ordered.append(by_kind[kind].pop(0))
    return ordered


def reduce_items(items: list[dict], budget: int, user_id: uuid.UUID, warnings: list[str]) -> tuple[list[dict], list[dict]]:
    """Returns (ranked items, self_check questions). Items are chosen by id only."""
    for i, item in enumerate(items, start=1):
        item["id"] = f"i{i}"
    by_id = {item["id"]: item for item in items}

    ranked: list[dict] | None = None
    self_check: list[dict] = []
    prompt = REDUCE_PROMPT.format(
        items=json.dumps([_llm_view(i) for i in items], ensure_ascii=False),
        budget=budget, num_questions=SELF_CHECK_QUESTIONS,
    )
    for _ in range(2):
        try:
            raw = chat_completion(
                [{"role": "user", "content": prompt}],
                model=REDUCE_MODEL, temperature=0.2, purpose="revision_sheet", user_id=user_id, groq_extra=LOW_EFFORT,
            )
        except Exception:
            logger.warning("Revision reduce call failed", exc_info=True)
            continue
        data = extract_json(raw)
        if not data or not isinstance(data.get("sections"), list):
            continue
        chosen: list[dict] = []
        seen: set[str] = set()
        for section in data["sections"]:
            for item_id in (section.get("items") or []) if isinstance(section, dict) else []:
                item = by_id.get(str(item_id))
                if item and item["id"] not in seen:
                    seen.add(item["id"])
                    chosen.append(item)
        if chosen:
            ranked = chosen
            self_check = _validate_self_check(data.get("self_check"), by_id)
            break

    if ranked is None:
        warnings.append("The summary step was unavailable, so items were ordered automatically.")
        ranked = _fallback_order(items)
    return ranked[:budget], self_check


def _validate_self_check(raw, by_id: dict[str, dict]) -> list[dict]:
    """Keep only questions tied to a real item whose numbers match that item - the question
    and answer are new LLM text, so they get the same no-invented-numbers check."""
    out = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        item = by_id.get(str(entry.get("item", "")))
        question, answer = _clean(entry.get("question")), _clean(entry.get("answer"))
        if not item or not question or not answer:
            continue
        if not _numbers(f"{question} {answer}") <= _numbers(_item_text(item)):
            continue
        out.append({"question": question, "answer": answer, "ref": item["ref"]})
    return out[:SELF_CHECK_QUESTIONS]


def _fallback_self_check(items: list[dict]) -> list[dict]:
    out = []
    for item in items:
        if item["kind"] == "definition":
            out.append({"question": f"What is {item['term']}?", "answer": item["definition"], "ref": item["ref"]})
        elif item["kind"] == "formula" and item.get("when_to_use"):
            out.append({"question": f"When do you use {item['name']}?", "answer": item["when_to_use"], "ref": item["ref"]})
        if len(out) >= SELF_CHECK_QUESTIONS:
            break
    return out


# ------------------------------------------------------------------ 5. language


def _main_text(item: dict) -> str:
    """The one sentence-like field of an item (used for the bilingual gloss line)."""
    kind = item["kind"]
    if kind == "definition":
        return item["definition"]
    if kind == "formula":
        return item.get("when_to_use") or item["name"]
    if kind == "fact":
        return item["fact"]
    if kind == "key_point":
        return item["point"]
    if kind == "process":
        return "; ".join(item["steps"])
    return item["point"]


TRANSLATE_PROMPT = """You will translate numbered lines of a student's revision sheet.

Input is a JSON object mapping an id to an English line. Translate each line. Return ONLY a JSON object with the SAME ids mapping to the translated lines. Do not merge, split, add or drop lines. Numbers, dates, formulas, symbols and units must stay exactly as in the English line."""


def _line_problem(language: Language, english: str, translated: str) -> str | None:
    script = lang._script_problem(language, translated)
    if script:
        return script
    new_numbers = _numbers(translated) - _numbers(english)
    if new_numbers:
        return f"numbers not in the original: {', '.join(sorted(new_numbers))}"
    return None


def translate_lines(lines: dict[str, str], language: Language, user_id: uuid.UUID, warnings: list[str]) -> dict[str, str]:
    """Translate lines into Urdu/Roman Urdu with the same rules and checks as chat
    explanations. A line that still fails after a retry stays in English rather than risk a
    wrong rendering."""
    system = lang.SYSTEM_PROMPT.format(
        language=lang.LANGUAGE_LABELS[language],
        script_rules=lang.URDU_SCRIPT_RULES if language == Language.ur else lang.ROMAN_URDU_SCRIPT_RULES,
    )
    system = system.replace("Rewrite the ANSWER below in", "Translate the numbered lines into") + "\n\n" + TRANSLATE_PROMPT

    def call(batch: dict[str, str], extra: str = "") -> dict[str, str]:
        try:
            raw = chat_completion(
                [{"role": "system", "content": system + extra}, {"role": "user", "content": json.dumps(batch, ensure_ascii=False)}],
                model=lang.EXPLAIN_MODEL, temperature=0.2, purpose="revision_sheet", user_id=user_id, groq_extra=LOW_EFFORT,
            )
        except Exception:
            logger.warning("Revision translate call failed", exc_info=True)
            return {}
        data = extract_json(raw) or {}
        return {k: _clean(v) for k, v in data.items() if k in batch and isinstance(v, str)}

    result: dict[str, str] = {}
    keys = list(lines)
    for start in range(0, len(keys), TRANSLATE_BATCH_LINES):
        batch = {k: lines[k] for k in keys[start : start + TRANSLATE_BATCH_LINES]}
        translated = call(batch)
        bad: dict[str, str] = {}
        problems: list[str] = []
        for key, english in batch.items():
            text = translated.get(key)
            problem = _line_problem(language, english, text) if text else "missing"
            if problem:
                bad[key] = english
                problems.append(problem)
            else:
                result[key] = text
        if bad:  # one retry for just the failing lines, with the problems spelled out
            retry = call(bad, f"\nA previous attempt was rejected: {'; '.join(sorted(set(problems))[:5])}. Fix this.")
            for key, english in bad.items():
                text = retry.get(key)
                if text and not _line_problem(language, english, text):
                    result[key] = text

    missing = [k for k in lines if k not in result]
    if missing:
        warnings.append(f"{len(missing)} line(s) are shown in English because a safe translation wasn't available.")
    return {k: result.get(k, lines[k]) for k in lines}


def apply_language(sheet: dict, language: str, user_id: uuid.UUID, warnings: list[str]) -> None:
    """Render the sheet in `language` ("en" | "ur" | "roman_ur" | "bilingual") in place."""
    headings = SECTION_HEADINGS["ur" if language in ("ur", "bilingual") else language if language != "en" else "en"]
    if language == "en":
        sheet["labels"] = SECTION_HEADINGS["en"]
        return

    items = [item for section in sheet["sections"] for item in section["items"]]

    if language == "bilingual":
        lines = {item["id"]: _main_text(item) for item in items}
        for item_id, text in translate_lines(lines, Language.ur, user_id, warnings).items():
            item = next(i for i in items if i["id"] == item_id)
            if text != lines[item_id]:
                item["gloss"] = text
        sheet["labels"] = SECTION_HEADINGS["en"]
        sheet["labels_ur"] = headings
        return

    target = Language.ur if language == "ur" else Language.roman_ur
    # Terms, names and topics deliberately stay in English (technical terms are kept in
    # English, as in chat explanations); only the descriptive sentences are translated.
    lines: dict[str, str] = {}
    for item in items:
        i = item["id"]
        kind = item["kind"]
        if kind == "definition":
            lines[f"{i}.definition"] = item["definition"]
        elif kind == "formula":
            if item.get("when_to_use"):
                lines[f"{i}.when_to_use"] = item["when_to_use"]
        elif kind == "fact":
            lines[f"{i}.fact"] = item["fact"]
        elif kind == "key_point":
            lines[f"{i}.point"] = item["point"]
        elif kind == "process":
            for n, step in enumerate(item["steps"]):
                lines[f"{i}.step{n}"] = step
        else:
            lines[f"{i}.point"] = item["point"]
    for n, q in enumerate(sheet["self_check"]):
        lines[f"q{n}.question"], lines[f"q{n}.answer"] = q["question"], q["answer"]

    translated = translate_lines(lines, target, user_id, warnings)
    for item in items:
        i = item["id"]
        for key in ("definition", "when_to_use", "fact", "point"):
            if f"{i}.{key}" in translated:
                item[key] = translated[f"{i}.{key}"]
        if item["kind"] == "process":
            item["steps"] = [translated.get(f"{i}.step{n}", s) for n, s in enumerate(item["steps"])]
    for n, q in enumerate(sheet["self_check"]):
        q["question"] = translated.get(f"q{n}.question", q["question"])
        q["answer"] = translated.get(f"q{n}.answer", q["answer"])
    sheet["labels"] = SECTION_HEADINGS[language]


# ------------------------------------------------------------------ orchestration


def generate_revision_sheet(
    *,
    db,
    user,
    title: str,
    document_ids: list[uuid.UUID],
    doc_names: dict[str, str],
    topics: list[str],
    language: str,
    page_target: int,
    include_weak_spots: bool,
) -> SheetResult:
    warnings: list[str] = []
    doc_tags = {str(d): f"D{i}" for i, d in enumerate(document_ids, start=1)}

    chunks = gather_material(user.id, document_ids, doc_tags, topics, page_target)
    items = extract_items(chunks, user.id, warnings)

    weak: list[dict] = []
    if include_weak_spots:
        weak = collect_weak_spots(db, user, document_ids, doc_tags, MAX_WEAK_ITEMS[page_target])

    if not items and not weak:
        raise RevisionSheetError(
            "We couldn't find enough revision-worthy content in this material. Try different documents or topics."
        )

    budget = PAGE_ITEM_BUDGET[page_target]
    ranked, self_check = reduce_items(items, max(budget - len(weak), 4), user.id, warnings) if items else ([], [])

    # Weak spots always make the sheet when the student has them; they follow the priority items.
    n_priority = sum(1 for i in ranked if i["priority"])
    for k, w in enumerate(weak):
        w["id"] = f"w{k + 1}"
    final = ranked[:n_priority] + weak + ranked[n_priority:]
    for rank, item in enumerate(final, start=1):
        item["rank"] = rank  # lower = more important; the PDF fitter drops the highest ranks first

    sections: list[dict] = []
    for section_type in SECTION_ORDER:
        group = [i for i in final if KIND_TO_SECTION[i["kind"]] == section_type]
        if group:
            sections.append({"type": section_type, "items": group})

    if not self_check:
        self_check = _fallback_self_check(ranked)

    refs_by_doc: dict[str, set[str]] = {}
    for item in final:
        refs_by_doc.setdefault(item["doc_id"], set()).add(item["ref"])
    sources = [
        {"tag": doc_tags.get(d, ""), "document": doc_names.get(d, "Document"), "document_id": d, "refs": sorted(r)}
        for d, r in refs_by_doc.items()
    ]

    sheet = {
        "title": title,
        "subtitle": ", ".join(sorted({doc_names.get(str(d), "Document") for d in document_ids}))[:140],
        "language": language,
        "page_target": page_target,
        "sections": sections,
        "self_check": self_check,
        "sources": sources,
        "topics": topics,
    }

    if len(final) < MIN_ITEMS_BEFORE_SHORT_WARNING:
        warnings.append("Your material was short; this sheet is brief.")

    apply_language(sheet, language, user.id, warnings)
    sheet["warnings"] = warnings
    return SheetResult(content=sheet, warnings=warnings)
