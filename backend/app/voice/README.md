# Voice (Piper TTS) setup

EchoLearn's "Listen" feature uses [Piper](https://github.com/rhasspy/piper) for
self-hosted, natural-sounding text-to-speech — no browser TTS, no cloud API cost.

## One-time setup: download the voice model

The model is **not** downloaded at runtime — fetch it once during setup/deploy:

```bash
mkdir -p backend/voices
curl -L -o backend/voices/en_US-lessac-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
curl -L -o backend/voices/en_US-lessac-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
```

Point `VOICE_MODEL_PATH` in `.env` at the `.onnx` file (the matching `.onnx.json`
config is expected alongside it, same path + `.json`). Other pre-trained Piper
voices work the same way — swap the filename to try a different one from the
[piper-voices](https://huggingface.co/rhasspy/piper-voices) repo.

If the model file is missing, the app **does not crash** — it logs a warning at
startup and `/voice/speak` returns `503` until the file is in place, so the rest
of the app keeps working.

## Deployment note: free-tier hosting

Piper runs in-process by default (`VOICE_BACKEND=local`) and needs the ONNX
model loaded in memory plus CPU for inference — on Render/Railway's free tier
this can be tight alongside the rest of the API (embeddings model, FastAPI,
Postgres connections).

If it's too heavy there, split it out:

1. Deploy Piper as its own service — a Hugging Face Space works well. Several
   ready-made "Piper TTS" Spaces already exist, or build a minimal one that
   wraps the same `synthesize_speech()` logic behind a small FastAPI/gradio
   app exposing `POST /synthesize` (body `{"text": "..."}`, returns raw WAV
   bytes).
2. Set `VOICE_BACKEND=hf_space` and `VOICE_HF_SPACE_URL=https://your-space-url`
   in the backend's env vars.

No frontend or route changes are needed to switch — `/voice/speak` stays the
same contract either way; only where the actual synthesis happens changes.
