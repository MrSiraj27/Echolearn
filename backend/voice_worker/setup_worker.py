"""One-time setup for the isolated voice-cloning worker (MOSS-TTS-Nano, ONNX, CPU).

    python backend/voice_worker/setup_worker.py            # from the repo root, any Python 3.11/3.12
    python backend/voice_worker/setup_worker.py --skip-weights   # skip the ~700 MB model download

Creates backend/models/moss-tts-nano/venv (gitignored), installs the pinned worker
dependencies there (NEVER into the main backend venv), clones the upstream repo at a
pinned commit into backend/models/moss-tts-nano/repo, and downloads the ONNX weights.
Re-running is safe (each step is skipped if already done). Verified on Windows 10,
Python 3.11, CPU only. No upstream code is patched.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "models" / "moss-tts-nano"
VENV = ROOT / "venv"
REPO = ROOT / "repo"
REPO_URL = "https://github.com/OpenMOSS/MOSS-TTS-Nano"
REPO_COMMIT = "8b7bcc9341b3b4ef3a3a58ba1338a7d85ff133eb"  # the commit this worker was validated against
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(cmd: list[str], **kw) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-weights", action="store_true")
    args = ap.parse_args()

    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        print(f"Warning: validated on Python 3.11 (3.12 is documented upstream); you have {sys.version.split()[0]}.")
    ROOT.mkdir(parents=True, exist_ok=True)

    if not VENV_PY.is_file():
        run([sys.executable, "-m", "venv", VENV])
    run([VENV_PY, "-m", "pip", "install", "-q", "-U", "pip"])
    # CPU-only torch/torchaudio (upstream pins 2.7.0); used only to load+resample the reference audio.
    run([VENV_PY, "-m", "pip", "install", "-q", "torch==2.7.0", "torchaudio==2.7.0",
         "--index-url", "https://download.pytorch.org/whl/cpu"])
    run([VENV_PY, "-m", "pip", "install", "-q", "-r", HERE / "requirements-worker.txt"])

    if not (REPO / "onnx_tts_runtime.py").is_file():
        run(["git", "clone", REPO_URL, REPO])
    run(["git", "-C", REPO, "checkout", "-q", REPO_COMMIT])

    if args.skip_weights:
        print("Skipping weights; the worker downloads them on first start instead.")
    else:
        code = ("import sys; sys.path.insert(0, '.'); "
                "from onnx_tts_runtime import ensure_browser_onnx_model_dir as e; print('weights at', e())")
        run([VENV_PY, "-c", code], cwd=REPO)
    print("\nDone. Start the backend as usual; the worker launches on the first 'My Voice' request.")
    print(f"Manual test:  {VENV_PY} {HERE / 'worker.py'} --port 8765")


if __name__ == "__main__":
    main()
