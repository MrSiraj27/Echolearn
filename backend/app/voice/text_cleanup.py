import re

_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]*)`")
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_HEADING_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_BOLD_ITALIC_RE = re.compile(r"(\*\*\*|\*\*|\*|___|__|_)")
_BULLET_RE = re.compile(r"^[\s]*[-*+]\s+", re.MULTILINE)
_NUMBERED_LIST_RE = re.compile(r"^[\s]*\d+\.\s+", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^>\s*", re.MULTILINE)
_HR_RE = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{2,}")
_REPEATED_PUNCTUATION_RE = re.compile(r"([.!?])\s*\1+")

# Matches the inline source citations EchoLearn's answers include, e.g. "(p. 3)",
# "(page 12)", "(multipage.pdf, p. 2)", "(p. 1, Sec 1)" — these are meant to be read on
# screen, not spoken aloud ("open paren pee dot one close paren" is not useful speech).
_CITATION_RE = re.compile(
    r"\s*\([^()]*\bp(?:age)?s?\.?\s*\d+[^()]*\)", re.IGNORECASE
)


def clean_text_for_speech(text: str) -> str:
    """Strip markdown syntax so Piper speaks natural sentences instead of reading
    literal symbols ("asterisk asterisk bold asterisk asterisk")."""
    cleaned = text

    cleaned = _CODE_BLOCK_RE.sub(" ", cleaned)
    cleaned = _INLINE_CODE_RE.sub(r"\1", cleaned)
    cleaned = _LINK_RE.sub(r"\1", cleaned)
    cleaned = _HEADING_RE.sub("", cleaned)
    cleaned = _BLOCKQUOTE_RE.sub("", cleaned)
    cleaned = _HR_RE.sub(" ", cleaned)
    cleaned = _BULLET_RE.sub("", cleaned)
    cleaned = _NUMBERED_LIST_RE.sub("", cleaned)
    cleaned = _BOLD_ITALIC_RE.sub("", cleaned)
    cleaned = _CITATION_RE.sub("", cleaned)

    # Collapse whitespace left behind by stripped syntax.
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    cleaned = _MULTI_NEWLINE_RE.sub(". ", cleaned)
    cleaned = cleaned.replace("\n", ". ")
    cleaned = _REPEATED_PUNCTUATION_RE.sub(r"\1", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)

    return cleaned.strip()
