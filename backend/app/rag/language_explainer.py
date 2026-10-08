"""Explain an existing assistant answer in Urdu or Roman Urdu.

This is deliberately a separate step that runs on top of the normal grounded English
answer (see app/rag/langgraph_pipeline.py) instead of changing it: retrieval quality is
untouched, and the extra step can be cached and quota-limited on its own.

Accuracy matters more than fluency here, so every result is checked for facts that were
not in the original answer (see `_find_new_facts`) and flagged to the user if any remain.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass

from app.core.languages import LANGUAGE_LABELS, ExplainMode, Language
from app.models import Message
from app.rag.llm import chat_completion

logger = logging.getLogger(__name__)

EXPLAIN_MODEL = "openai/gpt-oss-120b"
CHECK_MODEL = "openai/gpt-oss-20b"

# Answers shorter than this are cheap to eyeball, so we skip the extra fidelity LLM call.
FIDELITY_CHECK_MIN_WORDS = 40
# How many times to regenerate when the result has problems (script or invented facts).
MAX_RETRIES = 2
# Cap on how much source text goes into the prompt (the answer already summarises it).
MAX_CONTEXT_CHARS_PER_SOURCE = 1200
MAX_CONTEXT_CHARS_TOTAL = 6000

SYSTEM_PROMPT = """You are EchoLearn's language assistant. Rewrite the ANSWER below in {language}.

{script_rules}

Rules for ALL languages:
- Use ONLY facts present in the ANSWER and the SOURCE CONTEXT. Do not add new facts, examples, numbers or dates.
- Keep technical terms, formulas, symbols, code, units and proper nouns in English. The first time a term appears you may add a short gloss in brackets. Add a gloss only when it genuinely helps, and never repeat the same word in the brackets.
- Keep the same structure: lists stay lists, headings stay headings, bold stays bold.
- Use simple, natural, conversational Urdu a university student would use, not formal literary Urdu.
- If the ANSWER says the information was not found in the document, say that in the target language and add nothing else.
- Output only the rewritten answer, with no preface or commentary."""

URDU_SCRIPT_RULES = """Write every sentence in Urdu SCRIPT (right-to-left Urdu letters). Do NOT write Urdu in Latin letters.
Only technical terms, formulas, units and names stay in English letters. Glosses go in Urdu script.
Example: Photosynthesis (روشنی سے خوراک بنانے کا عمل) پودوں کے سبز حصوں میں ہوتا ہے۔"""

ROMAN_URDU_SCRIPT_RULES = """Write every sentence in ROMAN Urdu: Urdu words spelled with Latin letters (e.g. 'hai', 'ka', 'ke liye', 'mein', 'kehte hain'). Do NOT leave sentences in English, and do NOT use any Urdu/Arabic-script letters anywhere, including glosses.
Only technical terms, formulas, units and names stay in English. Glosses, if any, go in Roman Urdu.
Use common everyday spelling and stay consistent.
Example: Photosynthesis (roshni se khuraak banane ka amal) paudon ke sabz hisson mein hota hai."""

SIMPLIFY_ADDENDUM = """
- Explain it more simply than the original, as if to a student meeting the topic for the first time. You may add ONE short analogy, but it must be clearly labelled as an analogy and must not introduce any new facts about the topic."""

STRICT_RETRY_ADDENDUM = """
IMPORTANT: a previous attempt was rejected for these problems: {issues}. Fix them. Every number, date, formula and name in your output must appear in the ANSWER, and the output must follow the script rules above exactly."""

CHECK_PROMPT = """ORIGINAL ANSWER:
{original}

TRANSLATION:
{translation}

