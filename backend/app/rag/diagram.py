import logging
import re

from app.rag.llm import chat_completion

logger = logging.getLogger(__name__)

DIAGRAM_MODEL = "openai/gpt-oss-120b"

NO_DIAGRAM_SENTINEL = "NO_DIAGRAM_POSSIBLE"

DIAGRAM_PROMPT = """Based ONLY on the context below, generate a Mermaid.js diagram that \
visualizes what the user asked for. Return ONLY valid Mermaid syntax — no explanation, \
no markdown code fences, no extra text before or after. Choose the most appropriate \
diagram type (flowchart, sequenceDiagram, mindmap, or classDiagram) based on the content's \
actual structure. If the context doesn't contain enough structured process/relationship \
information to meaningfully diagram, respond with EXACTLY this and nothing else: \
{sentinel}

CRITICAL syntax rule: if any node/label text contains punctuation — parentheses, colons, \
slashes, ampersands, or commas — wrap that ENTIRE label in double quotes, e.g. \
A["Relevant Documents (Context)"] not A[Relevant Documents (Context)]. Unquoted \
parentheses inside a node label are the single most common cause of a broken diagram.

Context:
{context}

Request: {instruction}"""

_VALID_START_RE = re.compile(
    r"^\s*(flowchart|graph|sequenceDiagram|classDiagram|mindmap|stateDiagram(-v2)?|erDiagram|"
    r"gantt|pie|journey)\b",
    re.IGNORECASE,
)

# Phrases from our own prompt leaking into the model's output — a sign it echoed
# instructions instead of returning pure Mermaid. Kept narrow and prompt-specific
# (e.g. NOT "relevant documents" — that can legitimately be a real diagram label like
# a RAG pipeline's "Relevant Documents (Context)" node) to avoid false positives.
_LEAK_MARKERS = (
    "context:\n",
    "request:",
    "based only on the context",
    "return only valid mermaid",
    "the user asked",
)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"```\s*$", "", text)
    return text.strip()


# Square-bracket node labels containing unescaped punctuation (most commonly
# parentheses) are the single most common cause of a Mermaid parse error — the model
# is told to quote these, but as a safety net, auto-quote any that slip through.
_UNQUOTED_LABEL_RE = re.compile(r'\[(?!")([^\[\]"]*[()][^\[\]"]*)\]')


def _auto_quote_labels(text: str) -> str:
    return _UNQUOTED_LABEL_RE.sub(lambda m: f'["{m.group(1)}"]', text)


def _brackets_balanced(text: str) -> bool:
    """Catches truncated or otherwise structurally broken output (a common failure mode
    when the model's response gets cut off or garbled) — every Mermaid node/edge shape
    uses paired brackets, so an imbalance is a strong signal the syntax is broken."""
    closers = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for ch in text:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack.pop() != closers[ch]:
                return False
    return not stack


def _looks_like_valid_mermaid(text: str) -> bool:
    if not _VALID_START_RE.match(text):
        return False
    lowered = text.lower()
    if any(marker in lowered for marker in _LEAK_MARKERS):
        return False
    if "```" in text:
        return False
    return _brackets_balanced(text)


def generate_diagram(instruction: str, chunks: list[dict]) -> str | None:
    """Generate a Mermaid diagram from retrieved context. Returns the Mermaid source, or
    None if the model determined the content can't be meaningfully diagrammed (or every
    attempt produced malformed output)."""
    context = "\n\n".join(c["text"] for c in chunks)
    prompt = DIAGRAM_PROMPT.format(sentinel=NO_DIAGRAM_SENTINEL, context=context, instruction=instruction)
    retry_prompt = (
        DIAGRAM_PROMPT.format(sentinel=NO_DIAGRAM_SENTINEL, context=context, instruction=instruction)
        + "\n\nIMPORTANT: your previous response was not valid Mermaid syntax — it may have included "
        "explanation, headers, echoed prompt/context text, an unterminated code fence, or unbalanced "
        "brackets (likely from being cut off). Your entire response must be ONLY complete, well-formed "
        "Mermaid syntax: start directly with a diagram type keyword (e.g. 'flowchart TD'), keep it short "
        "enough to finish completely, and make sure every bracket you open is closed. No prose, no "
        "headers, no restating the context or instructions anywhere in the output."
    )

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            raw = chat_completion(
                [{"role": "user", "content": prompt if attempt == 0 else retry_prompt}],
                model=DIAGRAM_MODEL,
                temperature=0.1,
                purpose="diagram_generation",
            )
        except Exception:
            logger.exception("Diagram generation LLM call failed")
            return None

        cleaned = _strip_code_fences(raw)

        if cleaned.strip() == NO_DIAGRAM_SENTINEL or NO_DIAGRAM_SENTINEL in cleaned:
            return None

        cleaned = _auto_quote_labels(cleaned)

        if _looks_like_valid_mermaid(cleaned):
            return cleaned

        logger.warning("Diagram generation attempt %d/%d produced malformed Mermaid, retrying", attempt + 1, max_attempts)

    return None
