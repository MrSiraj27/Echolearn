"""Builds "EchoLearn FYP Final Document.docx" in the layout of the Bahria University FYP template.

Usage (from docs/fyp):  python build_report.py [--skip-tests]

The tables of contents / tables / figures are Word fields; run finalize_report.ps1 afterwards so
Word fills in page numbers and exports the PDF.
"""
import importlib.util
import os
import re
import subprocess
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
ASSETS = os.path.join(HERE, "assets")
OUT = os.path.join(HERE, "EchoLearn FYP Final Document.docx")
BACKEND = os.path.join(os.path.dirname(os.path.dirname(HERE)), "backend")
TEXT_WIDTH = 6.25  # inches: 8.5 - 1.25 - 1.0

BODY_FONT = "Times New Roman"
HEAD_FONT = "Calibri"


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "content", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


refs_mod = load("refs")
front = load("front_back")
chapters = []
for mod_name in ("ch1_ch2", "ch3", "ch4", "ch5", "ch6_ch7"):
    chapters += load(mod_name).BLOCKS
BLOCKS = chapters + front.appendices()
REFS = refs_mod.REFS


# ------------------------------------------------------------------ test results -> table cells
def run_tests() -> dict:
    cmd = [os.path.join(BACKEND, "venv", "Scripts", "python.exe"), "-W", "ignore", "-m", "unittest", "discover",
           "-s", "tests", "-t", ".", "-v"]
    proc = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = proc.stdout + "\n" + proc.stderr
    results = {}
    for m in re.finditer(r"test_([A-Z]+\d+)_\w+ \([^)]*\) \.\.\. (ok|FAIL|ERROR|skipped[^\n]*)", text):
        tid, status = m.group(1), m.group(2)
        results[tid] = "PASS" if status == "ok" else ("SKIPPED" if status.startswith("skipped") else "FAIL")
    summary = re.search(r"Ran (\d+) tests", text)
    print(f"tests: {len(results)} parsed, ran={summary.group(1) if summary else '?'}; "
          f"{sum(v == 'PASS' for v in results.values())} pass")
    return results


if "--skip-tests" in sys.argv:
    TEST_RESULTS = {}
else:
    TEST_RESULTS = run_tests()

# ------------------------------------------------------------------ numbering pre-pass
label_numbers = {}        # "tbl:name" / "fig:name" -> "4.2"
cite_numbers = {}         # ref key -> n
_chapter = 0
_counters = {"tbl": 0, "fig": 0}


def _scan_cites(text):
    for key in re.findall(r"\[\[([a-z0-9_,\s]+)\]\]", text):
        for k in [x.strip() for x in key.split(",")]:
            if k not in REFS:
                raise KeyError(f"unknown reference {k}")
            cite_numbers.setdefault(k, len(cite_numbers) + 1)


for blk in BLOCKS:
    kind = blk[0]
    if kind == "h1":
        m = re.match(r"Chapter (\d+):", blk[1])
        if m:
            _chapter = int(m.group(1))
            _counters = {"tbl": 0, "fig": 0}
    elif kind == "table":
        _counters["tbl"] += 1
        label_numbers["tbl:" + blk[1]] = f"{_chapter}.{_counters['tbl']}"
    elif kind == "fig":
        _counters["fig"] += 1
        label_numbers["fig:" + blk[1]] = f"{_chapter}.{_counters['fig']}"
for blk in BLOCKS:
    kind = blk[0]
    if kind in ("p",):
        _scan_cites(blk[1])
    elif kind in ("ul", "ol"):
        for it in blk[1]:
            _scan_cites(it)
    elif kind == "table":
        for row in blk[4]:
            for cell in row:
                _scan_cites(cell)


def expand(text: str) -> str:
    def cite(m):
        keys = [k.strip() for k in m.group(1).split(",")]
        return ", ".join(f"[{cite_numbers[k]}]" for k in keys)

    def xref(m):
        kind, label = m.group(1), m.group(2)
        num = label_numbers[f"{kind}:{label}"]
        return ("Table " if kind == "tbl" else "Figure ") + num

    text = re.sub(r"\[\[([a-z0-9_,\s]+)\]\]", cite, text)
    text = re.sub(r"\{(tbl|fig):([a-z0-9_]+)\}", xref, text)
    return text.replace(" -- ", " – ")


