"""Render a revision sheet to a compact A4 PDF (fpdf2 + HarfBuzz text shaping).

Why fpdf2 and not WeasyPrint/ReportLab: Urdu needs real shaping (joined letters, right-to-left,
Nastaliq ligatures). WeasyPrint needs system Pango/Cairo libraries that a plain Python host
(like Render's native runtime) doesn't have, and ReportLab can't shape Urdu. fpdf2 with the
`uharfbuzz` wheel shapes Urdu with no system libraries at all.

Layout: two columns of "cards" (one card per item), a header, a footer disclaimer on every
page, and an answers box for the self-check questions. Every card is measured exactly before
it is placed (it is drawn once on an off-screen page to learn its height), so cards never
split or overflow a column. If the sheet runs past the requested page count we shrink the font
(floor 8.5pt), then drop the lowest-ranked items until it fits - it never silently overflows.
"""

import copy
import logging
import math
import os
import re
from datetime import datetime, timezone

from fpdf import FPDF

# fontTools logs every glyph it subsets at INFO; that would flood the server logs.
logging.getLogger("fontTools").setLevel(logging.WARNING)
logging.getLogger("fpdf").setLevel(logging.WARNING)

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

PAGE_W, PAGE_H = 210.0, 297.0
MARGIN = 11.0
GUTTER = 5.0
HEADER_H = 19.0
FOOTER_H = 9.0
COL_W = (PAGE_W - 2 * MARGIN - GUTTER) / 2
PAD = 1.8
CARD_GAP = 1.6

MIN_BODY_PT = 8.5
START_BODY_PT = 9.5
MIN_ITEMS = 5

DISCLAIMER = "AI-generated revision aid based on your uploaded material. Verify against your source documents."

INK = (20, 20, 20)
MUTED = (110, 110, 110)
RULE = (200, 200, 200)
CARD_BORDER = (190, 190, 190)
FORMULA_FILL = (240, 240, 240)
WATCH_FILL = (250, 244, 232)
WATCH_BORDER = (200, 150, 70)

_ARABIC_RE = re.compile("[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


# The bundled fonts cover essentially all science/maths symbols (arrows, Greek, super/subscripts,
# ≈ ≤ ≥ ...) via fallbacks, except these three. Replace them with readable equivalents instead
# of letting the PDF silently drop them. Also strip zero-width / control characters.
_SYMBOL_SUBSTITUTES = {"\u2211": "\u03a3", "\u222b": " integral ", "\u221d": " proportional to "}
_INVISIBLE_RE = re.compile(
    "[" + "".join(chr(c) for c in [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF] + list(range(0, 9)) + [11, 12] + list(range(14, 32))) + "]"
)


def _safe_text(text: str) -> str:
    text = _INVISIBLE_RE.sub("", text)
    for char, replacement in _SYMBOL_SUBSTITUTES.items():
        text = text.replace(char, replacement)
    return text


def _safe_sheet(value):
    """A copy of the sheet with every string made PDF-safe."""
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, list):
        return [_safe_sheet(v) for v in value]
    if isinstance(value, dict):
        return {k: _safe_sheet(v) for k, v in value.items()}
    return value


def _is_urdu(text: str) -> bool:
    """True if the text is mostly Urdu script (so it needs the Urdu font and right alignment)."""
    arabic = len(_ARABIC_RE.findall(text))
    latin = len(re.findall("[A-Za-z]", text))
    return arabic > 0 and arabic >= latin * 0.5


