"""Languages an answer can be explained in. Defined once here and reused by the chat
routes, the user preference, and the language explainer so the three values can't drift."""

import enum
import re

# EchoLearn serves Pakistani students: English, Urdu (Urdu script) and Roman Urdu only. Hindi
# (written in Devanagari) must never be shown, even when a source document is in Hindi.
DEVANAGARI_RE = re.compile("[ऀ-ॿ꣠-ꣿ]")


def contains_devanagari(text: str | None) -> bool:
    return bool(text) and DEVANAGARI_RE.search(text) is not None


class Language(str, enum.Enum):
    en = "en"
    ur = "ur"  # Urdu, written in Urdu script
    roman_ur = "roman_ur"  # Urdu written in Latin letters


class ExplainMode(str, enum.Enum):
    translate = "translate"  # faithful rendering of the answer
    simplify = "simplify"  # simpler wording (plus one labelled analogy)


# Languages the explain endpoint can produce (English is the original answer itself).
EXPLAIN_TARGETS = (Language.ur, Language.roman_ur)

LANGUAGE_LABELS = {
    Language.en: "English",
    Language.ur: "Urdu (in Urdu script)",
    Language.roman_ur: "Roman Urdu (Urdu written in Latin letters)",
}