# ------------------------------------------------------------------ docx helpers
doc = Document()


def set_font(style_or_run, name, size=None, bold=None, color=None):
    f = style_or_run.font
    f.name = name
    if size is not None:
        f.size = Pt(size)
    if bold is not None:
        f.bold = bold
    if color is not None:
        f.color.rgb = RGBColor(*color)
    rpr = style_or_run.element.get_or_add_rPr() if hasattr(style_or_run, "element") and hasattr(
        style_or_run.element, "get_or_add_rPr") else None
    if rpr is not None:
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        for att in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rfonts.set(qn(att), name)


def para_fmt(pf, align=None, before=0, after=0, line=None, keep_next=False, keep_lines=False, page_break=False,
             left=None, first=None):
    if align is not None:
        pf.alignment = align
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if line is not None:
        pf.line_spacing = line
    pf.keep_with_next = keep_next
    pf.keep_together = keep_lines
    pf.page_break_before = page_break
    if left is not None:
        pf.left_indent = Inches(left)
    if first is not None:
        pf.first_line_indent = Inches(first)


# base styles
st = doc.styles
normal = st["Normal"]
set_font(normal, BODY_FONT, 12)
para_fmt(normal.paragraph_format, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 8, 1.5)

for name, size in (("Heading 1", 16), ("Heading 2", 14), ("Heading 3", 13)):
    h = st[name]
    set_font(h, HEAD_FONT, size, True, (0, 0, 0))
    h.font.italic = False
    para_fmt(h.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT,
             before=0 if name == "Heading 1" else (14 if name == "Heading 2" else 10),
             after=12 if name == "Heading 1" else 6, line=1.15, keep_next=True, keep_lines=True,
             page_break=(name == "Heading 1"))

front_title = st.add_style("Front Title", WD_STYLE_TYPE.PARAGRAPH)
front_title.base_style = normal
set_font(front_title, BODY_FONT, 16, True, (0, 0, 0))
para_fmt(front_title.paragraph_format, WD_ALIGN_PARAGRAPH.CENTER, before=0, after=18, line=1.15, keep_next=True,
         page_break=True)

cap_tbl = st.add_style("Table Caption", WD_STYLE_TYPE.PARAGRAPH)
cap_tbl.base_style = normal
set_font(cap_tbl, BODY_FONT, 10, True, (0, 0, 0))
para_fmt(cap_tbl.paragraph_format, WD_ALIGN_PARAGRAPH.CENTER, before=10, after=4, line=1.0, keep_next=True)

cap_fig = st.add_style("Figure Caption", WD_STYLE_TYPE.PARAGRAPH)
cap_fig.base_style = normal
set_font(cap_fig, BODY_FONT, 10, True, (0, 0, 0))
para_fmt(cap_fig.paragraph_format, WD_ALIGN_PARAGRAPH.CENTER, before=4, after=14, line=1.0)

cell_style = st.add_style("Table Text", WD_STYLE_TYPE.PARAGRAPH)
cell_style.base_style = normal
set_font(cell_style, BODY_FONT, 10)
para_fmt(cell_style.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, before=2, after=2, line=1.0)

code_style = st.add_style("Code Block", WD_STYLE_TYPE.PARAGRAPH)
code_style.base_style = normal
set_font(code_style, "Courier New", 9)
para_fmt(code_style.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, before=0, after=0, line=1.0, left=0.1)

for list_style in ("List Bullet", "List Number"):
    ls = st[list_style]
    set_font(ls, BODY_FONT, 12)
    para_fmt(ls.paragraph_format, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 4, 1.5)

# page setup
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
sec.left_margin, sec.right_margin = Inches(1.25), Inches(1.0)
sec.top_margin, sec.bottom_margin = Inches(1.0), Inches(1.0)
sec.footer_distance = Inches(0.55)
sec.header_distance = Inches(0.5)

