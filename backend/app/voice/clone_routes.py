import hashlib
import io
import logging
import threading
import uuid
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.limits import get_effective_limits
from app.core.security import get_current_user
from app.core.usage import enforce_quota
from app.documents.storage import sanitize_filename
from app.models import Chat, Message, User, VoiceCloneJob, VoiceCloneJobStatus
from app.voice.clone_background import process_clone_job, sample_path
from app.voice.clone_model import CloneUnavailableError, prepare_worker, worker_setup_problem
from app.voice.clone_schemas import (
    TEXT_HARD_CAP,
    CloneRequestBody,
    CloneRequestResponse,
    CloneStatusResponse,
    PregenerateBody,
    SampleInfoResponse,
)
from app.voice.text_cleanup import clean_text_for_speech

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice-clone"])

MIN_SAMPLE_SECONDS = 3
MAX_SAMPLE_SECONDS = 20
MAX_SAMPLE_UPLOAD_MB = 15
# Queued/processing jobs older than this are assumed dead and stop counting as pending quota.
PENDING_JOB_MAX_AGE = timedelta(minutes=15)

# Serialises "check quota + create job" so two simultaneous requests can't both slip past a
# limit of 1 (single backend process).
_request_lock = threading.Lock()


def _wav_info(content: bytes) -> tuple[float, int, int]:
    """(duration_seconds, sample_rate, channels) of a PCM WAV; raises ValueError otherwise."""
    try:
        with wave.open(io.BytesIO(content), "rb") as wav_file:
            rate = wav_file.getframerate()
            if rate <= 0 or wav_file.getnframes() <= 0:
                raise ValueError("empty")
            return wav_file.getnframes() / float(rate), rate, wav_file.getnchannels()
    except (wave.Error, EOFError) as exc:
        raise ValueError(str(exc)) from exc


@router.post("/upload-sample")
async def upload_sample(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if len(content) > MAX_SAMPLE_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Sample must be under {MAX_SAMPLE_UPLOAD_MB}MB.")

    try:
        duration, _rate, _channels = _wav_info(content)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The voice sample must be a standard WAV file (the Settings page converts recordings and uploads automatically).",
        )
    if not (MIN_SAMPLE_SECONDS <= duration <= MAX_SAMPLE_SECONDS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reference audio must be between {MIN_SAMPLE_SECONDS} and {MAX_SAMPLE_SECONDS} seconds long (got {duration:.1f}s).",
        )

    safe_name = sanitize_filename(file.filename or "voice_sample.wav")
    sample_path(current_user.id).write_bytes(content)

    current_user.cloned_voice_sample_hash = hashlib.sha256(content).hexdigest()
    db.commit()

    logger.info("Voice sample uploaded for user %s (file %s, %.1fs)", current_user.id, safe_name, duration)
    return {"has_sample": True}


@router.get("/sample", response_model=SampleInfoResponse)
def get_sample_info(current_user: User = Depends(get_current_user)):
    return SampleInfoResponse(
        has_sample=bool(current_user.cloned_voice_sample_hash), pregenerate=bool(current_user.voice_pregenerate)
    )


