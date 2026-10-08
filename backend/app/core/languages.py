"""Languages an answer can be explained in. Defined once here and reused by the chat
routes, the user preference, and the language explainer so the three values can't drift."""

import enum


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
