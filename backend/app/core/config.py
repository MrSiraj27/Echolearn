from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    # Generic SMTP (used instead of Resend when set): Resend's free tier only delivers to
    # the account owner's own address without a verified custom domain, which most people
    # signing up don't have. SMTP2GO's free tier (smtp2go.com) lets you verify a single
    # sender EMAIL you already own — no domain/DNS needed — and then send to any real
    # recipient. Any standard SMTP provider works here, not just SMTP2GO.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    FRONTEND_URL: str = "http://localhost:3000"
    STORAGE_PATH: str = "./storage"
    CHROMA_PATH: str = "./chroma_data"
    TESSERACT_CMD: str = ""
    MAX_UPLOAD_SIZE_MB: int = 50
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    HF_HOME: str = ""

    # Object storage (optional): an S3-compatible bucket (e.g. Cloudflare R2's free tier)
    # that backs up each document's original file + parsed text, so they survive a restart
    # on a host with an ephemeral filesystem (e.g. Render's free tier). Local disk under
    # STORAGE_PATH is still used as a working/cache copy; see app/documents/object_storage.py.
    # Leave all four blank to disable and rely on local disk only (fine for local dev).
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = ""

    VOICE_BACKEND: str = "local"  # "local" (in-process Piper) or "hf_space" (remote Space)
    VOICE_MODEL_PATH: str = "./voices/en_US-lessac-medium.onnx"
    VOICE_HF_SPACE_URL: str = ""
    VOICE_AUDIO_CACHE_PATH: str = "./storage/audio"

    # Voice cloning: Fish Audio API (api.fish.audio) — no local model/worker, works
    # identically on any host. Free tier (s2.1-pro-free model) has no hard usage cap
    # under fair use and needs no card. If unset, "My Voice" reports 503.
    FISH_AUDIO_API_KEY: str = ""

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