doc.core_properties.title = front.TITLE
doc.core_properties.author = ", ".join(n for _, n in front.MEMBERS)
doc.core_properties.subject = "Final Year Project report, BSCS, Bahria University Lahore Campus"
doc.core_properties.keywords = "retrieval-augmented generation, study assistant, spaced repetition"


def shade(cell_or_par, fill):
    el = cell_or_par._tc if hasattr(cell_or_par, "_tc") else cell_or_par._p
    tcPr = el.get_or_add_tcPr() if hasattr(el, "get_or_add_tcPr") else el.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def add_field(par, instr, placeholder=""):
    r1 = par.add_run()
    fc = OxmlElement("w:fldChar")
    fc.set(qn("w:fldCharType"), "begin")
    r1._r.append(fc)
    r2 = par.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    r2._r.append(it)
    r3 = par.add_run()
    fc2 = OxmlElement("w:fldChar")
    fc2.set(qn("w:fldCharType"), "separate")
    r3._r.append(fc2)
    r4 = par.add_run(placeholder)
    r5 = par.add_run()
    fc3 = OxmlElement("w:fldChar")
    fc3.set(qn("w:fldCharType"), "end")
    r5._r.append(fc3)
    return par


def add_runs(par, text, bold=None, size=None, highlight_placeholders=True):
    """Add text; any [___] style placeholder is highlighted yellow so it cannot be missed."""
    parts = re.split(r"(\[[^\]]*___[^\]]*\]|\[Date\])", text) if highlight_placeholders else [text]
    for part in parts:
        if not part:
            continue
        run = par.add_run(part)
        if bold is not None:
            run.bold = bold
        if size:
            run.font.size = Pt(size)
        if highlight_placeholders and (("___" in part and part.startswith("[")) or part == "[Date]"):
            rpr = run._r.get_or_add_rPr()
            hl = OxmlElement("w:highlight")
            hl.set(qn("w:val"), "yellow")
            rpr.append(hl)


def centered(text, size=12, bold=False, before=0, after=0, line=1.0, keep_next=False):
    p = doc.add_paragraph()
    para_fmt(p.paragraph_format, WD_ALIGN_PARAGRAPH.CENTER, before, after, line, keep_next)
    add_runs(p, text, bold, size)
    return p


def set_cell_borders(table, sz=4):
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tblPr.append(borders)


def set_cell_margins(table, top=40, bottom=40, left=90, right=90):
    tblPr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)


def make_table(header, rows, widths, bold_first_col=False):
    scale = TEXT_WIDTH / sum(widths)
    widths = [w * scale for w in widths]
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    set_cell_borders(t)
    set_cell_margins(t)
    tblPr = t._tbl.tblPr
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblPr.append(lay)
    for ri, row in enumerate([header] + rows):
        tr = t.rows[ri]
        trPr = tr._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit")
        trPr.append(cs)
        if ri == 0:
            th = OxmlElement("w:tblHeader")
            trPr.append(th)
        for ci, val in enumerate(row):
            cell = tr.cells[ci]
            cell.width = Inches(widths[ci])
            par = cell.paragraphs[0]
            par.style = st["Table Text"]
            text = expand(val)
            if text.startswith("@"):
                key = text[1:]
                text = TEST_RESULTS.get(key, "n/a")
            run = par.add_run(text)
            if ri == 0 or (bold_first_col and ci == 0):
                run.bold = True
            if text in ("PASS",):
                run.bold = True
            if ri == 0:
                shade(cell, "E7E6E6")
    n_rows = len(t.rows)
    for ri, tr in enumerate(t.rows):
        keep = (n_rows <= 8 and ri < n_rows - 1) or ri == 0 or (n_rows > 3 and ri == n_rows - 2)
        if keep:
            for cell in tr.cells:
                for par in cell.paragraphs:
                    par.paragraph_format.keep_with_next = True
    # fixed grid widths
    grid = t._tbl.tblGrid
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
        gc.set(qn("w:w"), str(int(w * 1440)))
    return t


def spacer(pts=6):
    p = doc.add_paragraph()
    para_fmt(p.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, 0, 0, 1.0)
    p.paragraph_format.space_after = Pt(pts)
    return p


