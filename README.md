# EchoLearn

A RAG (Retrieval-Augmented Generation) document-chat platform. Upload documents
(PDF, DOCX, audio/video, etc.), chat with them, generate quizzes/diagrams/
infographics, and listen to answers read aloud — all grounded in your own files.

- **Frontend**: Next.js 16 + React 19 + Tailwind (`frontend/`)
- **Backend**: FastAPI + SQLAlchemy + Postgres + Chroma (`backend/`)

## Run it on Windows (one double-click)

Double-click **`setup.bat`** once. It installs Python, Node.js and PostgreSQL if
needed, creates the database, asks for your Groq/Gemini keys and your login, and
starts the app. After that, double-click **`start.bat`**. Full steps:
**[HOW-TO-RUN.md](HOW-TO-RUN.md)**.

## Quick start (manual, any OS)

```bash
npm install
```

Run from the repo root, this installs the frontend's `node_modules` **and**
sets up the backend automatically (creates a Python virtualenv, installs the
pinned `requirements.txt`, and copies `.env.example` → `.env` / `.env.local`
in both projects if they don't already exist). See `scripts/setup.mjs` for
exactly what it does.

You still need to do a few things by hand afterward, since they require real
credentials or external installs that can't be automated:

### 1. Prerequisites

- **Python 3.11+** and **Node.js 18+** on your PATH.
- **PostgreSQL** running locally (or a free hosted instance — see
  [DEPLOYMENT.md](DEPLOYMENT.md)).
- OCR for scanned PDFs and images uses **RapidOCR** (installed with the Python
  requirements; no system Tesseract needed).
- **[FFmpeg](https://ffmpeg.org)** (for audio/video parsing) — either on your
  PATH or pointed to via `FFMPEG_PATH` in `backend/.env`.
- A free **[Groq](https://console.groq.com)** API key and a free
  **[Gemini](https://aistudio.google.com/apikey)** API key (fallback LLM).

### 2. Fill in `backend/.env`

`npm install` already created this file from `backend/.env.example` — open it
and fill in at least:

```
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<database>
JWT_SECRET=<any long random string>
GROQ_API_KEY=<your key>
GEMINI_API_KEY=<your key>
TESSERACT_CMD=<path to tesseract, if not on PATH>
FFMPEG_PATH=<path to ffmpeg, if not on PATH>
```

`RESEND_API_KEY` is optional — without it, verification/reset emails just
won't send, but the rest of the app works fine.

### 3. Create the database and run migrations

```bash
cd backend
venv\Scripts\python -m alembic upgrade head      # Windows
venv/bin/python -m alembic upgrade head          # macOS/Linux
```

### 4. (Optional) Voice model for text-to-speech

Not downloaded automatically — it's 100MB+. See
[backend/app/voice/README.md](backend/app/voice/README.md) for the one-time
download command. Without it, the app still runs; `/voice/speak` just returns
503 until the model is in place.

### 4b. Voice cloning (optional)

"My Voice" reads answers in a voice cloned from a 3-20 s sample of yours, via the
[Fish Audio](https://fish.audio) API (no local model, no GPU/CPU cost — works the same on
any host). Sign up free (no card), grab an API key, and set:

```
FISH_AUDIO_API_KEY=...
```

in `backend/.env`. If you skip this, the app runs normally and "My Voice" reports that
voice cloning is unavailable (HTTP 503); the default voice is unaffected. Cloning also
needs a plan/limit with `voice_clone_uses_per_day` above 0.

### 5. Run both servers

From the repo root:

```bash
npm run dev:backend     # in one terminal — FastAPI on :8000
npm run dev:frontend    # in another terminal — Next.js on :3000
```

Then open http://localhost:3000.

### 6. Create an admin account (optional)

```bash
cd backend
venv\Scripts\python scripts\create_admin.py you@example.com --role superadmin   # Windows
venv/bin/python scripts/create_admin.py you@example.com --role superadmin      # macOS/Linux
```

Log in at http://localhost:3000/admin/login.

### 7. (Optional) A local test account

```bash
cd backend
venv\Scripts\python scripts\seed_test_user.py      # Windows
venv/bin/python scripts/seed_test_user.py          # macOS/Linux
```

Creates (or resets) a verified throwaway account whose email and password are in
`scripts/seed_test_user.py`. It refuses to run unless `DATABASE_URL` points at localhost.

## Features at a glance

- **Documents**: upload PDF, DOCX, PPTX, TXT, CSV, images, audio/video, or a video link.
  Processing runs in the background (`uploaded → parsing → embedded → ready`, or `failed`).
  A failed document shows *why* (password-protected PDF, damaged file, no readable text,
  indexing failure, interrupted by a restart) and can be retried from the sidebar. Documents
  can be renamed, moved to folders, searched and deleted.
- **Reader** (`/read/<documentId>`): page-by-page text of any processed document, with page
  list, detected sections, find-in-document, zoom, reading progress and keyboard shortcuts
  (←/→ pages, Ctrl/Cmd+F find, E to explain a selection, Esc to close). PDFs also have an
  **Original** view (the browser's own PDF viewer). Chat citations open the reader on the cited page.
- **Explain with AI**: select a word, sentence, passage, formula or code in the reader. The
  explanation uses the text around the selection plus related passages from the same
  document, adapts to the kind of selection, and supports follow-up questions. Only text is
  sent to the model; images and diagrams inside documents are not explained.
- **Chat**: grounded answers with page citations, follow-ups, copy, regenerate, and
  helpful / not helpful / report-incorrect feedback (reviewable by admins at
  `GET /admin/system/feedback`).
- **Voice**: answers read aloud; optional voice cloning from a sample you **record in the
  browser** (pause/resume, live waveform, preview before upload) or upload. Uploading a
  sample requires confirming it is your own voice or that you have permission (enforced by
  the API, not only the UI).

## Running the tests

```bash
cd backend
venv\Scripts\python -m unittest discover -s tests -v      # Windows
venv/bin/python -m unittest discover -s tests -v          # macOS/Linux
```

The backend tests need no database, network or API keys (a few HTTP checks are skipped
unless the API is running on :8000). For the frontend:

```bash
cd frontend
npx tsc --noEmit
npm run lint
npm run build
```

## Deploying to production

See [DEPLOYMENT.md](DEPLOYMENT.md) for Render/Railway (backend), Vercel
(frontend), and Supabase/Neon (database) setup.

## Repo layout

```
backend/    FastAPI app, Alembic migrations, RAG pipeline
frontend/   Next.js app (user-facing + admin panel)
scripts/    Cross-platform setup/launch helpers used by npm at the root
```
