"""Voice-cloning synthesis client + isolated worker manager.

Real zero-shot voice cloning is done by MOSS-TTS-Nano (Apache-2.0, 0.1B params, ONNX,
CPU). It is NOT imported into this process: the upstream project pins torch==2.7.0 /
transformers==4.57.1, which hard-conflict with this backend's torch 2.13 / transformers
5.x stack (installing it here would break RAG embeddings and Whisper). Instead it runs as
an ISOLATED LOCAL WORKER (backend/voice_worker/worker.py) in its own venv, bound to
127.0.0.1 only. This module:

  * launches that worker lazily (first clone request) as a subprocess and terminates it on
    backend shutdown (the worker also watches this process's PID, so it can't leak when
    uvicorn --reload / a hard kill takes the backend down),
  * health-checks it, and
  * calls POST /clone with httpx (reference WAV + text -> 48 kHz stereo WAV bytes).

There is deliberately NO fallback voice: if the worker or its model is unavailable, the
functions here raise CloneUnavailableError and the routes answer 503. Nothing silently
substitutes a stock Piper voice for a "cloned" one.
"""
import atexit
import logging
import os
import subprocess
import threading
import time
from pathlib import Path

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
_MODEL_ROOT = BACKEND_DIR / "models" / "moss-tts-nano"
_WORKER_LOG = BACKEND_DIR / "voice_worker.log"  # covered by the backend/*.log gitignore rule


class CloneUnavailableError(Exception):
    """The worker/model can't be used right now (not set up, not started, crashed, loading timed out)."""


class CloneFailedError(Exception):
    """The worker is up but could not synthesize this request (bad reference audio, etc.)."""


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


def worker_python() -> Path:
    if settings.VOICE_CLONE_WORKER_PYTHON:
        return _resolve(settings.VOICE_CLONE_WORKER_PYTHON)
    sub = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return _MODEL_ROOT / "venv" / sub


def worker_script() -> Path:
    return _resolve(settings.VOICE_CLONE_WORKER_SCRIPT)


def worker_setup_problem() -> str | None:
    """None if the worker is installed; otherwise a human-readable reason."""
    if not worker_python().is_file():
        return "The voice-cloning worker is not set up on this server (see backend/voice_worker/README.md)."
    if not worker_script().is_file():
        return "The voice-cloning worker script is missing on this server."
    if not (_MODEL_ROOT / "repo" / "onnx_tts_runtime.py").is_file():
        return "The MOSS-TTS-Nano runtime is not installed on this server (see backend/voice_worker/README.md)."
    return None


def _base_url() -> str:
    return f"http://127.0.0.1:{settings.VOICE_CLONE_WORKER_PORT}"


def worker_health(timeout: float = 2.0) -> dict | None:
    """The worker's /health payload, or None if nothing is answering."""
    try:
        r = httpx.get(f"{_base_url()}/health", timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except (httpx.HTTPError, ValueError):
        pass
    return None


class _WorkerManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._log_handle = None

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def ensure_started(self) -> None:
        """Make sure a worker process exists (does not wait for the model to load).
        Raises CloneUnavailableError if it can't be launched."""
        problem = worker_setup_problem()
        if problem:
            raise CloneUnavailableError(problem)
        with self._lock:
            if self._alive() or worker_health() is not None:
                return  # ours is running, or an already-healthy worker is bound to the port (adopt it)
            if not settings.VOICE_CLONE_WORKER_AUTOSTART:
                raise CloneUnavailableError("The voice-cloning worker is not running.")
            self._spawn()

    def _spawn(self) -> None:
        cmd = [
            str(worker_python()),
            str(worker_script()),
            "--host", "127.0.0.1",
            "--port", str(settings.VOICE_CLONE_WORKER_PORT),
            "--parent-pid", str(os.getpid()),
        ]
        if settings.VOICE_CLONE_WORKER_THREADS > 0:
            cmd += ["--threads", str(settings.VOICE_CLONE_WORKER_THREADS)]
        kwargs: dict = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            self._log_handle = open(_WORKER_LOG, "ab")
            self._proc = subprocess.Popen(
                cmd, cwd=str(BACKEND_DIR), stdout=self._log_handle, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, **kwargs,
            )
        except OSError as exc:
            self._proc = None
            raise CloneUnavailableError(f"Could not start the voice-cloning worker: {exc}") from exc
        logger.info("Started voice-cloning worker pid=%s port=%s", self._proc.pid, settings.VOICE_CLONE_WORKER_PORT)

    def wait_ready(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            health = worker_health()
            if health is not None:
                if health.get("status") == "ready":
                    return
                if health.get("status") == "error":
                    raise CloneUnavailableError(f"Voice model failed to load: {health.get('error')}")
            elif self._proc is not None and self._proc.poll() is not None:
                raise CloneUnavailableError(
                    f"The voice-cloning worker exited during startup (code {self._proc.returncode}); see voice_worker.log."
                )
            time.sleep(1.0)
        raise CloneUnavailableError("The voice model is still loading. Please try again in a minute.")

    def shutdown(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            logger.info("Stopping voice-cloning worker pid=%s", proc.pid)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self._log_handle:
            try:
                self._log_handle.close()
            except OSError:
                pass


_manager = _WorkerManager()
atexit.register(_manager.shutdown)


def load_clone_model() -> None:
    """Startup hook: log whether cloning is installed. Does not spawn the worker (lazy)."""
    problem = worker_setup_problem()
    if problem:
        logger.warning("Voice cloning unavailable: %s", problem)
    else:
        logger.info("Voice cloning worker installed; it will start on the first clone request.")


def shutdown_clone_worker() -> None:
    _manager.shutdown()


def prepare_worker() -> None:
    """Called by the clone-request route: start the worker if needed. Raises
    CloneUnavailableError if it isn't installed or can't be launched."""
    _manager.ensure_started()


def wait_for_worker() -> None:
    _manager.ensure_started()
    _manager.wait_ready(float(settings.VOICE_CLONE_WORKER_LOAD_TIMEOUT_SECONDS))


def synthesize_cloned_speech(text: str, reference_wav: bytes) -> bytes:
    """WAV bytes (48 kHz, 2-channel, 16-bit as produced by MOSS-TTS-Nano) of `text` spoken in
    the voice of `reference_wav`. Blocks (CPU-bound on the worker) — call from a thread.
    Raises CloneUnavailableError / CloneFailedError; never returns a substitute voice."""
    _manager.ensure_started()
    _manager.wait_ready(float(settings.VOICE_CLONE_WORKER_LOAD_TIMEOUT_SECONDS))
    try:
        resp = httpx.post(
            f"{_base_url()}/clone",
            files={"audio": ("reference.wav", reference_wav, "audio/wav")},
            data={"text": text},
            timeout=httpx.Timeout(float(settings.VOICE_CLONE_REQUEST_TIMEOUT_SECONDS), connect=5.0),
        )
    except httpx.HTTPError as exc:
        raise CloneUnavailableError(f"Lost contact with the voice-cloning worker ({type(exc).__name__}).") from exc
    if resp.status_code == 503:
        raise CloneUnavailableError("The voice model is not ready.")
    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("detail", "")
        except ValueError:
            pass
        raise CloneFailedError(f"Voice generation failed ({resp.status_code}): {detail}"[:300])
    return resp.content
