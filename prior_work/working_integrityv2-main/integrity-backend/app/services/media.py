"""
Media Service — researcher deliverables.

- Server-side PDF generation from already-rendered HTML (WeasyPrint).
- WebM → H.264 MP4 transcoding for session-replay videos (ffmpeg).
- Binary blob storage: S3 when configured (reuses image_storage credentials),
  otherwise GridFS in MongoDB (development fallback — same pattern as
  image_storage's S3-or-Mongo split, but GridFS because videos exceed the
  16MB document limit).

Blob refs are strings: "s3:<key>" or "gridfs:<id>".
"""

import asyncio
import logging
import os
import subprocess
import tempfile
import uuid
from typing import Optional, Tuple

from . import image_storage

logger = logging.getLogger(__name__)

FFMPEG_TIMEOUT_SECONDS = 300
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")

# GridFS bucket (set from main.py lifespan)
_gridfs_bucket = None


def set_database(database):
    """Initialize the GridFS fallback bucket. Call during app startup."""
    global _gridfs_bucket
    try:
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket
        _gridfs_bucket = AsyncIOMotorGridFSBucket(database, bucket_name="media_blobs")
        logger.info("Media GridFS bucket ready")
    except Exception as e:
        logger.error(f"GridFS bucket init failed: {e}")
        _gridfs_bucket = None


# ============================================================================
# PDF GENERATION (WeasyPrint)
# ============================================================================

def _render_pdf_sync(html: str, base_url: Optional[str]) -> bytes:
    # Lazy import — missing system libs (pango/cairo) must not break app startup
    from weasyprint import HTML
    return HTML(string=html, base_url=base_url).write_pdf()


async def generate_pdf_from_html(html: str, base_url: Optional[str] = None) -> bytes:
    """Render static HTML (document content or integrity report) to PDF bytes."""
    return await asyncio.to_thread(_render_pdf_sync, html, base_url)


def pdf_available() -> bool:
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception:
        return False


# ============================================================================
# VIDEO TRANSCODE (ffmpeg)
# ============================================================================

def _transcode_sync(webm_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.webm")
        dst = os.path.join(tmp, "out.mp4")
        with open(src, "wb") as f:
            f.write(webm_bytes)
        cmd = [
            FFMPEG_BIN, "-y",
            "-i", src,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "26",
            "-pix_fmt", "yuv420p",
            # H.264 requires even dimensions; canvas sizes may be odd
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-movflags", "+faststart",
            "-an",  # replay videos have no audio track
            dst,
        ]
        result = subprocess.run(
            cmd, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS
        )
        if result.returncode != 0:
            stderr = (result.stderr or b"").decode(errors="replace")[-2000:]
            raise RuntimeError(f"ffmpeg failed (code {result.returncode}): {stderr}")
        with open(dst, "rb") as f:
            return f.read()


async def transcode_webm_to_mp4(webm_bytes: bytes) -> bytes:
    """Transcode a browser-recorded WebM into a universally playable MP4."""
    return await asyncio.to_thread(_transcode_sync, webm_bytes)


def ffmpeg_available() -> bool:
    try:
        result = subprocess.run(
            [FFMPEG_BIN, "-version"], capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


# ============================================================================
# BLOB STORAGE (S3 with GridFS fallback)
# ============================================================================

async def store_blob(data: bytes, content_type: str, folder: str, owner_id: str = "") -> Optional[str]:
    """Store a binary blob; returns a ref ("s3:<key>" / "gridfs:<id>") or None."""
    ext = {
        "video/mp4": "mp4",
        "application/pdf": "pdf",
        "video/webm": "webm",
    }.get(content_type, "bin")

    # Prefer S3 (encrypted, private) — same client image_storage initialized
    if image_storage.S3_AVAILABLE and image_storage.s3_client:
        try:
            key = f"{folder}/{owner_id}/{uuid.uuid4().hex}.{ext}"
            image_storage.s3_client.put_object(
                Bucket=image_storage.S3_BUCKET,
                Key=key,
                Body=data,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            )
            logger.info(f"Stored blob to S3: {key} ({len(data)} bytes)")
            return f"s3:{key}"
        except Exception as e:
            logger.error(f"S3 blob upload failed, falling back to GridFS: {e}")

    if _gridfs_bucket is not None:
        try:
            file_id = await _gridfs_bucket.upload_from_stream(
                f"{folder}-{uuid.uuid4().hex}.{ext}",
                data,
                metadata={"content_type": content_type, "owner_id": owner_id, "folder": folder},
            )
            logger.info(f"Stored blob to GridFS: {file_id} ({len(data)} bytes)")
            return f"gridfs:{file_id}"
        except Exception as e:
            logger.error(f"GridFS blob upload failed: {e}")

    return None


async def fetch_blob(ref: str) -> Optional[Tuple[bytes, str]]:
    """Fetch a stored blob by ref. Returns (bytes, content_type) or None."""
    if not ref:
        return None

    if ref.startswith("s3:"):
        key = ref[3:]
        if image_storage.S3_AVAILABLE and image_storage.s3_client:
            try:
                obj = await asyncio.to_thread(
                    image_storage.s3_client.get_object,
                    Bucket=image_storage.S3_BUCKET,
                    Key=key,
                )
                data = await asyncio.to_thread(obj["Body"].read)
                return data, obj.get("ContentType", "application/octet-stream")
            except Exception as e:
                logger.error(f"S3 blob fetch failed for {key}: {e}")
        return None

    if ref.startswith("gridfs:"):
        if _gridfs_bucket is None:
            return None
        try:
            from bson import ObjectId
            stream = await _gridfs_bucket.open_download_stream(ObjectId(ref[7:]))
            data = await stream.read()
            content_type = "application/octet-stream"
            if stream.metadata:
                content_type = stream.metadata.get("content_type", content_type)
            return data, content_type
        except Exception as e:
            logger.error(f"GridFS blob fetch failed for {ref}: {e}")
        return None

    return None
