"""Question Paper / Answer Key PDFs for a practice paper (reportlab platypus).

Unicode: the app's chat exporter uses the built-in Helvetica (Latin-1 only), which turns
anything outside Latin-1 into black boxes. LLM text routinely contains characters such as
U+2011 (non-breaking hyphen) and U+202F (narrow no-break space), so these PDFs instead
register the TrueType Bitstream Vera family that ships inside reportlab (no new
dependency, works on every OS) and pass all text through `pdf_safe()`, which
  1. normalises exotic spaces / hyphens / quotes to their plain equivalents,
  2. drops zero-width and control characters,
  3. for any character the font still lacks, tries a readable substitute (Greek letter
     names, arrows, NFKD decomposition e.g. subscripts) and finally '?'.
so text can never crash the build or render as a missing-glyph box.
"""

import io
import os
import re
import unicodedata

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.practice.constants import DISCLAIMER, QUESTION_TYPE_LABELS

_FONT_DIR = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
_FONTS_READY = False
_GLYPHS: set[int] = set()

INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#666666")
FAINT = colors.HexColor("#999999")
RULE = colors.HexColor("#cfcfcf")
PANEL = colors.HexColor("#f3f3f3")

MARGIN = 0.85 * inch
CONTENT_WIDTH = LETTER[0] - 2 * MARGIN


def _ensure_fonts() -> None:
    global _FONTS_READY
    if _FONTS_READY:
        return
    for name, filename in (
        ("Vera", "Vera.ttf"),
        ("VeraBd", "VeraBd.ttf"),
        ("VeraIt", "VeraIt.ttf"),
        ("VeraBI", "VeraBI.ttf"),
    ):
        pdfmetrics.registerFont(TTFont(name, os.path.join(_FONT_DIR, filename)))
    pdfmetrics.registerFontFamily("Vera", normal="Vera", bold="VeraBd", italic="VeraIt", boldItalic="VeraBI")
    _GLYPHS.update(pdfmetrics.getFont("Vera").face.charToGlyph.keys())
    _FONTS_READY = True


# ---- text safety ----

_SPACE_LIKE = {
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", "　": " ", " ": "\n",
}
_HYPHEN_LIKE = {"‐": "-", "‑": "-", "‒": "-", "⁃": "-", "­": "", "−": "-"}
_INVISIBLE = {"​", "‌", "‍", "⁠", "﻿", "‎", "‏", "‪", "‫", "‬", "‭", "‮"}
_SUBSTITUTES = {
    "→": "->", "←": "<-", "↔": "<->", "⇒": "=>", "✓": "v", "✔": "v", "✗": "x",
    "✘": "x", "□": "[ ]", "☐": "[ ]", "☑": "[x]", "●": "*", "○": "o",
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "θ": "theta",
    "λ": "lambda", "μ": "mu", "σ": "sigma", "τ": "tau", "φ": "phi", "ω": "omega",
    "Δ": "Delta", "Σ": "Sigma", "Φ": "Phi", "Γ": "Gamma", "Θ": "Theta", "Λ": "Lambda",
    "≠": "!=", "≤": "<=", "≥": ">=", "•": "-", "≈": "~", "√": "sqrt", "∞": "infinity",
}


def pdf_safe(text) -> str:
    """Make arbitrary text safe to draw with the registered Vera font (see module doc)."""
    _ensure_fonts()
    text = str(text or "")
    out: list[str] = []
    for ch in text:
        if ch in _INVISIBLE:
            continue
        if ch in _SPACE_LIKE:
            out.append(_SPACE_LIKE[ch])
            continue
        if ch in _HYPHEN_LIKE:
            out.append(_HYPHEN_LIKE[ch])
            continue
        if ch in ("\n", "\t"):
            out.append(ch)
            continue
        if unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co"):
            continue
        if ord(ch) in _GLYPHS:
            out.append(ch)
            continue
        if ch in _SUBSTITUTES:
            out.append(_SUBSTITUTES[ch])
            continue
        decomposed = unicodedata.normalize("NFKD", ch)
        if decomposed != ch:
            stripped = "".join(c for c in decomposed if ord(c) in _GLYPHS and not unicodedata.combining(c))
            if stripped:
                out.append(stripped)
                continue
        out.append("?")
    return "".join(out)


