# Voice-cloning worker (MOSS-TTS-Nano)

Real zero-shot voice cloning for the "My Voice" option, running fully locally on CPU with
[MOSS-TTS-Nano](https://github.com/OpenMOSS/MOSS-TTS-Nano) (Apache-2.0, 0.1B parameters, ONNX).

## Why a separate process and venv

Upstream pins `torch==2.7.0` and `transformers==4.57.1`. The main backend runs torch 2.13 /
transformers 5.x / numpy 2.x for RAG embeddings and Whisper, so installing MOSS into the
backend venv would break them. The worker therefore runs in its own venv
(`backend/models/moss-tts-nano/venv`) and exposes a tiny HTTP API on `127.0.0.1` only:

- `GET /health` -> `{"status": "loading"|"ready"|"error", ...}`
- `POST /clone` (multipart `audio` = reference WAV, `text`) -> `audio/wav` (48 kHz, stereo, 16-bit)

The backend (`app/voice/clone_model.py`) starts the worker lazily on the first clone request,
health-checks it, and stops it when the backend exits (the worker also exits by itself if the
backend process disappears, e.g. under `uvicorn --reload`). Nothing runs unless someone uses
"My Voice".

## One-time setup

From the repo root, with any Python 3.11 (validated) or 3.12:

```bash
python backend/voice_worker/setup_worker.py
```

This creates the venv, installs `requirements-worker.txt` (+ CPU torch), clones the upstream
repo at a pinned commit into `backend/models/moss-tts-nano/repo`, and downloads ~700 MB of ONNX
weights from Hugging Face (`OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX`,
`OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX`). `backend/models/` is gitignored.
Use `--skip-weights` to let the worker download them on first start instead.

Without setup, the app works normally; "My Voice" answers HTTP 503 ("voice-cloning worker is not
set up") and the default Piper voice is unaffected. There is no fallback voice.

## Settings (`backend/.env`)

`VOICE_CLONE_WORKER_PORT` (8765), `VOICE_CLONE_WORKER_PYTHON`, `VOICE_CLONE_WORKER_SCRIPT`,
`VOICE_CLONE_WORKER_AUTOSTART` (true), `VOICE_CLONE_WORKER_THREADS` (0 = half the cores).

## Deviations from upstream (no upstream file is modified)

- **WeTextProcessing is disabled** (`enable_wetext=False`). It needs `pynini`, which is not
  pip-installable on Windows. Upstream imports it lazily and treats it as optional; the built-in
  "robust" text normalizer still runs. Effect: numerals/abbreviations are read less smartly.
- **Transformers is not installed** (only needed by upstream's PyTorch path, not the ONNX path).
- The worker caches encoded reference-audio codes (LRU of 8) per reference-file hash.
- Long text is chunked by upstream (75-token, sentence-aware budget), chunks are joined with short
  pauses. Reference audio must be WAV (the Settings page converts recordings/uploads in the browser).

## Manual test

```bash
backend/models/moss-tts-nano/venv/Scripts/python.exe backend/voice_worker/worker.py --port 8765
curl -F audio=@ref.wav -F "text=Hello there." http://127.0.0.1:8765/clone -o out.wav
```
