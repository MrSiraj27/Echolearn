# EchoLearn

A RAG (Retrieval-Augmented Generation) document-chat platform. Upload documents
(PDF, DOCX, audio/video, etc.), chat with them, generate quizzes/diagrams/
infographics, and listen to answers read aloud — all grounded in your own files.

- **Frontend**: Next.js 16 + React 19 + Tailwind (`frontend/`)
- **Backend**: FastAPI + SQLAlchemy + Postgres + Chroma (`backend/`)

## Quick start (one command)

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
- **[Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)** (for
  scanned image/PDF text extraction).
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

## Deploying to production

See [DEPLOYMENT.md](DEPLOYMENT.md) for Render/Railway (backend), Vercel
(frontend), and Supabase/Neon (database) setup.

## Repo layout

```
backend/    FastAPI app, Alembic migrations, RAG pipeline
frontend/   Next.js app (user-facing + admin panel)
scripts/    Cross-platform setup/launch helpers used by npm at the root
```