def _new_pdf(format_=(PAGE_W, PAGE_H)) -> FPDF:
    pdf = FPDF(unit="mm", format=format_)
    pdf.set_auto_page_break(False)
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.add_font("Sans", "", os.path.join(FONT_DIR, "NotoSans-Regular.ttf"))
    pdf.add_font("Sans", "B", os.path.join(FONT_DIR, "NotoSans-Bold.ttf"))
    pdf.add_font("Urdu", "", os.path.join(FONT_DIR, "NotoNastaliqUrdu-Regular.ttf"))
    pdf.add_font("Urdu", "B", os.path.join(FONT_DIR, "NotoNastaliqUrdu-Bold.ttf"))
    pdf.add_font("Mono", "", os.path.join(FONT_DIR, "NotoSansMono-Regular.ttf"))
    pdf.set_text_shaping(True)  # HarfBuzz: joins Urdu letters and handles right-to-left
    # A glyph missing from the current font (e.g. the arrow in "A → B", which Noto Sans lacks)
    # would otherwise be silently dropped from the page - on a cheat sheet that changes the
    # meaning. Fall back to the other bundled fonts for any symbol the main font can't draw.
    pdf.set_fallback_fonts(["Sans", "Mono", "Urdu"], exact_match=False)
    pdf.add_page()
    return pdf


class _Style:
    def __init__(self, body_pt: float, spacing: float):
        self.pt = body_pt
        self.spacing = spacing  # 1.0 normal, <1 tighter

    def line(self, urdu: bool) -> float:
        """Line height in mm. Nastaliq letters are tall and stacked, so Urdu needs far more."""
        factor = 2.15 if urdu else 1.38
        return self.pt * 0.3528 * factor * (0.92 + 0.08 * self.spacing)


