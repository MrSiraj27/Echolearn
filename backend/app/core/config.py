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
