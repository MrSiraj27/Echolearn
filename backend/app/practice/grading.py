"""Grading for the optional in-app "attempt" mode.

Honesty rule: only multiple-choice can be marked wrong automatically. Short answers and
numerical answers are auto-marked correct ONLY on a (normalised) exact match; anything
else - and every long / diagram answer - is returned with the model answer for the
student to self-mark. We never claim an automatic "incorrect" for free text."""

import math
import re
import unicodedata

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*(?:[eE][-+]?\d+)?|[-+]?\.\d+")


def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    text = re.sub(r"[^\w\s%.-]", " ", text)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _first_number(text: str) -> float | None:
    match = _NUMBER_RE.search((text or "").replace("−", "-"))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _numbers_match(submitted: str, expected: str) -> bool:
    a, b = _first_number(submitted), _first_number(expected)
    if a is None or b is None:
        return False
    return math.isclose(a, b, rel_tol=0.01, abs_tol=1e-9)


def _num(value) -> float:
    return float(value)


def grade_paper(content: dict, answers: dict[str, str], self_marks: dict[str, float] | None) -> dict:
    """Returns {"results": [...], "marks_obtained", "total_marks", "score_percent",
    "pending_self_grade_count"}."""
    self_marks = self_marks or {}
    results = []
    obtained = 0.0
    pending = 0

    for section in content["sections"]:
        for q in section["questions"]:
            qid = q["id"]
            marks = _num(q["marks"])
            submitted = (answers.get(qid) or "").strip()
            qtype = q["question_type"]
            status = "needs_self_grade"
            awarded: float | None = None
            note = None

            if qtype == "multiple_choice":
                if not submitted:
                    status, awarded = "unanswered", 0.0
                else:
                    chosen = submitted.strip()
                    letter = re.fullmatch(r"\(?([A-Da-d])[\).]?", chosen)
                    correct = (
                        letter.group(1).upper() == q.get("correct_option")
                        if letter
                        else _normalize_text(chosen) == _normalize_text(q["correct_answer"])
                    )
                    status, awarded = ("correct", marks) if correct else ("incorrect", 0.0)
            elif qtype in ("short_answer", "numerical"):
                expected = q.get("correct_answer") or q.get("model_answer") or ""
                if submitted and (
                    _normalize_text(submitted) == _normalize_text(expected)
                    or (qtype == "numerical" and _numbers_match(submitted, expected))
                ):
                    status, awarded = "correct", marks
                elif not submitted:
                    status = "needs_self_grade"
                    note = "No answer typed - compare with the model answer if you wrote it on paper."
                else:
                    note = "Not an exact match. Free-text answers can be worded differently, so compare with the model answer and mark yourself."
            else:
                note = "Long and diagram answers can't be auto-marked. Compare with the model answer and mark yourself."

            if awarded is None and qid in self_marks:
                try:
                    awarded = max(0.0, min(marks, float(self_marks[qid])))
                    status = "self_graded"
                except (TypeError, ValueError):
                    pass

            if awarded is None:
                pending += 1
            else:
                obtained += awarded

            results.append(
                {
                    "id": qid,
                    "section": section["name"],
                    "question_type": qtype,
                    "question_text": q["question_text"],
                    "options": q.get("options") or [],
                    "marks": q["marks"],
                    "submitted_answer": submitted or None,
                    "correct_answer": q.get("correct_answer") or None,
                    "correct_option": q.get("correct_option"),
                    "model_answer": q.get("model_answer"),
                    "status": status,
                    "marks_awarded": awarded,
                    "note": note,
                    "source_reference": q.get("source_reference"),
                }
            )

    total = _num(content["total_marks"])
    return {
        "results": results,
        "marks_obtained": round(obtained, 2),
        "total_marks": content["total_marks"],
        "score_percent": round(100 * obtained / total, 1) if total else 0.0,
        "pending_self_grade_count": pending,
    }
