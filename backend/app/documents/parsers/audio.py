import logging
import os
import subprocess

from app.core.config import settings
from app.documents.parsers.types import ParsedPage

logger = logging.getLogger(__name__)

_model = None


def load_whisper_model():
    """Load the faster-whisper model once and reuse it for every transcription — loading
    the model is the slow part, so this follows the same singleton pattern as the Piper
    voice model in app/voice/tts.py."""
    global _model
    if _model is not None:
        return _model

    from faster_whisper import WhisperModel

    # download_root keeps the model weights on the D: drive (via HF_HOME) rather than
    # falling back to the default ~/.cache location on C:.
    download_root = settings.HF_HOME or None
    _model = WhisperModel(settings.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8", download_root=download_root)
    logger.info("faster-whisper model '%s' loaded", settings.WHISPER_MODEL_SIZE)
    return _model


def transcribe_audio(file_path: str) -> list[dict]:
    """Transcribe an audio file, returning timestamped segments:
    [{"start_time": float, "end_time": float, "text": str}, ...]."""
    model = load_whisper_model()
    segments, _info = model.transcribe(file_path, beam_size=1, vad_filter=True)
    return [
        {"start_time": seg.start, "end_time": seg.end, "text": seg.text.strip()}
        for seg in segments
        if seg.text.strip()
    ]


def extract_audio_from_video(video_path: str) -> str:
    """Extract a 16kHz mono WAV audio track from a video file via ffmpeg, returning the
    path to the extracted file (caller is responsible for cleaning it up)."""
    wav_path = f"{video_path}.extracted.wav"
    ffmpeg_bin = settings.FFMPEG_PATH or "ffmpeg"
    cmd = [ffmpeg_bin, "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", wav_path]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to extract audio: {result.stderr.decode(errors='ignore')[:500]}")
    return wav_path


def parse_audio(file_path: str) -> list[ParsedPage]:
    segments = transcribe_audio(file_path)
    return [
        ParsedPage(page_number=i + 1, text=seg["text"], start_time=seg["start_time"], end_time=seg["end_time"])
        for i, seg in enumerate(segments)
    ]


def parse_video(file_path: str) -> list[ParsedPage]:
    wav_path = extract_audio_from_video(file_path)
    try:
        return parse_audio(wav_path)
    finally:
        try:
            os.remove(wav_path)
        except OSError:
            pass
