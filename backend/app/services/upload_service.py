import logging
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import UPLOADS_DIR

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500MB


def validate_extension(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return suffix


async def save_video(project_id: str, video: UploadFile) -> tuple[Path, int]:
    """Stream an uploaded video to disk, enforcing the size limit. Returns (path, bytes_written)."""
    suffix = validate_extension(video.filename or "")
    dest_path = UPLOADS_DIR / f"{project_id}{suffix}"

    size = 0
    with dest_path.open("wb") as out_file:
        while chunk := await video.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out_file.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Video exceeds 500MB limit")
            out_file.write(chunk)

    logger.info("Saved video for project %s: %s (%d bytes)", project_id, dest_path.name, size)
    return dest_path, size


def new_project_id() -> str:
    return uuid.uuid4().hex