def add_footer_page_number(section, fmt, start):
    section.footer.is_linked_to_previous = False
    fp = section.footer.paragraphs[0]
    for r in list(fp.runs):
        r._r.getparent().remove(r._r)
    para_fmt(fp.paragraph_format, WD_ALIGN_PARAGRAPH.CENTER, 0, 0, 1.0)
    run_holder = fp
    add_field(run_holder, "PAGE", "1")
    for r in fp.runs:
        r.font.size = Pt(10)
        r.font.name = BODY_FONT
    sectPr = section._sectPr
    pg = sectPr.find(qn("w:pgNumType"))
    if pg is None:
        pg = OxmlElement("w:pgNumType")
        sectPr.append(pg)
    pg.set(qn("w:fmt"), fmt)
    pg.set(qn("w:start"), str(start))


# ------------------------------------------------------------------ cover page
first = doc.paragraphs[0] if doc.paragraphs else doc.add_paragraph()
first.alignment = WD_ALIGN_PARAGRAPH.CENTER
first.paragraph_format.space_before = Pt(0)
first.paragraph_format.space_after = Pt(10)
first.add_run().add_picture(os.path.join(ASSETS, "bu_anchor.png"), height=Inches(2.35))

centered(front.GROUP_ID, 16, False, before=6, after=14)
mt = doc.add_table(rows=len(front.MEMBERS), cols=2)
mt.alignment = WD_TABLE_ALIGNMENT.CENTER
mt.autofit = False
_lay = OxmlElement("w:tblLayout")
_lay.set(qn("w:type"), "fixed")
mt._tbl.tblPr.append(_lay)
for _gc, _w in zip(mt._tbl.tblGrid.findall(qn("w:gridCol")), (2.05, 3.0)):
    _gc.set(qn("w:w"), str(int(_w * 1440)))
for i, (enr, name) in enumerate(front.MEMBERS):
    c0, c1 = mt.rows[i].cells
    c0.width, c1.width = Inches(2.05), Inches(3.0)
    p0, p1 = c0.paragraphs[0], c1.paragraphs[0]
    for p in (p0, p1):
        para_fmt(p.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, 4, 4, 1.0)
    add_runs(p0, enr, True, 16)
    add_runs(p1, name, False, 16)
centered(front.TITLE, 16, True, before=22, after=26, line=1.15)
centered("In partial fulfilment of the requirements for the degree of", 16, False, after=10, line=1.15)
centered("Bachelor of Science in Computer Science", 16, True, after=14, line=1.15)
centered(f"Supervisor: {front.SUPERVISOR}", 16, False, after=34, line=1.15)
centered("Department of Computer Sciences", 16, False, after=10)
centered("Bahria University, Lahore Campus", 16, False, after=10)
centered(front.COVER_DATE, 16, False, after=0)

# ------------------------------------------------------------------ section 2: front matter (roman)
s2 = doc.add_section(WD_SECTION.NEW_PAGE)
s2.footer.is_linked_to_previous = False
add_footer_page_number(s2, "lowerRoman", 2)

# copyright page
p = centered("© Bahria University, 2026", 12)
para_fmt(p.paragraph_format, WD_ALIGN_PARAGRAPH.CENTER, 330, 0, 1.0)

# certificate
t = doc.add_paragraph("Certificate", style="Front Title")
centered("", 12, after=6)
cp = doc.add_paragraph()
para_fmt(cp.paragraph_format, WD_ALIGN_PARAGRAPH.CENTER, 0, 14, 1.0)
cp.add_run().add_picture(os.path.join(ASSETS, "bu_crest.png"), width=Inches(1.55))
centered("We accept the work contained in the report titled", 12, after=10, line=1.15)
centered(front.TITLE, 12, True, after=10, line=1.15)
centered("written by", 12, after=8, line=1.15)
for _, n in front.MEMBERS:
    centered(n, 12, after=2, line=1.15)
cp = doc.add_paragraph()
para_fmt(cp.paragraph_format, WD_ALIGN_PARAGRAPH.JUSTIFY, 14, 14, 1.5)
cp.add_run("as a confirmation to the required standard for the partial fulfilment of the degree of Bachelor of "
           "Science in Computer Science.")
