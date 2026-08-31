import re
from pathlib import Path

from app.core.config import settings


def _safe_title(title: str) -> str:
    title = re.sub(r"[^\w\-. ]", "_", title).strip()
    return title[:80] or "video"


def download_audio_from_url(url: str, dest_dir: Path) -> tuple[str, str]:
    """Download a video from a URL (YouTube or any of the hundreds of other sites
    yt-dlp supports) and extract its audio track as a WAV file — free, local, no API key.
    Returns (file_path, display_title)."""
    import yt_dlp

    dest_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "wav", "preferredquality": "192"}
        ],
    }
    if settings.FFMPEG_PATH:
        ydl_opts["ffmpeg_location"] = settings.FFMPEG_PATH
    if settings.YTDLP_CACHE_DIR:
        ydl_opts["cachedir"] = settings.YTDLP_CACHE_DIR

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get("id") or "video"
        title = info.get("title") or video_id

    wav_path = dest_dir / f"{video_id}.wav"
    if not wav_path.exists():
        candidates = list(dest_dir.glob(f"{video_id}.*"))
        if not candidates:
            raise RuntimeError("Download succeeded but no output file was found.")
        wav_path = candidates[0]

    return str(wav_path), _safe_title(title)
