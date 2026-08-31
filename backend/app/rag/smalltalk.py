import re

# Matched against the ENTIRE message (after stripping punctuation/whitespace), not a
# substring search — "hi, does this cover onboarding?" should still go to the RAG
# pipeline, not get treated as a bare greeting.
_GREETING_RE = re.compile(
    r"^(hi|hello|hey|hiya|yo|sup|good\s?(morning|afternoon|evening)|greetings)(\s?there)?[!.\s]*$",
    re.IGNORECASE,
)
_THANKS_RE = re.compile(
    r"^(thanks|thank\s?you|thx|ty|thanks\s?a\s?lot|much\s?appreciated|appreciate\s?it|cheers)[!.\s]*$",
    re.IGNORECASE,
)
_FAREWELL_RE = re.compile(
    r"^(bye|goodbye|see\s?ya|see\s?you|later|take\s?care|good\s?night)[!.\s]*$",
    re.IGNORECASE,
)
_ACK_WORD = r"(?:ok|okay|k|cool|nice|great|good|got\s?it|sounds\s?good|perfect|awesome|alright)"
_ACK_RE = re.compile(rf"^{_ACK_WORD}([\s,]+{_ACK_WORD})*[!.\s]*$", re.IGNORECASE)
_HOW_ARE_YOU_RE = re.compile(
    r"^(how\s?are\s?you|how'?s\s?it\s?going|how\s?are\s?things|what'?s\s?up)[!?.\s]*$",
    re.IGNORECASE,
)

GREETING_REPLY = "Hi! Ask me anything about your uploaded document(s) — I'll answer using only what's in them."
THANKS_REPLY = "You're welcome! Let me know if there's anything else you'd like to know about your document(s)."
FAREWELL_REPLY = "Take care! Come back anytime you have more questions about your documents."
ACK_REPLY = "Got it — anything else you'd like to ask about your document(s)?"
HOW_ARE_YOU_REPLY = (
    "I'm doing well, thanks for asking! Ready whenever you want to ask something about your document(s)."
)


def detect_smalltalk_reply(message: str) -> str | None:
    """Return a canned reply for pure small talk, or None if this looks like a real question.

    Kept as fast, zero-latency regex matching rather than an LLM call — greetings and
    thanks are common enough in a chat UI that it's worth skipping retrieval entirely,
    and canned replies keep the tone consistently on-brand.
    """
    text = message.strip()
    if not text:
        return None

    if _GREETING_RE.match(text):
        return GREETING_REPLY
    if _THANKS_RE.match(text):
        return THANKS_REPLY
    if _FAREWELL_RE.match(text):
        return FAREWELL_REPLY
    if _HOW_ARE_YOU_RE.match(text):
        return HOW_ARE_YOU_REPLY
    if _ACK_RE.match(text):
        return ACK_REPLY

    return None