ap = doc.add_paragraph()
para_fmt(ap.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, 6, 6, 1.15)
ap.add_run("Approved by:")
ap = doc.add_paragraph()
para_fmt(ap.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, 6, 38, 1.15)
ap.add_run(f"Supervisor: {front.SUPERVISOR}")
sig = doc.add_paragraph()
para_fmt(sig.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, 0, 0, 1.0)
sig.paragraph_format.right_indent = Inches(2.6)
pPr = sig._p.get_or_add_pPr()
bd = OxmlElement("w:pBdr")
bt = OxmlElement("w:bottom")
bt.set(qn("w:val"), "single"); bt.set(qn("w:sz"), "6"); bt.set(qn("w:space"), "1"); bt.set(qn("w:color"), "000000")
bd.append(bt); pPr.append(bd)
sl = doc.add_paragraph()
para_fmt(sl.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, 2, 18, 1.0)
r = sl.add_run("(Signature)")
r.font.size = Pt(9)
dp = doc.add_paragraph()
para_fmt(dp.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, 0, 0, 1.15)
add_runs(dp, front.CERT_DATE)

# declaration
doc.add_paragraph("Declaration", style="Front Title")
dec = doc.add_paragraph()
para_fmt(dec.paragraph_format, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 18, 1.5)
dec.add_run("We hereby declare that this project report is based on our original work except for citations and "
            "quotations which have been duly acknowledged. We also declare that it has not been previously and "
            "concurrently submitted for any other degree or award at Bahria University or other institutions.")
dt = doc.add_table(rows=1 + len(front.MEMBERS), cols=3)
dt.alignment = WD_TABLE_ALIGNMENT.CENTER
dt.autofit = False
set_cell_borders(dt)
set_cell_margins(dt, 80, 80, 90, 90)
for ri, row in enumerate([("Enrolment", "Name", "Signature")] + [(e, n, "") for e, n in front.MEMBERS]):
    for ci, val in enumerate(row):
        cell = dt.rows[ri].cells[ci]
        cell.width = Inches((1.7, 2.4, 2.15)[ci])
        par = cell.paragraphs[0]
        par.style = st["Table Text"]
        add_runs(par, val, True if ri == 0 else None, 11)
        if ri > 0:
            par.paragraph_format.space_before = Pt(8)
            par.paragraph_format.space_after = Pt(8)
spacer(10)
dp = doc.add_paragraph()
para_fmt(dp.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, 22, 0, 1.15)
add_runs(dp, "Date: [Date]")

# dedication
doc.add_paragraph("Dedication", style="Front Title")
dd = doc.add_paragraph(front.DEDICATION)
dd.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

# acknowledgements
doc.add_paragraph("Acknowledgements", style="Front Title")
for txt in front.ACK:
    doc.add_paragraph(txt)
for _, n in front.MEMBERS:
    pn = doc.add_paragraph(n)
    para_fmt(pn.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, 0, 0, 1.15)

# abstract
at = doc.add_paragraph(front.TITLE, style="Front Title")
at.runs[0].font.size = Pt(12)
at.paragraph_format.space_after = Pt(6)
ab = doc.add_paragraph("Abstract")
set_font(ab.runs[0], BODY_FONT, 16, True)
para_fmt(ab.paragraph_format, WD_ALIGN_PARAGRAPH.CENTER, 0, 18, 1.15, keep_next=True)
doc.add_paragraph(front.ABSTRACT)

# table of contents
doc.add_paragraph("Table of Contents", style="Front Title")
toc_par = doc.add_paragraph()
toc_par.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
add_field(toc_par, 'TOC \\o "1-3" \\h \\z \\u', "Right-click and choose Update Field to build the table of contents.")

# ------------------------------------------------------------------ section 3: main body (arabic)
s3 = doc.add_section(WD_SECTION.NEW_PAGE)
add_footer_page_number(s3, "decimal", 1)

