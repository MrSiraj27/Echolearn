"""Captures real screenshots of the running app (local test user) for the report figures.

Prereqs: backend on :8000, frontend on :3000, backend/scripts/seed_test_user.py run, and the MML
book uploaded as that user (evidence/mml_ingest.json). Uses the installed Chrome via Playwright.
Run from backend/:  python ../docs/fyp/tools/capture_ui.py
"""
import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.getcwd())
from scripts.seed_test_user import TEST_EMAIL  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.security import create_access_token, create_refresh_token  # noqa: E402
from app.models import User  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(os.path.dirname(HERE), "figures")
API, WEB = "http://localhost:8000", "http://localhost:3000"
DOC = json.load(open(os.path.join(os.path.dirname(HERE), "evidence", "mml_ingest.json")))["document_id"]


def api(path, body=None, token=None, method=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method or ("POST" if body is not None else "GET"),
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read().decode()
    return raw


def prepare_chat(token: str) -> str:
    """A chat about the MML book with one cited answer and one 'not in the document' answer."""
    chat = json.loads(api("/chats/", {"document_ids": [DOC], "title": "Mathematics for Machine Learning"}, token))
    for q in ["What is an eigenvalue and eigenvector? Explain simply.", "What does the book say about ChatGPT?"]:
        raw = api(f"/chats/{chat['id']}/message", {"content": q}, token)  # streams; read to the end
        if "ran into an error" in raw:
            api(f"/chats/{chat['id']}", token=token, method="DELETE")
            print("model unavailable (chat):", q, raw[-600:]); sys.exit(3)
        time.sleep(65)  # free tier: 8,000 tokens per minute
    return chat["id"]


ONLY = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None


def want(name: str) -> bool:
    return ONLY is None or name in ONLY


def main():
    # Tokens are minted locally for the seeded test user, so repeated runs never hit the login rate limit.
    user = SessionLocal().query(User).filter(User.email == TEST_EMAIL).one()
    token = create_access_token(user.id, user.email)
    session_cookie = [{"name": "refresh_token", "value": create_refresh_token(user.id), "domain": "localhost",
                       "path": "/auth", "httpOnly": True, "secure": True, "sameSite": "None"}]
    # Session hint for the app, and hide the Next.js development indicator so it is not in the figures.
    hint = ("localStorage.setItem('echolearn_had_session', '1');"
            "document.addEventListener('DOMContentLoaded', () => { const s = document.createElement('style');"
            "s.textContent = 'nextjs-portal { display: none !important; }'; document.head.appendChild(s); });")
    chat_id = prepare_chat(token) if want("chat") else None
    os.makedirs(FIG, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="light")
        ctx.add_cookies(session_cookie)
        ctx.add_init_script(hint)
        page = ctx.new_page()
        page.goto(WEB + "/dashboard")
        page.wait_for_url("**/dashboard", timeout=30000)
        page.wait_for_timeout(3500)

        def shot(name, full=False):
            page.wait_for_timeout(1200)
            page.screenshot(path=os.path.join(FIG, name), full_page=full)
            print("saved", name)

        # Dashboard
        if want("dashboard"):
            shot("ui_dashboard.png")

        # Reader with an explanation of a selected term
        if want("reader"):
            reader(page, shot)
        if want("documents"):
            page.goto(WEB + "/documents")
            page.wait_for_timeout(3500)
            shot("ui_documents.png")
        if want("chat"):
            chat(page, shot, chat_id)
        if want("rest"):
            rest(page, shot, browser, session_cookie, hint)
        browser.close()


def reader(page, shot):
        page.goto(f"{WEB}/read/{DOC}?page=53")
        page.wait_for_selector("article", timeout=30000)
        page.wait_for_timeout(2500)
        page.evaluate("""() => {
          const a = document.querySelector('article'); const w = document.createTreeWalker(a, NodeFilter.SHOW_TEXT);
          let n; while ((n = w.nextNode())) { const i = n.textContent.search(/linearly independent/i);
            if (i !== -1) { const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 'linearly independent'.length);
              getSelection().removeAllRanges(); getSelection().addRange(r); a.dispatchEvent(new MouseEvent('mouseup', {bubbles: true})); return; } }
        }""")
        page.wait_for_timeout(500)
        btn = page.get_by_role("button", name="Explain with AI")
        if btn.count():
            btn.first.click()
            page.wait_for_timeout(14000)
        if page.get_by_text("didn't respond").count() or page.get_by_text("Couldn't produce").count():
            print("model unavailable (explain)"); sys.exit(3)
        shot("ui_reader_explain.png")


def chat(page, shot, chat_id):
        page.goto(f"{WEB}/chat/{chat_id}")
        page.wait_for_timeout(5000)
        src = page.get_by_role("button", name="Sources")
        if src.count():
            src.first.click()
        page.wait_for_timeout(800)
        page.evaluate("() => { const s = document.querySelector('main .overflow-y-auto'); if (s) s.scrollTop = 0; }")
        shot("ui_chat_cited.png")
        page.evaluate("() => { const s = document.querySelector('main .overflow-y-auto'); if (s) s.scrollTop = s.scrollHeight; }")
        shot("ui_chat_notfound_new.png")


def rest(page, shot, browser, session_cookie, hint):
        # Quizzes, Tutor start, Voice recorder
        page.goto(WEB + "/quizzes"); page.wait_for_timeout(3000); shot("ui_quizzes.png")
        page.goto(WEB + "/tutor"); page.wait_for_timeout(3000); shot("ui_tutor_start.png")
        page.goto(WEB + "/settings#voice"); page.wait_for_timeout(3000); shot("ui_voice_settings.png")

        # Phone view of the dashboard
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
        mobile.add_cookies(session_cookie)
        mobile.add_init_script(hint)
        mp = mobile.new_page()
        mp.goto(WEB + "/dashboard"); mp.wait_for_timeout(4500)
        mp.screenshot(path=os.path.join(FIG, "ui_mobile.png")); print("saved ui_mobile.png")


if __name__ == "__main__":
    main()
