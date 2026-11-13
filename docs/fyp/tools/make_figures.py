"""Draws the report's diagrams (architecture, use cases, pipelines, ER) as PNG files.

All sizes are in "logical" pixels for a 1800 px wide figure (about 6.25 in at 288 dpi) and are
drawn at 2x then reduced, so edges stay sharp when the figure is placed in the report. Text is
never smaller than ~30 logical px (about 7.5 pt in print).

Usage:  python make_figures.py <output-dir>
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SS = 2  # supersampling
FONT_DIR = "C:/Windows/Fonts/"
INK = (16, 24, 40)
MUTED = (82, 96, 118)
LINE = (120, 132, 152)
WHITE = (255, 255, 255)

# (fill, stroke)
BLUE = ((234, 241, 255), (47, 95, 208))
GREEN = ((232, 246, 238), (30, 142, 78))
AMBER = ((255, 244, 224), (199, 119, 0))
PURPLE = ((241, 235, 255), (107, 70, 193))
GRAY = ((242, 244, 247), (102, 112, 133))
ROSE = ((255, 236, 238), (190, 52, 70))


def font(size, bold=False):
    name = "calibrib.ttf" if bold else "calibri.ttf"
    return ImageFont.truetype(FONT_DIR + name, int(size * SS))


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * SS, h * SS), WHITE)
        self.d = ImageDraw.Draw(self.img)

    # -- primitives (logical coordinates) -------------------------------------------------
    def _s(self, v):
        return int(round(v * SS))

    def rect(self, x, y, w, h, colors=GRAY, radius=14, width=3, fill=True):
        f, s = colors
        self.d.rounded_rectangle(
            [self._s(x), self._s(y), self._s(x + w), self._s(y + h)],
            radius=self._s(radius), fill=f if fill else None, outline=s, width=self._s(width),
        )

    def text(self, x, y, s, size=30, bold=False, color=INK, anchor="la"):
        self.d.text((self._s(x), self._s(y)), s, font=font(size, bold), fill=color, anchor=anchor)

    def text_w(self, s, size=30, bold=False):
        return self.d.textlength(s, font=font(size, bold)) / SS

    def wrap(self, s, max_w, size=30, bold=False):
        words, lines, cur = s.split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if self.text_w(t, size, bold) <= max_w or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def center_text(self, cx, cy, s, size=30, bold=False, color=INK, max_w=None, leading=1.18):
        lines = self.wrap(s, max_w, size, bold) if max_w else s.split("\n")
        total = len(lines) * size * leading
        y = cy - total / 2
        for ln in lines:
            self.text(cx, y, ln, size, bold, color, anchor="ma")
            y += size * leading

    def line(self, pts, color=LINE, width=3, dash=None):
        p = [(self._s(x), self._s(y)) for x, y in pts]
        if dash:
            for (x1, y1), (x2, y2) in zip(p, p[1:]):
                dist = math.hypot(x2 - x1, y2 - y1)
                n = max(1, int(dist / self._s(dash[0] + dash[1])))
                for i in range(n):
                    a = i / n
                    b = a + (dash[0] / (dash[0] + dash[1])) / n
                    self.d.line([(x1 + (x2 - x1) * a, y1 + (y2 - y1) * a), (x1 + (x2 - x1) * b, y1 + (y2 - y1) * b)],
                                fill=color, width=self._s(width))
        else:
            self.d.line(p, fill=color, width=self._s(width), joint="curve")

    def arrow(self, pts, color=LINE, width=3, head=16, both=False, dash=None):
        self.line(pts, color, width, dash)

        def head_at(p_from, p_to):
            (x1, y1), (x2, y2) = p_from, p_to
            ang = math.atan2(y2 - y1, x2 - x1)
            a1, a2 = ang + math.radians(150), ang - math.radians(150)
            tri = [(x2, y2), (x2 + head * math.cos(a1), y2 + head * math.sin(a1)),
                   (x2 + head * math.cos(a2), y2 + head * math.sin(a2))]
            self.d.polygon([(self._s(x), self._s(y)) for x, y in tri], fill=color)

        head_at(pts[-2], pts[-1])
        if both:
            head_at(pts[1], pts[0])

    def ellipse(self, cx, cy, rx, ry, colors=BLUE, width=3):
        f, s = colors
        self.d.ellipse([self._s(cx - rx), self._s(cy - ry), self._s(cx + rx), self._s(cy + ry)],
                       fill=f, outline=s, width=self._s(width))

    def actor(self, cx, top, label, size=30):
        r = 20
        self.d.ellipse([self._s(cx - r), self._s(top), self._s(cx + r), self._s(top + 2 * r)], outline=INK, width=self._s(3))
        self.line([(cx, top + 2 * r), (cx, top + 100)], INK, 3)
        self.line([(cx - 36, top + 66), (cx + 36, top + 66)], INK, 3)
        self.line([(cx, top + 100), (cx - 30, top + 150)], INK, 3)
        self.line([(cx, top + 100), (cx + 30, top + 150)], INK, 3)
        self.center_text(cx, top + 185, label, size, True)

    def save(self, path):
        out = self.img.resize((self.w, self.h), Image.LANCZOS)
        out.save(path, optimize=True)
        print("wrote", path, out.size)


def box(c, x, y, w, h, title, lines=(), colors=GRAY, title_size=32, line_size=28, head_h=None):
    """Panel with a bold title and optional lines of small text."""
    c.rect(x, y, w, h, colors)
    c.center_text(x + w / 2, y + (head_h or 48) / 2 + 6, title, title_size, True, max_w=w - 24)
    yy = y + (head_h or 48) + 14
    for ln in lines:
        for sub in c.wrap(ln, w - 36, line_size):
            c.text(x + w / 2, yy, sub, line_size, False, MUTED, anchor="ma")
            yy += line_size * 1.22
        yy += 3


# =========================================================================================
def fig_architecture(path):
    c = Canvas(1800, 1250)
    c.text(900, 22, "EchoLearn: system architecture", 40, True, anchor="ma")

    # clients
    c.rect(40, 90, 1720, 210, BLUE, 18)
    c.text(62, 100, "CLIENT TIER", 26, True, BLUE[1])
    for i, (t, s) in enumerate([("Web application", "Next.js 16, React 19, Tailwind CSS"),
                                ("Mobile application", "Flutter (Android / iOS / web)"),
                                ("Admin console", "Next.js, /admin routes")]):
        box(c, 70 + i * 570, 140, 520, 130, t, [s], (WHITE, BLUE[1]), 32, 28)

    c.arrow([(900, 300), (900, 360)], LINE, 4, both=True)
    c.text(918, 316, "HTTPS, JSON, server-sent events, JWT bearer token", 28, False, MUTED)

    # API tier
    c.rect(40, 360, 1720, 290, GREEN, 18)
    c.text(62, 370, "APPLICATION TIER: FastAPI (Python 3.11)", 26, True, GREEN[1])
    mods = ["Auth and users", "Documents and folders", "Chats and RAG", "Quizzes and review",
            "Study plans", "Tutor mode", "Voice (TTS / STT)", "Admin, plans, moderation"]
    for i, m in enumerate(mods):
        col, row = i % 4, i // 4
        c.rect(70 + col * 428, 410 + row * 92, 398, 76, (WHITE, GREEN[1]), 12)
        c.center_text(70 + col * 428 + 199, 410 + row * 92 + 38, m, 30, True, max_w=370)
    c.text(70, 598, "Cross-cutting: JWT auth, bcrypt hashing, CORS, rate limiting, per-plan quotas, API-call logging",
           28, False, MUTED)

    # arrows down
    c.arrow([(300, 650), (300, 720)], LINE, 4, both=True)
    c.arrow([(900, 650), (900, 720)], LINE, 4, both=True)
    c.arrow([(1500, 650), (1500, 720)], LINE, 4, both=True)

    # data tier
    c.rect(40, 720, 1100, 250, AMBER, 18)
    c.text(62, 730, "DATA TIER", 26, True, AMBER[1])
    box(c, 70, 775, 330, 170, "PostgreSQL", ["32 tables", "users, documents, chats, study data"], (WHITE, AMBER[1]), 30, 26)
    box(c, 425, 775, 330, 170, "Vector store", ["Chroma (local) or", "Qdrant Cloud, 384-dim"], (WHITE, AMBER[1]), 30, 26)
    box(c, 780, 775, 330, 170, "File storage", ["Original files, parsed text,", "audio cache"], (WHITE, AMBER[1]), 30, 26)

    # AI tier
    c.rect(1180, 720, 580, 250, PURPLE, 18)
    c.text(1202, 730, "AI SERVICES", 26, True, PURPLE[1])
    box(c, 1205, 775, 270, 170, "Groq API", ["gpt-oss-120b", "gpt-oss-20b"], (WHITE, PURPLE[1]), 30, 26)
    box(c, 1490, 775, 245, 170, "Gemini", ["fallback model"], (WHITE, PURPLE[1]), 30, 26)

    # local models + background workers
    c.rect(40, 1000, 1720, 150, GRAY, 18)
    c.text(62, 1018, "LOCAL MODELS AND BACKGROUND WORK (run inside the backend process)", 26, True, GRAY[1])
    items = ["fastembed MiniLM-L6\n(embeddings)", "faster-whisper base\n(speech to text)",
             "Piper\n(text to speech)", "RapidOCR\n(scanned pages)"]
    for i, t in enumerate(items):
        c.rect(70 + i * 428, 1046, 398, 86, (WHITE, GRAY[1]), 12)
        c.center_text(70 + i * 428 + 199, 1089, t, 27, False)

    c.text(900, 1190, "Deployment: frontend on Vercel, backend on Render, PostgreSQL on Neon, vectors on Qdrant Cloud",
           28, False, MUTED, anchor="ma")
    c.save(path)


def fig_usecases(path):
    c = Canvas(1800, 1530)
    c.rect(330, 40, 1140, 1400, ((252, 252, 253), LINE), 16, 3)
    c.text(900, 56, "EchoLearn", 36, True, anchor="ma")

    student = [
        "Register, verify email, log in",
        "Upload files or paste a video link",
        "Organise folders and workspaces",
        "Ask questions and read cited answers",
        "Use voice input and listen to answers",
        "Get explanations in Urdu / Roman Urdu",
        "Generate quizzes and diagrams",
        "Review flashcards (spaced repetition)",
        "Follow a day-by-day study plan",
        "Learn with the guided tutor",
        "Make revision sheets and practice papers",
        "View learning analytics and usage",
    ]
    admin = [
        "Manage users and block accounts",
        "Edit plans and per-user limits",
        "Moderate reported content",
        "Monitor system health and storage",
        "Change platform configuration",
    ]
    ys = [130 + i * 112 for i in range(len(student))]
    for y, t in zip(ys, student):
        c.ellipse(660, y + 40, 270, 46, BLUE)
        c.center_text(660, y + 40, t, 28, False, max_w=500)
    ya = [200 + i * 190 for i in range(len(admin))]
    for y, t in zip(ya, admin):
        c.ellipse(1190, y + 40, 235, 52, GREEN)
        c.center_text(1190, y + 40, t, 28, False, max_w=430)

    c.actor(150, 560, "Student")
    c.actor(1645, 560, "Admin")
    for y in ys:
        c.line([(180, 640), (390, y + 40)], LINE, 2)
    for y in ya:
        c.line([(1620, 640), (1425, y + 40)], LINE, 2)
    c.text(900, 1470, "Administrators can also use every student feature.", 28, False, MUTED, anchor="ma")
    c.save(path)


def fig_ingestion(path):
    c = Canvas(1800, 540)
    c.text(900, 18, "Document ingestion pipeline", 38, True, anchor="ma")
    steps = [
        ("1. Upload", "File or video URL;\ntype and size checked\nagainst the plan", BLUE),
        ("2. Parse", "PDF, DOCX, PPTX,\nTXT, CSV, images;\nOCR for scans", GREEN),
        ("3. Transcribe", "Audio and video via\nfaster-whisper, with\ntimestamps", GREEN),
        ("4. Chunk", "Roughly 1000 chars,\n150 overlap; tables\nkept whole", AMBER),
        ("5. Embed", "MiniLM-L6 gives a\n384-number vector\nper chunk", PURPLE),
        ("6. Index", "Vectors stored with\ndocument, page and\nuser metadata", AMBER),
    ]
    bw, gap = 250, 42
    x0 = (1800 - (6 * bw + 5 * gap)) / 2
    for i, (t, s_, col) in enumerate(steps):
        x = x0 + i * (bw + gap)
        c.rect(x, 105, bw, 270, col, 16)
        c.center_text(x + bw / 2, 145, t, 32, True, max_w=bw - 20)
        c.center_text(x + bw / 2, 255, s_, 26, False, MUTED)
        if i < 5:
            c.arrow([(x + bw + 5, 240), (x + bw + gap - 5, 240)], INK, 4, head=13)
    c.text(900, 415, "Afterwards a short summary and suggested questions are generated, so the document is ready to chat with.",
           27, False, MUTED, anchor="ma")
    c.text(900, 462, "Status moves through: uploaded, parsing, embedded, ready (or failed).", 27, False, MUTED, anchor="ma")
    c.save(path)


def fig_rag(path):
    c = Canvas(1800, 720)
    c.text(900, 18, "Question-answering pipeline", 38, True, anchor="ma")
    top = [
        ("Question", "typed or spoken", GRAY),
        ("Understand", "standalone rewrite;\nextra phrasings", PURPLE),
        ("Retrieve", "meaning + keyword +\nnumber lookup", AMBER),
        ("Grade", "is the context\nrelevant?", PURPLE),
        ("Answer", "grounded, with\npage citations", GREEN),
    ]
    bw, gap = 300, 55
    x0 = (1800 - (5 * bw + 4 * gap)) / 2
    centers = []
    for i, (t, s_, col) in enumerate(top):
        x = x0 + i * (bw + gap)
        centers.append(x + bw / 2)
        c.rect(x, 90, bw, 200, col, 16)
        c.center_text(x + bw / 2, 132, t, 34, True, max_w=bw - 20)
        c.center_text(x + bw / 2, 222, s_, 28, False, MUTED)
        if i < 4:
            c.arrow([(x + bw + 5, 190), (x + bw + gap - 5, 190)], INK, 4, head=14)

    # Retrieve detail (under columns 1-3)
    c.arrow([(centers[2], 290), (centers[2], 370)], AMBER[1], 4, head=14)
    c.rect(40, 370, 1000, 300, (WHITE, AMBER[1]), 14)
    c.text(540, 384, "Hybrid retrieval", 31, True, anchor="ma")
    bullets = ["Dense search for each phrasing of the question (vectors)",
               "BM25 keyword search over every chunk of the chat's documents",
               "Reference lookup: a cited number such as 240 is matched to the marker [240]",
               "Rank fusion, then the text that continues onto the next page is added"]
    for i, ln in enumerate(bullets):
        c.text(70, 440 + i * 56, "- " + ln, 27, False, MUTED)

    # Not-relevant branch (under Grade)
    c.arrow([(centers[3], 290), (centers[3], 370)], ROSE[1], 4, head=14)
    c.rect(1070, 370, 370, 170, ROSE, 14)
    c.center_text(1255, 455, "Not relevant:\nsay so and show\nno sources", 28, False)

    # Answer detail (under Answer)
    c.arrow([(centers[4], 290), (centers[4], 370)], GREEN[1], 4, head=14)
    c.rect(1470, 370, 290, 170, (WHITE, GREEN[1]), 14)
    c.center_text(1615, 455, "Follow-up questions\nand citations\nreturned", 28, False)
    c.save(path)


def fig_er(path):
    c = Canvas(1800, 1860)
    c.text(900, 14, "Entity relationship diagram (core tables)", 38, True, anchor="ma")

    def table(x, y, name, fields, colors, w=300):
        h = 60 + 36 * len(fields) + 10
        c.rect(x, y, w, h, colors, 10, 3)
        c.d.rectangle([c._s(x), c._s(y), c._s(x + w), c._s(y + 52)], fill=colors[1])
        size = 31 if c.text_w(name, 31, True) < w - 20 else 26
        c.text(x + w / 2, y + (7 if size == 31 else 11), name, size, True, WHITE, anchor="ma")
        for i, f in enumerate(fields):
            c.text(x + 16, y + 62 + i * 36, f, 26, False, INK)
        return (x, y, w, h)

    top, bottom = 110, 1700
    mid = (top + bottom) / 2
    ux, uw, uh = 40, 330, 8 * 36 + 70
    table(ux, mid - uh / 2, "users", ["id (PK)", "name, email", "password_hash", "is_verified, is_admin", "plan_id (FK)",
                                      "custom_limits", "is_blocked", "preferred_language"], BLUE, uw)
    bus_x = 420
    c.line([(bus_x, top + 30), (bus_x, bottom - 40)], BLUE[1], 5)
    c.line([(ux + uw, mid), (bus_x, mid)], BLUE[1], 5)

    rows = [
        (110, [("document_folders", ["id (PK)", "user_id (FK)", "name"], GRAY),
               ("documents", ["id (PK)", "user_id, folder_id", "filename, file_type", "status, page_count", "summary"], AMBER),
               ("chat_documents", ["chat_id (FK)", "document_id (FK)"], GRAY),
               ("chats", ["id (PK)", "user_id (FK)", "workspace_id (FK)", "title"], GREEN)]),
        (440, [("workspaces", ["id (PK)", "user_id (FK)", "name"], GRAY),
               ("workspace_documents", ["workspace_id (FK)", "document_id (FK)"], GRAY),
               ("messages", ["id (PK)", "chat_id (FK)", "role, content", "citations (JSON)"], GREEN),
               ("query_logs", ["id (PK)", "user_id, chat_id", "question", "was_answered"], GRAY)]),
        (770, [("quizzes", ["id (PK)", "user_id (FK)", "document_ids", "questions (JSON)"], PURPLE),
               ("quiz_attempts", ["id (PK)", "quiz_id, user_id", "answers, score"], PURPLE),
               ("review_cards", ["id (PK)", "user_id, document_id", "question, answer"], PURPLE),
               ("review_card_states", ["review_card_id", "ease_factor", "interval_days", "next_review_date"], PURPLE)]),
        (1100, [("study_plans", ["id (PK)", "user_id (FK)", "exam_date", "daily_study_minutes"], GREEN),
                ("study_sessions", ["id (PK)", "plan_id, quiz_id", "scheduled_date", "topic_title, status"], GREEN),
                ("tutor_sessions", ["id (PK)", "user_id (FK)", "topic, level", "plan, status"], ROSE),
                ("tutor_turns", ["id (PK)", "session_id (FK)", "role, turn_type", "hint_level, verdict"], ROSE)]),
        (1430, [("past_papers", ["id (PK)", "user_id, document_id", "extracted_pattern"], AMBER),
                ("practice_papers", ["id (PK)", "user_id (FK)", "pattern_config", "generated_content"], AMBER),
                ("practice_paper_attempts", ["id (PK)", "paper_id, user_id", "answers, score"], AMBER),
                ("revision_sheets", ["id (PK)", "user_id (FK)", "topics, language", "content, pdf_path"], AMBER)]),
    ]
    gx0, step, bw = 480, 330, 285
    pos = {}
    for (y, items) in rows:
        for i, (name, fields, col) in enumerate(items):
            pos[name] = table(gx0 + i * step, y, name, fields, col, bw)
        c.line([(bus_x, y + 26), (gx0, y + 26)], BLUE[1], 4)

    def link(a, b, label=""):
        ax, ay, aw, ah = pos[a]
        bx, by, bw_, bh = pos[b]
        c.arrow([(ax + aw + 2, ay + 26), (bx - 2, by + 26)], INK, 3, head=12)
        if label:
            c.text((ax + aw + bx) / 2, ay + 34, label, 22, False, MUTED, anchor="ma")

    link("document_folders", "documents", "1..*")
    link("documents", "chat_documents", "1..*")
    link("chat_documents", "chats", "*..1")
    link("workspaces", "workspace_documents", "1..*")
    link("quizzes", "quiz_attempts", "1..*")
    link("review_cards", "review_card_states", "1..1")
    link("study_plans", "study_sessions", "1..*")
    link("tutor_sessions", "tutor_turns", "1..*")
    link("past_papers", "practice_papers", "")
    link("practice_papers", "practice_paper_attempts", "1..*")

    c.text(40, 1790, "Not drawn: plans, usage_events, api_call_logs, auth_tokens, content_reports, admin_audit_logs, system_config,",
           25, False, MUTED)
    c.text(40, 1822, "rate_limit_violations, voice_clone_jobs, message_translations, tutor_concept_states. Every user-owned table carries user_id.",
           25, False, MUTED)
    c.save(path)


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    fig_architecture(os.path.join(out, "fig_architecture.png"))
    fig_usecases(os.path.join(out, "fig_usecases.png"))
    fig_ingestion(os.path.join(out, "fig_ingestion.png"))
    fig_rag(os.path.join(out, "fig_rag.png"))
    fig_er(os.path.join(out, "fig_er.png"))
