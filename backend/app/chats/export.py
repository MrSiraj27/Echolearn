import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, HRFlowable

from app.models import Chat, Message


def _format_citations_md(citations: list[dict] | None) -> str:
    if not citations:
        return ""
    lines = []
    for c in citations:
        page = f", p. {c['page_number']}" if c.get("page_number") else ""
        lines.append(f"  - {c.get('filename', 'unknown')}{page}")
    return "\n" + "\n".join(lines)


def build_markdown(chat: Chat, messages: list[Message], document_filenames: list[str]) -> str:
    lines = [
        f"# {chat.title or 'Untitled chat'}",
        "",
        f"*Exported from EchoLearn on {datetime.now().strftime('%B %d, %Y')}*",
        "",
    ]
    if document_filenames:
        lines.append("**Source document(s):** " + ", ".join(document_filenames))
        lines.append("")
    lines.append("---")
    lines.append("")

    for message in messages:
        speaker = "You" if message.role.value == "user" else "EchoLearn"
        lines.append(f"**{speaker}:** {message.content}")
        if message.role.value == "assistant" and message.citations:
            lines.append(f"\n*Sources:*{_format_citations_md(message.citations)}")
        lines.append("")

    return "\n".join(lines)


def build_pdf(chat: Chat, messages: list[Message], document_filenames: list[str]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        title=chat.title or "EchoLearn chat export",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ChatTitle", parent=styles["Title"], fontSize=20, spaceAfter=4, textColor=colors.HexColor("#111111")
    )
    meta_style = ParagraphStyle(
        "Meta", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#888888"), spaceAfter=16
    )
    user_style = ParagraphStyle(
        "UserMsg",
        parent=styles["Normal"],
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#111111"),
        spaceBefore=10,
        spaceAfter=4,
    )
    assistant_style = ParagraphStyle(
        "AssistantMsg",
        parent=styles["Normal"],
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#222222"),
        spaceBefore=10,
        spaceAfter=4,
    )
    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#999999"), spaceAfter=2
    )
    citation_style = ParagraphStyle(
        "Citation", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#999999"), leftIndent=12
    )

    def esc(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    elements = [
        Paragraph(esc(chat.title or "Untitled chat"), title_style),
        Paragraph(
            f"Exported from EchoLearn on {datetime.now().strftime('%B %d, %Y')}"
            + (f" &nbsp;·&nbsp; Source: {esc(', '.join(document_filenames))}" if document_filenames else ""),
            meta_style,
        ),
        HRFlowable(width="100%", color=colors.HexColor("#e5e5e5"), thickness=1, spaceAfter=14),
    ]

    for message in messages:
        is_user = message.role.value == "user"
        elements.append(Paragraph("You" if is_user else "EchoLearn", label_style))
        elements.append(Paragraph(esc(message.content).replace("\n", "<br/>"), user_style if is_user else assistant_style))
        if not is_user and message.citations:
            for c in message.citations:
                page = f", p. {c['page_number']}" if c.get("page_number") else ""
                elements.append(Paragraph(f"— {esc(c.get('filename', 'unknown'))}{page}", citation_style))

    def add_page_number(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#aaaaaa"))
        canvas.drawRightString(LETTER[0] - 0.75 * inch, 0.5 * inch, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()
