"""Isolated local voice-cloning worker (MOSS-TTS-Nano, ONNX, CPU).

Why this is a separate process: the upstream project pins torch==2.7.0 /
transformers==4.57.1 which conflict with the main backend's stack (torch 2.13 /
transformers 5.x). Installing it into the backend venv would break RAG
embeddings and Whisper, so it lives in its own venv and talks HTTP on
127.0.0.1 only.

Run with the worker venv's python:
    backend/models/moss-tts-nano/venv/Scripts/python.exe backend/voice_worker/worker.py --port 8765

API
    GET  /health  -> {"status": "loading"|"ready"|"error", ...}
    POST /clone   -> multipart: audio=<reference file>, text=<str> -> audio/wav (48 kHz stereo 16-bit)

Upstream code (backend/models/moss-tts-nano/repo) is used UNMODIFIED. The only
deviation from upstream defaults is enable_wetext=False: WeTextProcessing needs
pynini which is not pip-installable on Windows; the upstream runtime imports it
lazily and treats it as optional, so its built-in "robust" normalizer is used.
Long text is chunked by the upstream runtime (75-token budget, sentence aware)
and the chunks are concatenated with short pauses at the codec sample rate.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

HERE = Path(__file__).resolve().parent
DEFAULT_REPO = HERE.parent / "models" / "moss-tts-nano" / "repo"

log = logging.getLogger("voice_worker")

_state: dict = {"status": "loading", "error": None, "load_seconds": None, "runtime": None}
_infer_lock = threading.Lock()  # one inference at a time (CPU bound, sessions not thread-safe)
_codes_cache: "OrderedDict[str, list]" = OrderedDict()  # reference sha256 -> encoded prompt codes
_CODES_CACHE_MAX = 8
MAX_TEXT_CHARS = 2000
MAX_REF_BYTES = 20 * 1024 * 1024


def _watch_parent(pid: int) -> None:
    """Exit when the launching backend dies (covers uvicorn --reload / hard kills)."""
    if pid <= 0:
        return
    if os.name == "nt":
        import ctypes

        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        handle = k32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            log.warning("parent pid %s not found; exiting", pid)
            os._exit(0)
        k32.WaitForSingleObject(handle, 0xFFFFFFFF)  # blocks until the parent exits
        log.info("parent process exited; shutting down worker")
        os._exit(0)
    while True:
        try:
            os.kill(pid, 0)
        except OSError:
            os._exit(0)
        time.sleep(2)


def _load_runtime(repo_dir: Path, model_dir: str | None, threads: int) -> None:
    t0 = time.time()
    try:
        sys.path.insert(0, str(repo_dir))
        os.chdir(repo_dir)  # upstream resolves some paths relative to the repo
        from onnx_tts_runtime import OnnxTtsRuntime  # type: ignore

        runtime = OnnxTtsRuntime(model_dir=model_dir, thread_count=threads, max_new_frames=375,
                                 do_sample=True, sample_mode="fixed", execution_provider="cpu")
        _state["runtime"] = runtime
        _state["load_seconds"] = round(time.time() - t0, 2)
        _state["status"] = "ready"
        log.info("MOSS-TTS-Nano ready in %.1fs", _state["load_seconds"])
    except Exception as exc:  # noqa: BLE001
        log.exception("failed to load MOSS-TTS-Nano")
        _state["status"] = "error"
        _state["error"] = f"{type(exc).__name__}: {exc}"


def _rss_mb() -> float | None:
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = ctypes.c_void_p
            ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
            ctypes.windll.psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
            return round(pmc.WorkingSetSize / 1048576, 1)
        import resource

        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:  # noqa: BLE001
        return None


def build_app():
    app = FastAPI(title="EchoLearn voice worker", docs_url=None, redoc_url=None)

    @app.get("/health")
    def health():
        return {"status": _state["status"], "error": _state["error"],
                "load_seconds": _state["load_seconds"], "rss_mb": _rss_mb(),
                "model": "MOSS-TTS-Nano-100M-ONNX"}

    # Sync def -> FastAPI runs it in a threadpool, so /health stays responsive during inference.
    @app.post("/clone")
    def clone(audio: UploadFile = File(...), text: str = Form(...)):
        if _state["status"] == "loading":
            raise HTTPException(503, "Model is still loading")
        if _state["status"] != "ready":
            raise HTTPException(503, f"Model unavailable: {_state['error']}")
        text = (text or "").strip()
        if not text:
            raise HTTPException(400, "text is empty")
        if len(text) > MAX_TEXT_CHARS:
            raise HTTPException(400, f"text too long (max {MAX_TEXT_CHARS} chars)")
        data = audio.file.read(MAX_REF_BYTES + 1)
        if not data or len(data) > MAX_REF_BYTES:
            raise HTTPException(400, "reference audio missing or too large")

        runtime = _state["runtime"]
        ref_hash = hashlib.sha256(data).hexdigest()
        suffix = Path(audio.filename or "ref.wav").suffix or ".wav"
        t0 = time.time()
        with tempfile.TemporaryDirectory(prefix="vw_") as tmp:
            ref_path = Path(tmp) / f"ref{suffix}"
            ref_path.write_bytes(data)
            out_path = Path(tmp) / "out.wav"
            with _infer_lock:
                try:
                    codes = _codes_cache.get(ref_hash)
                    if codes is None:
                        codes = runtime.encode_reference_audio(ref_path)
                        _codes_cache[ref_hash] = codes
                        while len(_codes_cache) > _CODES_CACHE_MAX:
                            _codes_cache.popitem(last=False)
                    else:
                        _codes_cache.move_to_end(ref_hash)
                    # Reuse cached reference codes (instance-level override; upstream file untouched).
                    orig = runtime.resolve_prompt_audio_codes
                    runtime.resolve_prompt_audio_codes = lambda **_kw: codes
                    try:
                        result = runtime.synthesize(
                            text=text, prompt_audio_path=str(ref_path), output_audio_path=str(out_path),
                            sample_mode="fixed", do_sample=True, streaming=True,
                            voice_clone_max_text_tokens=75, enable_wetext=False,
                            enable_normalize_tts_text=True)
                    finally:
                        runtime.resolve_prompt_audio_codes = orig
                except Exception as exc:  # noqa: BLE001
                    log.exception("clone failed")
                    raise HTTPException(422, f"Could not synthesize: {type(exc).__name__}: {exc}")
            wav_bytes = out_path.read_bytes()
        elapsed = time.time() - t0
        log.info("clone ok chars=%d chunks=%d out_bytes=%d elapsed=%.1fs", len(text),
                 len(result.get("text_chunks", [])), len(wav_bytes), elapsed)
        return Response(content=wav_bytes, media_type="audio/wav",
                        headers={"X-Elapsed-Ms": str(int(elapsed * 1000)),
                                 "X-Sample-Rate": str(result["sample_rate"])})

    return app


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--repo-dir", default=str(DEFAULT_REPO))
    ap.add_argument("--model-dir", default=None, help="ONNX model dir (default: <repo>/models, auto-downloaded)")
    ap.add_argument("--threads", type=int, default=max(2, (os.cpu_count() or 4) // 2))
    ap.add_argument("--parent-pid", type=int, default=0)
    args = ap.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        sys.exit("worker refuses to bind to non-loopback addresses")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    repo = Path(args.repo_dir).resolve()
    if not (repo / "onnx_tts_runtime.py").is_file():
        sys.exit(f"MOSS-TTS-Nano repo not found at {repo}. Run voice_worker/setup_worker.ps1 first.")
    if args.parent_pid:
        threading.Thread(target=_watch_parent, args=(args.parent_pid,), daemon=True).start()
    threading.Thread(target=_load_runtime, args=(repo, args.model_dir, args.threads), daemon=True).start()
    import uvicorn

    uvicorn.run(build_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