class _Layout:
    """Draws one card. `draw=False` only measures (same code path, so heights are exact)."""

    def __init__(self, pdf: FPDF, style: _Style, ui_urdu: bool):
        self.pdf = pdf
        self.style = style
        self.ui_urdu = ui_urdu  # the whole sheet is in Urdu script

    # -- text helpers ---------------------------------------------------------

    def _font(self, urdu: bool, bold: bool = False, size: float | None = None, mono: bool = False) -> None:
        family = "Mono" if mono else ("Urdu" if urdu else "Sans")
        style = "B" if bold and not mono else ""
        self.pdf.set_font(family, style, size or self.style.pt)

    def _rtl_paragraph(self, x: float, y: float, w: float, text: str, bold=False, size=None, color=INK, draw=True) -> float:
        """Right-aligned Urdu paragraph. Returns the new y."""
        pdf = self.pdf
        size = (size or self.style.pt) + 0.5
        self._font(True, bold, size)
        pdf.set_text_color(*color)
        pdf.set_xy(x, y)
        line_h = self.style.line(True) * (size / self.style.pt)
        if not draw:
            lines = pdf.multi_cell(w, line_h, text, align="R", dry_run=True, output="LINES")
            return y + len(lines) * line_h
        pdf.multi_cell(w, line_h, text, align="R", new_x="LEFT", new_y="NEXT")
        return pdf.get_y()

    def _runs(self, x: float, y: float, w: float, runs: list[tuple[str, dict]], draw: bool) -> float:
        """Left-to-right text built from styled runs (e.g. bold term, normal text, gray ref).
        Wrapping is done by fpdf's write() inside temporary left/right margins = the card.
        `draw` is kept for symmetry: measuring is done by calling this on the off-screen
        measuring page (see _render), never on the real page."""
        pdf = self.pdf
        pdf.set_left_margin(x)
        pdf.set_right_margin(pdf.w - (x + w))
        pdf.set_xy(x, y)
        line_h = self.style.line(False)
        for text, opts in runs:
            self._font(False, opts.get("bold", False), opts.get("size"), opts.get("mono", False))
            pdf.set_text_color(*opts.get("color", INK))
            pdf.write(line_h, text)
        end_y = pdf.get_y() + line_h
        pdf.set_left_margin(MARGIN)
        pdf.set_right_margin(MARGIN)
        return end_y

    # -- one card per item kind ------------------------------------------------

    def card(self, item: dict, x: float, y: float, w: float, draw: bool, height: float | None = None) -> float:
        """Lay out an item card and return its height.

        Measuring (`draw=False`) is always done on the off-screen measuring page. Drawing
        (`draw=True`) needs that measured `height` up front so the card's border can be painted
        before its text."""
        kind = item["kind"]
        inner_x, inner_w = x + PAD, w - 2 * PAD
        cur = y + PAD * 0.8
        ref = f"[{item['ref']}]" if item.get("ref") else ""
        small = max(self.style.pt - 1.8, 6.2)

        def text_blocks() -> float:
            nonlocal cur
            if kind == "definition":
                cur = self._text(inner_x, cur, inner_w, item["term"], item["definition"], ref, draw)
            elif kind == "formula":
                cur = self._text(inner_x, cur, inner_w, item["name"], "", ref, draw)
                cur = self._formula(inner_x, cur + 0.4, inner_w, item["expression"], draw)
                if item.get("when_to_use"):
                    cur = self._text(inner_x, cur + 0.3, inner_w, "", item["when_to_use"], "", draw, size=small)
            elif kind == "fact":
                cur = self._text(inner_x, cur, inner_w, "", item["fact"], ref, draw)
            elif kind == "key_point":
                cur = self._text(inner_x, cur, inner_w, item.get("topic", ""), item["point"], ref, draw)
            elif kind == "process":
                cur = self._text(inner_x, cur, inner_w, item["name"], "", ref, draw)
                for n, step in enumerate(item["steps"], start=1):
                    cur = self._text(inner_x, cur, inner_w, "", f"{n}. {step}", "", draw)
            else:  # watch_out
                cur = self._text(inner_x, cur, inner_w, "", item["point"], ref, draw)
            if item.get("gloss"):
                cur = self._rtl_paragraph(inner_x, cur + 0.3, inner_w, item["gloss"], size=self.style.pt - 0.8,
                                          color=MUTED, draw=draw)
            return cur

        if draw:
            assert height is not None, "measure the card on the off-screen page first"
            border = WATCH_BORDER if kind == "watch_out" else CARD_BORDER
            fill = WATCH_FILL if kind == "watch_out" else None
            self.pdf.set_draw_color(*border)
            self.pdf.set_line_width(0.22)
            if fill:
                self.pdf.set_fill_color(*fill)
                self.pdf.rect(x, y, w, height, style="DF")
            else:
                self.pdf.rect(x, y, w, height, style="D")
        end = text_blocks()
        return (end - y) + PAD * 0.6

    def _text(self, x, y, w, lead, body, ref, draw, size=None) -> float:
        """A lead-in (bold) plus body text plus a small gray source ref, as one paragraph."""
        combined = f"{lead} {body}"
        if _is_urdu(combined):
            text = " ".join(part for part in (f"{lead}:" if lead and body else lead, body, ref) if part)
            return self._rtl_paragraph(x, y, w, text, draw=draw, size=size)
        runs: list[tuple[str, dict]] = []
        if lead:
            runs.append((lead + (" " if body else ""), {"bold": True}))
        if body:
            runs.append((body, {"size": size} if size else {}))
        if ref:
            runs.append(("  " + ref, {"color": MUTED, "size": max(self.style.pt - 2.0, 6.0)}))
        return self._runs(x, y, w, runs, draw)

    def _formula(self, x, y, w, expression, draw) -> float:
        """Formulas are always left-to-right, monospaced, on a light box."""
        pdf = self.pdf
        pad = 1.0
        line_h = self.style.line(False) * 1.05
        pdf.set_font("Mono", "", self.style.pt + 0.4)
        lines = pdf.multi_cell(w - 2 * pad, line_h, expression, dry_run=True, output="LINES")
        box_h = len(lines) * line_h + pad * 1.2
        if draw:
            pdf.set_fill_color(*FORMULA_FILL)
            pdf.rect(x, y, w, box_h, style="F")
            pdf.set_text_color(*INK)
            pdf.set_xy(x + pad, y + pad * 0.6)
            pdf.multi_cell(w - 2 * pad, line_h, expression, align="L", new_x="LEFT", new_y="NEXT")
        return y + box_h

    def heading(self, text: str, x: float, y: float, w: float, urdu: bool, draw: bool) -> float:
        pdf = self.pdf
        size = self.style.pt + 1.2
        self._font(urdu, True, size + (0.5 if urdu else 0))
        pdf.set_text_color(*INK)
        line_h = self.style.line(urdu) * (size / self.style.pt)
        if draw:
            pdf.set_xy(x, y)
            pdf.cell(w, line_h, text.upper() if not urdu else text, align="R" if urdu else "L")
            pdf.set_draw_color(*INK)
            pdf.set_line_width(0.3)
            pdf.line(x, y + line_h, x + w, y + line_h)
        return line_h + 1.6


