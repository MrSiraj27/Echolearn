from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    FRONTEND_URL: str = "http://localhost:3000"
    STORAGE_PATH: str = "./storage"
    CHROMA_PATH: str = "./chroma_data"
    TESSERACT_CMD: str = ""
    MAX_UPLOAD_SIZE_MB: int = 50
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    HF_HOME: str = ""

    VOICE_BACKEND: str = "local"  # "local" (in-process Piper) or "hf_space" (remote Space)
    VOICE_MODEL_PATH: str = "./voices/en_US-lessac-medium.onnx"
    VOICE_HF_SPACE_URL: str = ""
    VOICE_AUDIO_CACHE_PATH: str = "./storage/audio"

    # Voice cloning runs in an ISOLATED local worker process (MOSS-TTS-Nano, ONNX/CPU) with its
    # own venv, because its pinned torch/transformers conflict with this app's stack. See
    # backend/voice_worker/README.md. If the worker isn't set up, "My Voice" reports 503.
    VOICE_CLONE_WORKER_PYTHON: str = ""  # default: models/moss-tts-nano/venv/{Scripts/python.exe|bin/python}
    VOICE_CLONE_WORKER_SCRIPT: str = "./voice_worker/worker.py"
    VOICE_CLONE_WORKER_PORT: int = 8765
    VOICE_CLONE_WORKER_AUTOSTART: bool = True  # spawn lazily on the first clone request
    VOICE_CLONE_WORKER_THREADS: int = 0  # 0 = worker picks (half the CPU cores)
    VOICE_CLONE_WORKER_LOAD_TIMEOUT_SECONDS: int = 300  # first run may also download ~700MB of weights
    VOICE_CLONE_REQUEST_TIMEOUT_SECONDS: int = 600

    # "small"/"base" balance speed and CPU/RAM use for free hosting; "medium"/"large"
    # are far more accurate but need much more RAM and are usually too slow on a CPU-only
    # free tier.
    WHISPER_MODEL_SIZE: str = "base"
    FFMPEG_PATH: str = ""
    YTDLP_CACHE_DIR: str = "./.ytdlp_cache"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