List any numbers, dates, formulas or named entities that appear in the TRANSLATION but NOT in the ORIGINAL ANSWER. Ignore differences in script or spelling (e.g. Urdu digits vs Latin digits, transliterated names). Return ONLY a JSON list of short strings, or [] if there are none."""

# Urdu / Arabic-Indic digits -> ASCII, so "۱۲" and "12" count as the same number.
_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")


@dataclass
class ExplainResult:
    text: str
    language: Language
    mode: ExplainMode
    fidelity_warning: bool = False


# Urdu/Arabic script blocks (basic, supplement, presentation forms A and B).
_ARABIC_SCRIPT_RE = re.compile("[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_LATIN_LETTER_RE = re.compile("[A-Za-z]")
# At least this share of an Urdu-script answer's letters must be Urdu script. English
# technical terms legitimately stay in Latin letters, so this is deliberately not 100%.
MIN_URDU_SCRIPT_SHARE = 0.5


def _script_problem(language: Language, text: str) -> str | None:
    """None if `text` uses the right script for `language`, else a short description of
    what is wrong (fed back to the model on retry). The model sometimes answers in the
    wrong script, e.g. Roman Urdu when asked for Urdu script."""
    arabic = len(_ARABIC_SCRIPT_RE.findall(text))
    latin = len(_LATIN_LETTER_RE.findall(text))
    if language == Language.ur:
        if arabic + latin and arabic / (arabic + latin) < MIN_URDU_SCRIPT_SHARE:
            return "the answer was not written in Urdu script (use Urdu letters, not Latin letters)"
    elif language == Language.roman_ur:
        if arabic:
            return "the answer contains Urdu/Arabic-script letters (Roman Urdu must use only Latin letters)"
        if latin and len(text.split()) >= 8 and _looks_untranslated_english(text):
            return "the answer is still mostly English (write the sentences in Roman Urdu)"
    return None


# Very common English function words; a Roman Urdu answer should contain few of them.
_ENGLISH_STOPWORDS = frozenset(
    "the is are was were of and to in that this it for with as on by be an or if its from at which "
    "states equals stays measured".split()
)


def _looks_untranslated_english(text: str) -> bool:
    words = re.findall(r"[A-Za-z']+", text.lower())
    if len(words) < 8:
        return False
    return sum(w in _ENGLISH_STOPWORDS for w in words) / len(words) > 0.18


def _numbers_in(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER_RE.findall(text.translate(_DIGIT_TABLE))}


def _source_context(message: Message) -> str:
    """The text of the chunks this answer cited, trimmed. Citations already store the
    chunk text, so nothing needs to be re-fetched from the vector store."""
    parts: list[str] = []
    total = 0
    for citation in message.citations or []:
        chunk = (citation.get("chunk_text") or "").strip()
        if not chunk:
            continue
        chunk = chunk[:MAX_CONTEXT_CHARS_PER_SOURCE]
        if total + len(chunk) > MAX_CONTEXT_CHARS_TOTAL:
            break
        label = citation.get("filename") or "source"
        parts.append(f"[{label}]\n{chunk}")
        total += len(chunk)
    return "\n\n".join(parts)


def _generate(
    message: Message,
    language: Language,
    mode: ExplainMode,
    user_id: uuid.UUID | None,
    issues: list[str] | None = None,
) -> str:
    script_rules = URDU_SCRIPT_RULES if language == Language.ur else ROMAN_URDU_SCRIPT_RULES
    system = SYSTEM_PROMPT.format(language=LANGUAGE_LABELS[language], script_rules=script_rules)
    if mode == ExplainMode.simplify:
        system += SIMPLIFY_ADDENDUM
    if issues:
        system += STRICT_RETRY_ADDENDUM.format(issues=", ".join(issues[:10]))

    context = _source_context(message) or "(no source context available)"
    user = f"ANSWER:\n{message.content}\n\nSOURCE CONTEXT:\n{context}"

    text = chat_completion(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=EXPLAIN_MODEL,
        temperature=0.2,
        purpose="language_explain",
        user_id=user_id,
    )
    return text.strip()


def _parse_string_list(raw: str) -> list[str] | None:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    return [str(item).strip() for item in data if str(item).strip()]


def _find_new_facts(original: str, translation: str, user_id: uuid.UUID | None) -> list[str]:
    """Numbers/dates/formulas/names present in the translation but not the original.

    Two layers: a free, deterministic number comparison (catches the worst failure — an
    invented figure — with no LLM call), then, for answers long enough to be worth it, a
    small LLM pass for dates, formulas and names."""
    issues = sorted(_numbers_in(translation) - _numbers_in(original))

    if len(original.split()) >= FIDELITY_CHECK_MIN_WORDS:
        try:
            raw = chat_completion(
                [
                    {
                        "role": "user",
                        "content": CHECK_PROMPT.format(original=original, translation=translation),
                    }
                ],
                model=CHECK_MODEL,
                temperature=0,
                purpose="language_explain",
                user_id=user_id,
            )
            flagged = _parse_string_list(raw)
            if flagged is None:
                logger.warning("Fidelity check returned unparseable output: %r", raw[:200])
            else:
                issues.extend(item for item in flagged if item not in issues)
        except Exception:
            # The check is a safeguard, not the feature: if it can't run, don't fail the
            # user's explanation over it.
            logger.warning("Fidelity check call failed", exc_info=True)

    return issues


def explain_message(
    message: Message,
    language: Language,
    mode: ExplainMode = ExplainMode.translate,
    user_id: uuid.UUID | None = None,
) -> ExplainResult:
    """Generate (not cache) an Urdu/Roman Urdu rendering of `message`. Raises if the LLM
    call itself fails; a fidelity problem is reported via `fidelity_warning` instead."""
    if language == Language.en:
        raise ValueError("English is the original answer; nothing to explain.")

    text = _generate(message, language, mode, user_id)
    if not text:
        raise RuntimeError("The language model returned an empty explanation.")

    issues = _problems(message, text, language, user_id)
    for attempt in range(MAX_RETRIES):
        if not issues:
            break
        logger.info("Explanation of message %s had problems %s; retry %d", message.id, issues, attempt + 1)
        retry = _generate(message, language, mode, user_id, issues=issues)
        if not retry:
            break
        retry_issues = _problems(message, retry, language, user_id)
        # Keep the retry if it is cleaner than what we had.
        if len(retry_issues) <= len(issues):
            text, issues = retry, retry_issues

    return ExplainResult(text=text, language=language, mode=mode, fidelity_warning=bool(issues))


def _problems(message: Message, text: str, language: Language, user_id: uuid.UUID | None) -> list[str]:
    """Everything wrong with `text`: wrong script, or facts that weren't in the answer."""
    problems: list[str] = []
    script = _script_problem(language, text)
    if script:
        problems.append(script)
    problems.extend(_find_new_facts(message.content, text, user_id))
    return problems