def _esc(text) -> str:
    return pdf_safe(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rich(text) -> str:
    """Escaped text with newlines -> <br/> and **bold** -> <b>."""
    escaped = _esc(text).replace("\r", "")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return escaped.replace("\n", "<br/>")


# ---- styles ----


def _styles() -> dict[str, ParagraphStyle]:
    _ensure_fonts()
    base = dict(fontName="Vera", textColor=INK, fontSize=10, leading=14)
    return {
        "title": ParagraphStyle("PTitle", **{**base, "fontName": "VeraBd", "fontSize": 20, "leading": 25, "alignment": TA_CENTER}),
        "subtitle": ParagraphStyle("PSub", **{**base, "fontSize": 10, "textColor": MUTED, "alignment": TA_CENTER, "spaceAfter": 10}),
        "body": ParagraphStyle("PBody", **base),
        "small": ParagraphStyle("PSmall", **{**base, "fontSize": 8.5, "leading": 12, "textColor": MUTED}),
        "info": ParagraphStyle("PInfo", **{**base, "fontSize": 10, "alignment": TA_CENTER}),
        "disclaimer": ParagraphStyle("PDisc", **{**base, "fontName": "VeraBd", "fontSize": 9.5, "leading": 13.5}),
        "h_instr": ParagraphStyle("PHInstr", **{**base, "fontName": "VeraBd", "fontSize": 10, "spaceBefore": 4, "spaceAfter": 3}),
        "bullet": ParagraphStyle("PBullet", **{**base, "fontSize": 9.5, "leading": 13, "leftIndent": 12, "bulletIndent": 0}),
        "section": ParagraphStyle("PSection", **{**base, "fontName": "VeraBd", "fontSize": 11.5, "leading": 15}),
        "section_marks": ParagraphStyle("PSectionM", **{**base, "fontSize": 9.5, "alignment": TA_RIGHT, "textColor": MUTED}),
        "section_instr": ParagraphStyle("PSectionI", **{**base, "fontName": "VeraIt", "fontSize": 9.5, "textColor": MUTED, "spaceBefore": 4, "spaceAfter": 8}),
        "q": ParagraphStyle("PQ", **{**base, "fontSize": 10.5, "leading": 15}),
        "q_num": ParagraphStyle("PQNum", **{**base, "fontName": "VeraBd", "fontSize": 10.5, "leading": 15}),
        "q_marks": ParagraphStyle("PQMarks", **{**base, "fontSize": 9, "leading": 15, "alignment": TA_RIGHT, "textColor": MUTED}),
        "option": ParagraphStyle("POpt", **{**base, "fontSize": 10, "leading": 14, "leftIndent": 0.5 * inch, "firstLineIndent": 0, "spaceBefore": 2}),
        "option_correct": ParagraphStyle("POptC", **{**base, "fontName": "VeraBd", "fontSize": 10, "leading": 14, "leftIndent": 0.5 * inch, "spaceBefore": 2}),
        "answer": ParagraphStyle("PAns", **{**base, "fontSize": 9.5, "leading": 13.5, "leftIndent": 0.5 * inch, "spaceBefore": 4}),
        "source": ParagraphStyle("PSrc", **{**base, "fontSize": 8.5, "leading": 12, "leftIndent": 0.5 * inch, "textColor": MUTED, "spaceBefore": 3}),
    }


# ---- flowables ----


class AnswerLines(Flowable):
    """Light ruled writing lines."""

    def __init__(self, lines: int, line_height: float = 0.29 * inch, indent: float = 0.5 * inch):
        super().__init__()
        self.lines = lines
        self.line_height = line_height
        self.indent = indent

    def wrap(self, avail_width, avail_height):
        self.avail_width = avail_width
        return avail_width, self.lines * self.line_height + 4

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        for i in range(self.lines):
            y = self.lines * self.line_height - (i + 1) * self.line_height + 4
            c.line(self.indent, y, self.avail_width, y)
        c.restoreState()


class AnswerBox(Flowable):
    """Empty bordered box (diagram questions)."""

    def __init__(self, height: float, indent: float = 0.5 * inch):
        super().__init__()
        self.height = height
        self.indent = indent

    def wrap(self, avail_width, avail_height):
        self.avail_width = avail_width
        return avail_width, self.height + 4

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.rect(self.indent, 2, self.avail_width - self.indent, self.height)
        c.restoreState()


class _NumberedCanvas(rl_canvas.Canvas):
    """Two-pass canvas so the footer can say 'Page x of y'."""

    footer_left = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages: list[dict] = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total: int):
        self.saveState()
        self.setStrokeColor(RULE)
        self.setLineWidth(0.5)
        self.line(MARGIN, 0.62 * inch, LETTER[0] - MARGIN, 0.62 * inch)
        self.setFont("Vera", 8)
        self.setFillColor(FAINT)
        self.drawString(MARGIN, 0.45 * inch, self.footer_left)
        self.drawRightString(LETTER[0] - MARGIN, 0.45 * inch, f"Page {self._pageNumber} of {total}")
        self.restoreState()