lot = doc.add_paragraph("List of Tables", style="Front Title")
lot.paragraph_format.page_break_before = False   # the section break already starts a new page
lt = doc.add_paragraph()
lt.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
add_field(lt, 'TOC \\h \\z \\t "Table Caption,1"', "Update field to build the list of tables.")
doc.add_paragraph("List of Figures", style="Front Title")
lf = doc.add_paragraph()
lf.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
add_field(lf, 'TOC \\h \\z \\t "Figure Caption,1"', "Update field to build the list of figures.")

# ------------------------------------------------------------------ body
ref_inserted = False


def insert_references():
    h = doc.add_paragraph("References", style="Heading 1")
    ordered = sorted(cite_numbers.items(), key=lambda kv: kv[1])
    for key, n in ordered:
        p = doc.add_paragraph()
        para_fmt(p.paragraph_format, WD_ALIGN_PARAGRAPH.LEFT, 0, 7, 1.15)
        p.paragraph_format.left_indent = Inches(0.45)
        p.paragraph_format.first_line_indent = Inches(-0.45)
        p.add_run(f"[{n}]\t{REFS[key]}")
        p.paragraph_format.tab_stops.add_tab_stop(Inches(0.45))


chapter_no = 0
for blk in BLOCKS:
    kind = blk[0]
    if kind == "h1" and blk[1] == "Appendices" and not ref_inserted:
        insert_references()
        ref_inserted = True
    if kind == "h1":
        doc.add_paragraph(expand(blk[1]), style="Heading 1")
        m = re.match(r"Chapter (\d+):", blk[1])
        if m:
            chapter_no = int(m.group(1))
    elif kind == "h2":
        doc.add_paragraph(expand(blk[1]), style="Heading 2")
    elif kind == "h3":
        doc.add_paragraph(expand(blk[1]), style="Heading 3")
    elif kind == "p":
        doc.add_paragraph(expand(blk[1]))
    elif kind == "ul":
        for it in blk[1]:
            doc.add_paragraph(expand(it), style="List Bullet")
    elif kind == "ol":
        for n_, it in enumerate(blk[1], 1):
            op = doc.add_paragraph()
            para_fmt(op.paragraph_format, WD_ALIGN_PARAGRAPH.JUSTIFY, 0, 4, 1.5)
            op.paragraph_format.left_indent = Inches(0.4)
            op.paragraph_format.first_line_indent = Inches(-0.3)
            op.paragraph_format.tab_stops.add_tab_stop(Inches(0.4))
            op.add_run(f"{n_}.	{expand(it)}")
    elif kind == "code":
        lines = blk[1].split("\n")
        for i, ln in enumerate(lines):
            cp = doc.add_paragraph(ln if ln else " ", style="Code Block")
            if i == 0:
                cp.paragraph_format.space_before = Pt(4)
            if i == len(lines) - 1:
                cp.paragraph_format.space_after = Pt(10)
            # keep short snippets together
            if len(lines) < 25 and i < len(lines) - 1:
                cp.paragraph_format.keep_with_next = True
    elif kind == "table":
        _, label, caption, header, rows, widths = blk
        num = label_numbers["tbl:" + label]
        cp = doc.add_paragraph(f"Table {num}: {expand(caption)}", style="Table Caption")
        make_table(header, rows, widths)
        spacer(8)
    elif kind == "fig":
        _, label, filename, caption, width = blk
        num = label_numbers["fig:" + label]
        pp = doc.add_paragraph()
        para_fmt(pp.paragraph_format, WD_ALIGN_PARAGRAPH.CENTER, 8, 2, 1.0, keep_next=True)
        pp.add_run().add_picture(os.path.join(FIG, filename), width=Inches(width))
        short = expand(caption).replace("interface render with sample content", "sample render")
        doc.add_paragraph(f"Figure {num}: {short}", style="Figure Caption")
    else:
        raise ValueError(kind)

if not ref_inserted:
    insert_references()

doc.save(OUT)
print("saved", OUT)
print("tables:", sum(1 for k in label_numbers if k.startswith("tbl:")), "figures:",
      sum(1 for k in label_numbers if k.startswith("fig:")), "references:", len(cite_numbers))
