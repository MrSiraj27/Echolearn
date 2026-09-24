"""Async job processing for voice cloning — same FastAPI BackgroundTasks pattern as
app/documents/background.py.

The actual synthesis is a remote Fish Audio API call now (see clone_model.py), not a
local CPU-bound worker, so there's no local resource to serialize access to — multiple
clone jobs can run concurrently without contention.

Billing: a UsageEvent("voice_clone_use") is written ONLY after a job is confirmed
successful (valid, non-silent WAV saved), in the same transaction that marks the job
done. Quota is still enforced at request time in clone_routes.py by counting
queued/processing jobs as pending, so users can't queue unlimited work.
"""
import hashlib
import io
import logging
import time
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import User, UsageEvent, VoiceCloneJob, VoiceCloneJobStatus
from app.voice.clone_model import (
    CloneFailedError,
    CloneUnavailableError,
    create_fish_voice_model,
    synthesize_via_fish,
)

logger = logging.getLogger(__name__)


def sample_path(user_id: uuid.UUID) -> Path:
    path = Path(settings.STORAGE_PATH) / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path / "voice_sample.wav"


def output_path(user_id: uuid.UUID, job_id: uuid.UUID) -> Path:
    path = Path(settings.STORAGE_PATH) / str(user_id) / "clones"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{job_id}.wav"


def validate_wav_output(data: bytes) -> tuple[int, int, float]:
    """Parse the WAV and sanity-check it. Returns (sample_rate, channels, seconds).
    Raises ValueError for malformed / empty / all-silent audio.

    Duration is computed from the actual PCM bytes read, not the header's declared frame
    count: Fish Audio's API streams its response, so that field is a bogus placeholder
    (observed: a few seconds of real audio reporting as ~13.5 hours) — harmless for
    playback (players read actual bytes, not the declared size) but useless for logging."""
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            rate, ch, framesize = w.getframerate(), w.getnchannels(), w.getsampwidth() * w.getnchannels()
            pcm = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"not a valid WAV: {exc}") from exc
    if rate <= 0 or framesize <= 0 or not pcm:
        raise ValueError("empty audio")
    if not pcm.strip(b"\x00"):
        raise ValueError("silent audio")
    actual_frames = len(pcm) / framesize
    return rate, ch, actual_frames / float(rate)


def _fail(db: Session, job: VoiceCloneJob, message: str, started: float | None = None) -> None:
    job.status = VoiceCloneJobStatus.failed
    job.error_message = message
    if started is not None:
        job.duration_ms = (time.perf_counter() - started) * 1000
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


def process_clone_job(job_id: uuid.UUID, text: str) -> None:
    """`text` is the already-cleaned, already-truncated text — passed in by the route
    (the job may outlive its message: message_id is SET NULL) and committed to by
    the cache key's text_hash."""
    db: Session = SessionLocal()
    try:
        job = db.query(VoiceCloneJob).filter(VoiceCloneJob.id == job_id).first()
        if not job:
            logger.error("VoiceCloneJob %s not found for processing", job_id)
            return
        job.status = VoiceCloneJobStatus.processing
        db.commit()

        try:
            user = db.query(User).filter(User.id == job.user_id).first()
            if not user:
                _fail(db, job, "Your account could not be found.")
                return
            if user.cloned_voice_sample_hash != job.reference_audio_hash:
                _fail(db, job, "Your voice sample changed while this was queued. Please try again.")
                return

            started = time.perf_counter()
            # Reuse the cached Fish Audio voice model for this sample if one already exists
            # (cleared to None whenever the sample is replaced/deleted — see clone_routes.py).
            # Fish Audio keeps the model on its own servers, so this doesn't depend on the
            # local reference WAV still being on disk — Render's filesystem is ephemeral and
            # wipes it on every restart/idle-spindown, well before the Fish model expires.
            reference_id = user.fish_voice_model_id
            if not reference_id:
                ref_file = sample_path(job.user_id)
                if not ref_file.is_file():
                    _fail(db, job, "Your voice sample is missing. Please upload it again in Settings.")
                    return
                ref_bytes = ref_file.read_bytes()
                if hashlib.sha256(ref_bytes).hexdigest() != job.reference_audio_hash:
                    _fail(db, job, "Your voice sample changed while this was queued. Please try again.")
                    return
                reference_id = create_fish_voice_model(ref_bytes)
                user.fish_voice_model_id = reference_id
                db.commit()
            audio_bytes = synthesize_via_fish(text, reference_id)
            elapsed_ms = (time.perf_counter() - started) * 1000

            try:
                rate, channels, seconds = validate_wav_output(audio_bytes)
            except ValueError as exc:
                logger.error("Clone job %s produced unusable audio: %s", job_id, exc)
                _fail(db, job, "Voice generation produced no usable audio. Please try again.", started)
                return

            out = output_path(job.user_id, job.id)
            out.write_bytes(audio_bytes)

            job.status = VoiceCloneJobStatus.done
            job.output_audio_path = str(out)
            job.duration_ms = elapsed_ms
            job.completed_at = datetime.now(timezone.utc)
            db.add(UsageEvent(user_id=job.user_id, event_type="voice_clone_use"))  # charge on success only
            db.commit()
            logger.info("Clone job %s done: %.1fs audio (%d Hz, %d ch) in %.1fs", job_id, seconds, rate, channels, elapsed_ms / 1000)
        except CloneUnavailableError as exc:
            logger.warning("Clone job %s: worker unavailable: %s", job_id, exc)
            db.rollback()
            _fail(db, job, str(exc))
        except CloneFailedError as exc:
            logger.error("Clone job %s failed: %s", job_id, exc)
            db.rollback()
            _fail(db, job, "Voice generation failed. Please try again.")
        except Exception:
            logger.exception("Voice clone job %s failed", job_id)
            db.rollback()
            _fail(db, job, "Voice generation failed. Please try again.")
    finally:
        db.close()


def fail_interrupted_jobs() -> int:
    """Startup hook: BackgroundTasks don't survive a restart, so any job still queued/
    processing belongs to a dead process. Mark them failed so they stop counting as
    pending work against the user's quota. (Assumes a single backend process.)"""
    db = SessionLocal()
    try:
        rows = (
            db.query(VoiceCloneJob)
            .filter(VoiceCloneJob.status.in_([VoiceCloneJobStatus.queued, VoiceCloneJobStatus.processing]))
            .all()
        )
        for job in rows:
            job.status = VoiceCloneJobStatus.failed
            job.error_message = "Interrupted by a server restart. Please try again."
            job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return len(rows)
    except Exception:
        logger.exception("Could not clean up interrupted clone jobs")
        db.rollback()
        return 0
    finally:
        db.close()
