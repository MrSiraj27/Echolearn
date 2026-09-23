import re

# Bare phrase patterns (no anchors) — each is tried at a specific position in the message
# by _PHRASE_RE below, not matched against the whole string. Longer/more-specific
# alternatives are listed before their shorter substrings (e.g. "thanks a lot" before
# "thanks") so the alternation prefers the longer match.
_GREETING = r"(?:hi|hello|hey|hiya|yo|sup|good\s?(?:morning|afternoon|evening)|greetings)(?:\s?there)?"
_THANKS = (
    r"(?:thanks\s?a\s?lot|thank\s?you(?:\s(?:so\s?much|very\s?much))?|thanks(?:\s(?:so\s?much|very\s?much))?"
    r"|thx|ty|much\s?appreciated|appreciate\s?it|cheers)"
)
_FAREWELL = r"(?:bye|goodbye|see\s?ya|see\s?you|later|take\s?care|good\s?night)"
_ACK_WORD = r"(?:got\s?it|sounds\s?good|okay|ok|k|cool|nice|great|good|perfect|awesome|alright)"
_HOW_ARE_YOU = r"(?:how'?s\s?it\s?going|how\s?are\s?you|how\s?are\s?things|what'?s\s?up)"

_PHRASE_RE = re.compile(
    rf"(?P<greeting>{_GREETING})\b"
    rf"|(?P<thanks>{_THANKS})\b"
    rf"|(?P<farewell>{_FAREWELL})\b"
    rf"|(?P<how_are_you>{_HOW_ARE_YOU})\b"
    rf"|(?P<ack>{_ACK_WORD})\b",
    re.IGNORECASE,
)
# Between two phrases: whitespace/punctuation, an optional "and", or both — e.g. the gap
# in "hi, thanks", "hey thanks a lot" (just a space) and "hi and thanks" all qualify.
_SEPARATOR_RE = re.compile(r"(?:[\s,;.!?]+(?:and\s+)?|and\s+)", re.IGNORECASE)

GREETING_REPLY = "Hi! Ask me anything about your uploaded document(s) — I'll answer using only what's in them."
THANKS_REPLY = "You're welcome! Let me know if there's anything else you'd like to know about your document(s)."
FAREWELL_REPLY = "Take care! Come back anytime you have more questions about your documents."
ACK_REPLY = "Got it — anything else you'd like to ask about your document(s)?"
HOW_ARE_YOU_REPLY = (
    "I'm doing well, thanks for asking! Ready whenever you want to ask something about your document(s)."
)

_SINGLE_CATEGORY_REPLY = {
    "greeting": GREETING_REPLY,
    "thanks": THANKS_REPLY,
    "farewell": FAREWELL_REPLY,
    "how_are_you": HOW_ARE_YOU_REPLY,
    "ack": ACK_REPLY,
}

# Opening fragment for a combo reply, one per category present (deduped, in the order
# each first appeared). "farewell" has no opening fragment — it instead picks which
# ENDING is used (see _combo_reply): "bye" reads oddly stitched mid-sentence but natural
# as a closer.
_COMBO_OPENING = {
    "greeting": "Hi!",
    "how_are_you": "I'm doing well, thanks for asking!",
    "thanks": "You're welcome!",
    "ack": "Got it!",
}
_STANDARD_ENDING = "Ask me anything about your uploaded document(s) — I'll answer using only what's in them."
_FAREWELL_ENDING = "Take care! Come back anytime you have more questions about your documents."


def _combo_reply(categories: list[str]) -> str:
    openings = [_COMBO_OPENING[c] for c in categories if c in _COMBO_OPENING]
    ending = _FAREWELL_ENDING if "farewell" in categories else _STANDARD_ENDING
    if not openings:
        return ending
    return " ".join(openings) + " " + ending


def detect_smalltalk_reply(message: str) -> str | None:
    """Return a canned reply for pure small talk — including combinations like "hi,
    thanks!", "hey thanks a lot" or "hello there, how are you? thanks" — or None if this
    looks like a real question.

    Parses the message as a sequence of known phrases separated by punctuation/"and"/
    whitespace: greedily matches one phrase, then a separator, then the next phrase, and
    so on until the string is fully consumed. If any token in that sequence isn't one of
    the known phrases (or a separator is missing between two phrases, e.g. "history" isn't
    "hi" + "story"), the whole message is treated as a real question instead.

    Kept as fast, zero-latency regex matching rather than an LLM call — greetings and
    thanks are common enough in a chat UI that it's worth skipping retrieval entirely,
    and canned replies keep the tone consistently on-brand.
    """
    text = message.strip()
    if not text:
        return None

    pos = 0
    length = len(text)
    categories: list[str] = []
    first = True

    while pos < length:
        if not first:
            sep = _SEPARATOR_RE.match(text, pos)
            if not sep or sep.end() == pos:
                return None
            pos = sep.end()
            if pos >= length:
                break
        m = _PHRASE_RE.match(text, pos)
        if not m:
            return None
        category = m.lastgroup
        if category not in categories:
            categories.append(category)
        pos = m.end()
        first = False

    if not categories:
        return None
    if len(categories) == 1:
        return _SINGLE_CATEGORY_REPLY[categories[0]]
    return _combo_reply(categories)