# ---- building blocks ----


def _fmt_marks(marks) -> str:
    marks = int(marks) if float(marks) == int(marks) else marks
    return f"[{marks} mark{'s' if marks != 1 else ''}]"


def _section_heading(section: dict, letter_label: str, styles) -> Table:
    total = section["count"] * section["marks_each"]
    total = int(total) if float(total) == int(total) else round(total, 2)
    me = section["marks_each"]
    me = int(me) if float(me) == int(me) else me
    left = Paragraph(
        f"{_esc(section['name'])} &nbsp;-&nbsp; {_esc(QUESTION_TYPE_LABELS[section['question_type']])}", styles["section"]
    )
    right = Paragraph(f"{section['count']} x {me} = {total} marks", styles["section_marks"])
    table = Table([[left, right]], colWidths=[CONTENT_WIDTH * 0.68, CONTENT_WIDTH * 0.32])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("LINEABOVE", (0, 0), (-1, 0), 1.2, INK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (0, 0), 8),
                ("RIGHTPADDING", (-1, 0), (-1, 0), 8),
            ]
        )
    )
    return table


def _question_head(number: int, question: dict, styles) -> Table:
    table = Table(
        [
            [
                Paragraph(f"{number}.", styles["q_num"]),
                Paragraph(_rich(question["question_text"]), styles["q"]),
                Paragraph(_fmt_marks(question["marks"]), styles["q_marks"]),
            ]
        ],
        colWidths=[0.5 * inch, CONTENT_WIDTH - 0.5 * inch - 0.95 * inch, 0.95 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _answer_space(question: dict) -> list:
    marks = float(question["marks"])
    qtype = question["question_type"]
    if qtype == "short_answer":
        return [Spacer(1, 4), AnswerLines(min(8, max(2, int(round(marks * 1.4)) + 1)))]
    if qtype == "long_answer":
        return [Spacer(1, 4), AnswerLines(min(20, max(6, int(round(marks * 1.6)) + 2)))]
    if qtype == "numerical":
        return [Spacer(1, 4), AnswerLines(min(12, max(5, int(round(marks * 1.5)) + 3)))]
    if qtype == "diagram_based":
        return [Spacer(1, 4), AnswerBox(min(5.0, max(2.2, 1.6 + marks * 0.45)) * inch)]
    return []


def _all_questions(content: dict):
    number = 0
    for section in content["sections"]:
        for question in section["questions"]:
            number += 1
            yield number, section, question


def _general_instructions(content: dict) -> list[str]:
    total_marks = content["total_marks"]
    time_line = f"You have {content['time_allowed_minutes']} minutes" + (
        " (a suggested time estimated from the paper's structure)." if content.get("time_estimated") else "."
    )
    return [
        time_line,
        f"The paper has {content['total_questions']} questions and is worth {total_marks} marks in total. Attempt all questions.",
        "The marks for each question are shown in square brackets at the right of the question.",
        "For multiple-choice questions, circle the letter of the single best answer.",
        "Write your answers in the space provided under each question, and show your working for calculations.",
    ]


def _build_story(paper_title: str, content: dict, variant: str) -> list:
    styles = _styles()
    story: list = []
    is_key = variant == "answer_key"

    story.append(Paragraph(_esc(paper_title), styles["title"]))
    story.append(
        Paragraph("AI-Generated Practice Exam" + (" &nbsp;-&nbsp; ANSWER KEY" if is_key else ""), styles["subtitle"])
    )

    minutes = content["time_allowed_minutes"]
    info = Table(
        [
            [
                Paragraph(f"<b>Total marks:</b> {content['total_marks']}", styles["info"]),
                Paragraph(
                    f"<b>Time allowed:</b> {minutes} minutes" + (" (est.)" if content.get("time_estimated") else ""),
                    styles["info"],
                ),
                Paragraph(f"<b>Questions:</b> {content['total_questions']}", styles["info"]),
            ]
        ],
        colWidths=[CONTENT_WIDTH / 3.0] * 3,
    )
    info.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, INK),
                ("LINEAFTER", (0, 0), (-2, -1), 0.5, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(info)
    story.append(Spacer(1, 8))

    if not is_key:
        story.append(
            Paragraph("Name: ______________________________ &nbsp;&nbsp;&nbsp;&nbsp; Date: ________________", styles["body"])
        )
        story.append(Spacer(1, 8))

    # The disclaimer travels with the PDF: verbatim, on page 1 of BOTH files.
    disclaimer = Table([[Paragraph(_esc(DISCLAIMER), styles["disclaimer"])]], colWidths=[CONTENT_WIDTH])
    disclaimer.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("BOX", (0, 0), (-1, -1), 0.8, INK),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(disclaimer)
    story.append(Spacer(1, 10))

    if is_key:
        story.append(
            Paragraph(
                "Model answers are drawn from the source material you selected. Where a question has several valid "
                "answers, award marks for any response that is supported by that material. Source references show the "
                "file and page each question was written from.",
                styles["small"],
            )
        )
    else:
        story.append(Paragraph("General instructions", styles["h_instr"]))
        for line in _general_instructions(content):
            story.append(Paragraph(_esc(line), styles["bullet"], bulletText="•"))
    story.append(Spacer(1, 6))

    number = 0
    for s_idx, section in enumerate(content["sections"]):
        heading = _section_heading(section, chr(ord("A") + s_idx), styles)
        instr = Paragraph(_esc(section.get("instructions", "")), styles["section_instr"]) if section.get("instructions") else Spacer(1, 6)
        first = True
        story.append(CondPageBreak(2.2 * inch))
        for question in section["questions"]:
            number += 1
            block: list = [_question_head(number, question, styles)]
            if question["question_type"] == "multiple_choice":
                for i, option in enumerate(question["options"]):
                    letter = "ABCD"[i]
                    is_right = is_key and question.get("correct_option") == letter
                    block.append(
                        Paragraph(
                            f"{letter}. &nbsp;{_esc(option)}", styles["option_correct" if is_right else "option"]
                        )
                    )
                if is_key:
                    block.append(
                        Paragraph(
                            f"<b>Correct answer: {question.get('correct_option', '')}</b>"
                            + (f" &nbsp;-&nbsp; {_rich(question['model_answer'])}" if question.get("model_answer") else ""),
                            styles["answer"],
                        )
                    )
                else:
                    block.append(Spacer(1, 4))
            elif is_key:
                if question["question_type"] in ("short_answer", "numerical") and question.get("correct_answer"):
                    block.append(Paragraph(f"<b>Answer:</b> {_rich(question['correct_answer'])}", styles["answer"]))
                block.append(Paragraph(f"<b>Model answer:</b> {_rich(question['model_answer'])}", styles["answer"]))
            else:
                block.extend(_answer_space(question))

            if is_key:
                refs = "; ".join(
                    dict.fromkeys(_esc(r.get("label", "")) for r in question.get("source_references") or [question["source_reference"]])
                )
                block.append(Paragraph(f"Source: {refs}", styles["source"]))

            block.append(Spacer(1, 10))
            if first:
                # Never strand a section heading at the bottom of a page: keep it with
                # its instructions and the first question.
                story.append(KeepTogether([heading, instr] + block))
                first = False
            else:
                story.append(KeepTogether(block))

    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", color=RULE, thickness=0.6, spaceAfter=6))
    story.append(
        Paragraph(
            "End of answer key" if is_key else "End of paper",
            ParagraphStyle("End", parent=styles["small"], alignment=TA_CENTER),
        )
    )
    return story


def build_paper_pdf(paper_title: str, content: dict, variant: str = "question") -> bytes:
    """variant: "question" (blank exam paper) or "answer_key"."""
    if variant not in ("question", "answer_key"):
        raise ValueError("variant must be 'question' or 'answer_key'")
    _ensure_fonts()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        topMargin=0.8 * inch,
        bottomMargin=0.85 * inch,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        title=pdf_safe(paper_title) + (" - Answer Key" if variant == "answer_key" else " - Question Paper"),
        author="EchoLearn",
        subject="AI-generated practice paper (study aid)",
    )

    class Canvas(_NumberedCanvas):
        footer_left = pdf_safe(
            ("AI-generated practice exam - answer key" if variant == "answer_key" else "AI-generated practice exam")
            + " - study aid only"
        )

    doc.build(_build_story(paper_title, content, variant), canvasmaker=Canvas)
    return buffer.getvalue()