# ------------------------------------------------------------------ whole-sheet rendering


def _label(sheet: dict, key: str) -> str:
    return (sheet.get("labels") or {}).get(key, key)


def _flat(sheet: dict) -> list[dict]:
    return [item for section in sheet["sections"] for item in section["items"]]


def _render(sheet: dict, style: _Style) -> tuple[bytes, int]:
    pdf = _new_pdf()
    measure = _new_pdf((PAGE_W, 4000.0))  # tall off-screen page used only to learn heights
    ui_urdu = sheet.get("language") == "ur"
    flow_layout = _Layout(pdf, style, ui_urdu)
    meter = _Layout(measure, style, ui_urdu)

    def measured(item: dict) -> float:
        measure.set_xy(0, 0)
        return meter.card(item, 0, 0, COL_W, draw=False)

    def heading_h(text: str) -> float:
        return meter.heading(text, 0, 0, COL_W, ui_urdu, draw=False)

    # ---- header (first page only)
    pdf.set_text_color(*MUTED)
    pdf.set_font("Sans", "", 7)
    pdf.set_xy(MARGIN, MARGIN - 3)
    pdf.cell(100, 4, "EchoLearn Revision Sheet")
    pdf.set_xy(PAGE_W - MARGIN - 80, MARGIN - 3)
    pdf.cell(80, 4, datetime.now(timezone.utc).strftime("%d %b %Y"), align="R")
    title = sheet["title"]
    pdf.set_text_color(*INK)
    title_urdu = _is_urdu(title)
    pdf.set_font("Urdu" if title_urdu else "Sans", "B", 15 if not title_urdu else 15.5)
    pdf.set_xy(MARGIN, MARGIN + (3.5 if title_urdu else 1.5))  # Nastaliq is tall: sit lower
    pdf.cell(PAGE_W - 2 * MARGIN, 8, title[:90], align="R" if title_urdu else "L")
    pdf.set_font("Sans", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.set_xy(MARGIN, MARGIN + 10)
    pdf.cell(PAGE_W - 2 * MARGIN, 4, sheet.get("subtitle", "")[:130])
    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.3)
    pdf.line(MARGIN, MARGIN + HEADER_H - 3, PAGE_W - MARGIN, MARGIN + HEADER_H - 3)

    # ---- flow state: pages -> two columns, filled top to bottom
    body_bottom = PAGE_H - MARGIN - FOOTER_H
    first_top = MARGIN + HEADER_H
    later_top = MARGIN + 2
    col_x = [MARGIN, MARGIN + COL_W + GUTTER]
    if ui_urdu:
        col_x.reverse()  # Urdu reads right to left: start in the right-hand column
    state = {"col": 0, "y": first_top, "top": first_top}

    def new_column() -> None:
        if state["col"] == 0:
            state["col"] = 1
        else:
            pdf.add_page()
            state["col"] = 0
            state["top"] = later_top
        state["y"] = state["top"]

    def ensure(height: float) -> None:
        if state["y"] + height > body_bottom and state["y"] > state["top"] + 0.01:
            new_column()

    # Heading + first card are kept together so a heading never sits alone at a column bottom.
    for section in sheet["sections"]:
        label = _label(sheet, section["type"])
        h_head = heading_h(label)
        first = measured(section["items"][0])
        ensure(h_head + first + CARD_GAP)
        x = col_x[state["col"]]
        state["y"] += flow_layout.heading(label, x, state["y"], COL_W, ui_urdu, draw=True)
        for item in section["items"]:
            height = measured(item)
            ensure(height + CARD_GAP)
            x = col_x[state["col"]]
            flow_layout.card(item, x, state["y"], COL_W, draw=True, height=height)
            state["y"] += height + CARD_GAP * style.spacing

    # ---- self-check: questions as a card, answers in a small box ("cover until you've tried")
    checks = sheet.get("self_check") or []
    if checks:
        label = _label(sheet, "self_check")
        questions = {"kind": "fact", "fact": "", "ref": "", "id": "sc"}
        q_text = "\n".join(f"{n}. {c['question']}" for n, c in enumerate(checks, start=1))
        a_text = "  ".join(f"{n}) {c['answer']}" for n, c in enumerate(checks, start=1))
        q_item = {**questions, "fact": q_text, "ref": ""}
        a_item = {**questions, "fact": f"{_label(sheet, 'answers')}: {a_text}", "ref": ""}
        total = heading_h(label) + measured(q_item) + measured(a_item) + 2 * CARD_GAP
        ensure(total)
        x = col_x[state["col"]]
        state["y"] += flow_layout.heading(label, x, state["y"], COL_W, ui_urdu, draw=True)
        for item in (q_item, a_item):
            height = measured(item)
            ensure(height + CARD_GAP)
            x = col_x[state["col"]]
            flow_layout.card(item, x, state["y"], COL_W, draw=True, height=height)
            state["y"] += height + CARD_GAP * style.spacing

    # ---- footer on every page (drawn last, when the total page count is known)
    total_pages = pdf.page
    for page in range(1, total_pages + 1):
        pdf.page = page
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.25)
        pdf.line(MARGIN, PAGE_H - MARGIN - FOOTER_H + 2, PAGE_W - MARGIN, PAGE_H - MARGIN - FOOTER_H + 2)
        pdf.set_text_color(*MUTED)
        pdf.set_font("Sans", "", 6.5)
        pdf.set_xy(MARGIN, PAGE_H - MARGIN - FOOTER_H + 3)
        pdf.cell(PAGE_W - 2 * MARGIN - 20, 4, DISCLAIMER)
        pdf.set_xy(PAGE_W - MARGIN - 20, PAGE_H - MARGIN - FOOTER_H + 3)
        pdf.cell(20, 4, f"{page} / {total_pages}", align="R")

    return bytes(pdf.output()), total_pages


