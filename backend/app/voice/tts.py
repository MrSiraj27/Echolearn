import io
import logging
import re
import wave
from pathlib import Path
from threading import Lock

from app.core.config import settings
from app.voice.text_cleanup import clean_text_for_speech

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 1000
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Every voice EchoLearn offers, keyed by the id the frontend sends. Each must have a
# matching {file_stem}.onnx and {file_stem}.onnx.json in VOICE_MODEL_DIR.
#
# Piper ships each voice at multiple quality tiers (x_low/low/medium/high) trained at
# different sample rates and model sizes — "high" sounds meaningfully more natural than
# "medium" at the cost of a larger model and slightly slower synthesis. All voices here
# are the "high" tier where Piper offers one; "amy" is medium-only upstream.
AVAILABLE_VOICES = {
    "lessac": {"label": "Lessac — neutral (US)", "file_stem": "en_US-lessac-high"},
    "ryan": {"label": "Ryan — male (US)", "file_stem": "en_US-ryan-high"},
    "ljspeech": {"label": "Sarah — female (US)", "file_stem": "en_US-ljspeech-high"},
    "cori": {"label": "Cori — female (British)", "file_stem": "en_GB-cori-high"},
    "amy": {"label": "Amy — female (US)", "file_stem": "en_US-amy-medium"},
}
DEFAULT_VOICE_ID = "lessac"

_voices: dict[str, object] = {}  # voice_id -> loaded PiperVoice
_voice_lock = Lock()


def _build_synthesis_config():
    from piper.config import SynthesisConfig

    # Slightly reduced noise vs. Piper's defaults (noise_scale ~0.667, noise_w ~0.8) —
    # trims some of the random pitch/duration jitter that reads as "wobbly" or
    # synthetic, at a small cost to expressiveness, for a calmer, more even delivery.
    return SynthesisConfig(length_scale=1.0, noise_scale=0.55, noise_w_scale=0.65)


SYNTHESIS_CONFIG = _build_synthesis_config()


class VoiceUnavailableError(Exception):
    pass


def _model_dir() -> Path:
    return Path(settings.VOICE_MODEL_PATH).parent


def _model_paths(voice_id: str) -> tuple[Path, Path]:
    file_stem = AVAILABLE_VOICES[voice_id]["file_stem"]
    base = _model_dir() / file_stem
    return base.with_suffix(".onnx"), Path(f"{base}.onnx.json")


def voice_model_exists(voice_id: str = DEFAULT_VOICE_ID) -> bool:
    if voice_id not in AVAILABLE_VOICES:
        return False
    onnx_path, config_path = _model_paths(voice_id)
    return onnx_path.exists() and config_path.exists()


def list_available_voices() -> list[dict]:
    """Voices whose model files actually exist on disk — a voice can be registered in
    AVAILABLE_VOICES without its file being downloaded yet."""
    return [
        {"id": voice_id, "label": meta["label"]}
        for voice_id, meta in AVAILABLE_VOICES.items()
        if voice_model_exists(voice_id)
    ]


def load_voice_model():
    """Load the default Piper voice once, at startup, so the first request isn't slow.
    Other voices load lazily on first use. Never crashes the app — logs a warning and
    leaves voices unloaded if files are missing, so the rest of the app keeps working."""
    if not voice_model_exists(DEFAULT_VOICE_ID):
        logger.warning(
            "Voice model not found at %s — /voice/speak will return 503 until it's downloaded. "
            "See README for setup instructions.",
            settings.VOICE_MODEL_PATH,
        )
        return

    try:
        _load_voice(DEFAULT_VOICE_ID)
        logger.info("Piper voice model '%s' loaded", DEFAULT_VOICE_ID)
    except Exception:
        logger.exception("Failed to load default Piper voice model — voice features will be unavailable")


def _load_voice(voice_id: str):
    """Load and cache one voice by id. Caller must hold _voice_lock or accept the
    (harmless) possibility of loading it twice under a race."""
    if voice_id in _voices:
        return _voices[voice_id]

    from piper import PiperVoice

    onnx_path, config_path = _model_paths(voice_id)
    voice = PiperVoice.load(str(onnx_path), str(config_path))
    _voices[voice_id] = voice
    return voice


def get_voice(voice_id: str):
    if voice_id not in AVAILABLE_VOICES or not voice_model_exists(voice_id):
        return None
    with _voice_lock:
        try:
            return _load_voice(voice_id)
        except Exception:
            logger.exception("Failed to load Piper voice '%s'", voice_id)
            return None


def is_voice_ready(voice_id: str = DEFAULT_VOICE_ID) -> bool:
    return voice_model_exists(voice_id)


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split into sentence-based chunks under max_chars — Piper synthesizes more
    naturally on shorter utterances than one giant block of text."""
    sentences = _SENTENCE_SPLIT_RE.split(text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks or [text]


def synthesize_speech(text: str, voice_id: str = DEFAULT_VOICE_ID) -> bytes:
    """Returns WAV audio bytes for `text` in the requested voice, or raises
    VoiceUnavailableError if that voice isn't available."""
    voice = get_voice(voice_id)
    if voice is None:
        raise VoiceUnavailableError(f"Voice '{voice_id}' is not available.")

    cleaned = clean_text_for_speech(text)
    if not cleaned:
        cleaned = "There's nothing to read here."

    chunks = _chunk_text(cleaned)

    buffer = io.BytesIO()
    with _voice_lock:  # Piper's ONNX session isn't guaranteed thread-safe across concurrent requests.
        with wave.open(buffer, "wb") as wav_file:
            for i, chunk in enumerate(chunks):
                voice.synthesize_wav(chunk, wav_file, syn_config=SYNTHESIS_CONFIG, set_wav_format=(i == 0))

    return buffer.getvalue()