@router.patch("/pregenerate")
def set_pregenerate(
    payload: PregenerateBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.voice_pregenerate = payload.enabled
    db.commit()
    return {"pregenerate": current_user.voice_pregenerate}


@router.get("/sample/audio")
def get_sample_audio(current_user: User = Depends(get_current_user)):
    """The caller's own stored sample, for the Settings preview player."""
    path = sample_path(current_user.id)
    if not current_user.cloned_voice_sample_hash or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No voice sample uploaded.")
    return Response(content=path.read_bytes(), media_type="audio/wav", headers={"Cache-Control": "private, no-store"})


@router.delete("/sample")
def delete_sample(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    path = sample_path(current_user.id)
    if path.exists():
        path.unlink()
    current_user.cloned_voice_sample_hash = None
    db.commit()
    return {"has_sample": False}


def _pending_jobs_query(db: Session, user: User):
    cutoff = datetime.now(timezone.utc) - PENDING_JOB_MAX_AGE
    return db.query(VoiceCloneJob).filter(
        VoiceCloneJob.user_id == user.id,
        VoiceCloneJob.status.in_([VoiceCloneJobStatus.queued, VoiceCloneJobStatus.processing]),
        VoiceCloneJob.created_at >= cutoff,
    )


@router.post("/clone-request", response_model=CloneRequestResponse)
def clone_request(
    payload: CloneRequestBody,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return enqueue_clone(db, current_user, payload.message_id, background_tasks.add_task)


def pregenerate_clone(user_id: uuid.UUID, message_id: uuid.UUID) -> None:
    """Fire-and-forget clone of a fresh assistant reply for users who enabled pre-generation.
    Runs in its own thread/session; every failure (quota, no worker, no sample) is silent —
    the user simply gets the normal on-demand flow when they press Listen."""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.voice_pregenerate or not user.cloned_voice_sample_hash:
            return
        # Run the job inline: this thread is already off the request path.
        enqueue_clone(db, user, str(message_id), lambda fn, *args: fn(*args))
    except HTTPException as exc:
        logger.info("Voice pre-generation skipped for user %s: %s", user_id, exc.detail)
    except Exception:
        logger.exception("Voice pre-generation failed for user %s", user_id)
    finally:
        db.close()


def enqueue_clone(db: Session, current_user: User, message_id: str, schedule) -> CloneRequestResponse:
    payload = CloneRequestBody(message_id=message_id)
    if not current_user.cloned_voice_sample_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a voice sample first (Settings → Voice Cloning) before requesting a cloned reading.",
        )

    try:
        message_uuid = uuid.UUID(payload.message_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message_id.")

    # Only the chat owner may have a message read aloud (404, not 403, so ids don't leak).
    message = (
        db.query(Message)
        .join(Chat, Chat.id == Message.chat_id)
        .filter(Message.id == message_uuid, Chat.user_id == current_user.id)
        .first()
    )
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    cleaned = clean_text_for_speech(message.content)
    truncated = False
    if len(cleaned) > TEXT_HARD_CAP:
        cleaned = cleaned[:TEXT_HARD_CAP].rsplit(" ", 1)[0] + "... (truncated)"
        truncated = True
    if not cleaned:
        cleaned = "There's nothing to read here."

    text_hash = hashlib.sha256(cleaned.encode()).hexdigest()
    reference_hash = current_user.cloned_voice_sample_hash

    matching = db.query(VoiceCloneJob).filter(
        VoiceCloneJob.user_id == current_user.id,
        VoiceCloneJob.reference_audio_hash == reference_hash,
        VoiceCloneJob.text_hash == text_hash,
    )

    # Cache hit: no new job, no quota use, and no worker needed.
    existing_done = (
        matching.filter(VoiceCloneJob.status == VoiceCloneJobStatus.done)
        .order_by(VoiceCloneJob.completed_at.desc())
        .first()
    )
    if existing_done and existing_done.output_audio_path and Path(existing_done.output_audio_path).exists():
        return CloneRequestResponse(
            status="done", job_id=str(existing_done.id), audio_url=f"/voice/clone-audio/{existing_done.id}", truncated=truncated
        )

    limits = get_effective_limits(current_user)
    if limits.get("voice_clone_uses_per_day") == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voice cloning isn't included in your plan. Upgrade to unlock it.",
        )

    with _request_lock:
        # Same request already in flight: reuse it (no second job, no extra pending count).
        in_flight = (
            _pending_jobs_query(db, current_user)
            .filter(
                VoiceCloneJob.reference_audio_hash == reference_hash,
                VoiceCloneJob.text_hash == text_hash,
            )
            .first()
        )
        if in_flight:
            return CloneRequestResponse(status="queued", job_id=str(in_flight.id), truncated=truncated)

        # Quota is enforced now (queued/processing jobs count as pending so nothing can be
        # queued past the limit) but the UsageEvent is only written when the job succeeds.
        enforce_quota(db, current_user, "voice_clone_use", pending=_pending_jobs_query(db, current_user).count())

        try:
            prepare_worker()  # start the isolated worker if needed (does not wait for model load)
        except CloneUnavailableError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

        job = VoiceCloneJob(
            user_id=current_user.id,
            message_id=message.id,
            reference_audio_hash=reference_hash,
            text_hash=text_hash,
            status=VoiceCloneJobStatus.queued,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    schedule(process_clone_job, job.id, cleaned)
    return CloneRequestResponse(status="queued", job_id=str(job.id), truncated=truncated)


@router.get("/clone-status/{job_id}", response_model=CloneStatusResponse)
def clone_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = _get_owned_job(job_id, current_user, db)
    audio_url = f"/voice/clone-audio/{job.id}" if job.status == VoiceCloneJobStatus.done else None
    return CloneStatusResponse(status=job.status.value, audio_url=audio_url, error_message=job.error_message)


@router.get("/clone-audio/{job_id}")
def clone_audio(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = _get_owned_job(job_id, current_user, db)
    if job.status != VoiceCloneJobStatus.done or not job.output_audio_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not ready.")
    path = Path(job.output_audio_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file missing.")
    return Response(content=path.read_bytes(), media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/clone-availability")
def clone_availability(current_user: User = Depends(get_current_user)):
    """Lightweight check for the UI: is the worker installed on this server?"""
    problem = worker_setup_problem()
    return {"available": problem is None, "detail": problem}


def _get_owned_job(job_id: str, current_user: User, db: Session) -> VoiceCloneJob:
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    job = db.query(VoiceCloneJob).filter(VoiceCloneJob.id == job_uuid, VoiceCloneJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job