def build_revision_pdf(sheet: dict) -> tuple[bytes, int, int]:
    """Render `sheet` to PDF within `sheet["page_target"]` pages.

    Returns (pdf_bytes, pages, dropped_items). Tries a normal render, then a smaller/tighter
    one (font floor 8.5pt), then drops the lowest-ranked items 10% at a time until it fits."""
    sheet = _safe_sheet(sheet)
    target = int(sheet.get("page_target") or 1)
    attempts = [_Style(START_BODY_PT, 1.0), _Style(MIN_BODY_PT, 0.9)]

    for style in attempts:
        data, pages = _render(sheet, style)
        if pages <= target:
            return data, pages, 0

    working = copy.deepcopy(sheet)
    total_before = len(_flat(working))
    style = attempts[-1]
    while True:
        items = _flat(working)
        if len(items) <= MIN_ITEMS:
            break
        drop = max(1, math.ceil(len(items) * 0.1))
        doomed = {id(i) for i in sorted(items, key=lambda i: i.get("rank", 0), reverse=True)[:drop]}
        for section in working["sections"]:
            section["items"] = [i for i in section["items"] if id(i) not in doomed]
        working["sections"] = [s for s in working["sections"] if s["items"]]
        data, pages = _render(working, style)
        if pages <= target:
            return data, pages, total_before - len(_flat(working))

    # Even the minimum didn't fit (extremely unlikely): return what we have, honestly reported.
    data, pages = _render(working, style)
    return data, pages, total_before - len(_flat(working))
