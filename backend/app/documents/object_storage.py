"""Optional S3-compatible backup for document files (Cloudflare R2's free tier is the
intended target). Local disk under STORAGE_PATH remains the working copy that parsers
and file-serving routes actually read/write — this module just keeps an off-box copy so
those local files can be restored if the host's disk is ephemeral (wiped on restart or
redeploy, e.g. Render's free tier) and gets wiped between requests.

Disabled (no-op) unless all four R2_* settings are set — safe to import unconditionally.
"""
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(settings.R2_ENDPOINT_URL and settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY and settings.R2_BUCKET)


_client = None


def _get_client():
    global _client
    if _client is None:
        import boto3

        _client = boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
    return _client


def upload_dir(prefix: str, local_dir: Path) -> None:
    """Best-effort: upload every file directly inside `local_dir` under `prefix`.
    Never raises — a backup failure shouldn't fail document ingestion."""
    if not enabled():
        return
    try:
        client = _get_client()
        for path in local_dir.iterdir():
            if path.is_file():
                client.upload_file(str(path), settings.R2_BUCKET, f"{prefix}/{path.name}")
    except Exception:
        logger.exception("R2 backup failed for %s (local files are still intact)", prefix)


def download_dir(prefix: str, local_dir: Path) -> bool:
    """Best-effort restore: fetch every object under `prefix` into `local_dir`. Returns
    True if at least one file was restored. Used when a route finds the local file
    missing (host disk was wiped) and falls back to the R2 copy."""
    if not enabled():
        return False
    try:
        client = _get_client()
        local_dir.mkdir(parents=True, exist_ok=True)
        paginator = client.get_paginator("list_objects_v2")
        restored = False
        for page in paginator.paginate(Bucket=settings.R2_BUCKET, Prefix=f"{prefix}/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                dest = local_dir / key.rsplit("/", 1)[-1]
                client.download_file(settings.R2_BUCKET, key, str(dest))
                restored = True
        return restored
    except Exception:
        logger.exception("R2 restore failed for %s", prefix)
        return False


def delete_prefix(prefix: str) -> None:
    """Best-effort: delete every object under `prefix` (mirrors delete_document_files)."""
    if not enabled():
        return
    try:
        client = _get_client()
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.R2_BUCKET, Prefix=f"{prefix}/"):
            keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if keys:
                client.delete_objects(Bucket=settings.R2_BUCKET, Delete={"Objects": keys})
    except Exception:
        logger.exception("R2 delete failed for %s", prefix)
