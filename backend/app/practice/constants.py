"""Shared constants for the Practice Paper feature.

Framing rule (applies to every user-facing string in this feature): this is an
"AI-Generated Practice Exam" / "Practice Paper" - a study aid. It is never described as
a prediction of the student's real exam."""

DISCLAIMER = (
    "This is an AI-generated practice paper based on your materials and any patterns you provided. "
    "It is a study aid, not a guaranteed prediction of your actual exam."
)

QUESTION_TYPES = ("multiple_choice", "short_answer", "long_answer", "numerical", "diagram_based")

QUESTION_TYPE_LABELS = {
    "multiple_choice": "Multiple Choice",
    "short_answer": "Short Answer",
    "long_answer": "Long Answer",
    "numerical": "Numerical",
    "diagram_based": "Diagram-Based",
}

# Sanity caps so a custom/extracted structure can't request an absurd paper.
MAX_SECTIONS = 8
MAX_QUESTIONS_PER_SECTION = 40
MAX_TOTAL_QUESTIONS = 80
MAX_MARKS_EACH = 100

DEFAULT_PATTERN = {
    "sections": [
        {"name": "Section A", "question_type": "multiple_choice", "count": 10, "marks_each": 1},
        {"name": "Section B", "question_type": "short_answer", "count": 5, "marks_each": 3},
        {"name": "Section C", "question_type": "long_answer", "count": 3, "marks_each": 8},
    ]
}

STANDARD_FORMAT_NOTE = "Standard practice format"
