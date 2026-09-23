"""Voice-cloning synthesis client — backed by the Fish Audio API (api.fish.audio).

Previously this ran MOSS-TTS-Nano as an isolated local worker process (its own venv,
CPU-bound inference). That worked, but needed real RAM/CPU no free hosting tier has to
spare (~130-180MB just for the model, plus real inference time on a throttled CPU) — it's
why voice cloning was local-dev-only on the deployed site. Fish Audio's `s2.1-pro-free`
API model has no hard usage cap under fair use and needs no card, so cloning now works
identically wherever the backend runs, with zero local memory/CPU cost: two HTTP calls
(create a voice model from the reference clip, then synthesize with it) instead of a
subprocess.

There is deliberately NO fallback voice: if the API key isn't configured or a call fails,
the functions here raise CloneUnavailableError/CloneFailedError and the routes answer 503.
Nothing silently substitutes a stock voice for a "cloned" one.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

FISH_API_BASE = "https://api.fish.audio"
FISH_MODEL_HEADER = "s2.1-pro-free"  # no hard usage cap under Fish Audio's fair-use policy


class CloneUnavailableError(Exception):
    """The API isn't usable right now (not configured, auth/quota problem, unreachable)."""


class CloneFailedError(Exception):
    """The API is reachable but could not synthesize this request (bad reference audio, etc.)."""


def worker_setup_problem() -> str | None:
    """None if voice cloning is usable; otherwise a human-readable reason. Named
    worker_setup_problem for compatibility with the route/schema code that calls it."""
    if not settings.FISH_AUDIO_API_KEY:
        return "Voice cloning isn't configured on this server (FISH_AUDIO_API_KEY is not set)."
    return None


def load_clone_model() -> None:
    """Startup hook: log whether cloning is configured."""
    problem = worker_setup_problem()
    if problem:
        logger.warning("Voice cloning unavailable: %s", problem)
    else:
        logger.info("Voice cloning configured (Fish Audio API).")


def shutdown_clone_worker() -> None:
    """No-op now — kept so app/main.py's lifespan doesn't need to change."""


def prepare_worker() -> None:
    """Called by the clone-request route before queuing a job. Raises
    CloneUnavailableError if the API key isn't configured."""
    problem = worker_setup_problem()
    if problem:
        raise CloneUnavailableError(problem)


def _headers(extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {settings.FISH_AUDIO_API_KEY}"}
    if extra:
        h.update(extra)
    return h


def _raise_for_response(resp: httpx.Response, context: str) -> None:
    if resp.status_code == 200 or resp.status_code == 201:
        return
    detail = ""
    try:
        body = resp.json()
        detail = body.get("message") or body.get("reason") or str(body)
    except ValueError:
        detail = resp.text[:300]
    if resp.status_code in (401, 402, 429, 503):
        raise CloneUnavailableError(f"Fish Audio {context} unavailable ({resp.status_code}): {detail}"[:300])
    raise CloneFailedError(f"Fish Audio {context} failed ({resp.status_code}): {detail}"[:300])


def create_fish_voice_model(reference_wav: bytes) -> str:
    """Uploads a reference clip and returns a Fish Audio model id (`reference_id`) that
    can be reused for many synthesize_via_fish calls without re-uploading the sample.
    train_mode="fast" makes the model usable immediately (no async training wait)."""
    try:
        resp = httpx.post(
            f"{FISH_API_BASE}/model",
            headers=_headers(),
            data={"type": "tts", "title": "EchoLearn cloned voice", "train_mode": "fast", "visibility": "private"},
            files={"voices": ("reference.wav", reference_wav, "audio/wav")},
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
    except httpx.HTTPError as exc:
        raise CloneUnavailableError(f"Could not reach Fish Audio ({type(exc).__name__}).") from exc
    _raise_for_response(resp, "model creation")
    return resp.json()["_id"]


def synthesize_via_fish(text: str, reference_id: str) -> bytes:
    """WAV bytes of `text` spoken in the voice identified by `reference_id`."""
    try:
        resp = httpx.post(
            f"{FISH_API_BASE}/v1/tts",
            headers=_headers({"model": FISH_MODEL_HEADER, "Content-Type": "application/json"}),
            json={"text": text, "reference_id": reference_id, "format": "wav"},
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
    except httpx.HTTPError as exc:
        raise CloneUnavailableError(f"Could not reach Fish Audio ({type(exc).__name__}).") from exc
    _raise_for_response(resp, "speech synthesis")
    return resp.content


def synthesize_cloned_speech(text: str, reference_wav: bytes) -> bytes:
    """Convenience one-shot path (create a model then synthesize) for callers that don't
    need to cache the model id across calls. The cached path in clone_background.py
    (which reuses a stored reference_id across requests) is preferred in production."""
    reference_id = create_fish_voice_model(reference_wav)
    return synthesize_via_fish(text, reference_id)
