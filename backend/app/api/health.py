import shutil
import subprocess
from functools import lru_cache

from fastapi import APIRouter

from app.core.config import groq_key_pool, settings

router = APIRouter(tags=["health"])


@lru_cache(maxsize=1)
def _media_tools() -> dict:
    """Whether FFmpeg is actually usable in this environment.

    The pipeline shells out to ffmpeg/ffprobe for metadata, audio extraction,
    clip cutting and caption burn-in. When they are missing, every upload
    fails at the first stage with an error that looks like an application bug.
    Reporting it here turns 'clip generation is broken' into a one-request
    answer. Cached because the binaries cannot appear or vanish mid-process.
    """
    result = {}
    for name in ("ffmpeg", "ffprobe"):
        binary = getattr(settings, f"{name}_bin")
        path = shutil.which(binary)
        if path is None:
            result[name] = {"available": False, "version": None, "path": None}
            continue
        try:
            out = subprocess.run(
                [binary, "-version"], capture_output=True, text=True, timeout=10
            )
            version = out.stdout.splitlines()[0] if out.stdout else None
        except (OSError, subprocess.SubprocessError):
            version = None
        result[name] = {"available": True, "version": version, "path": path}
    return result


@router.get("/health")
def health_check() -> dict:
    """Liveness, the AI engine's real capacity, and media tooling.

    The key pool already knows when every key is cooling down after a rate
    limit. Reporting it here is what lets the UI say "rate-limited, back in
    16 min" instead of leaving a generate button that quietly does nothing.
    """
    pool = groq_key_pool()
    keys = pool.status() if pool else []
    available = [k for k in keys if k["available"]]

    # Soonest moment any key frees up; -1 marks a permanently disabled key.
    waits = [
        k["cooldown_seconds"]
        for k in keys
        if not k["available"] and k["cooldown_seconds"] >= 0
    ]

    tools = _media_tools()

    return {
        "status": "ok",
        "openai_configured": settings.openai_configured,
        "ai": {
            "keys_total": len(keys),
            "keys_available": len(available),
            # True only when keys exist and none of them can currently be used.
            "rate_limited": bool(keys) and not available,
            "retry_after_seconds": min(waits) if waits else None,
        },
        "media": {
            "ffmpeg_available": tools["ffmpeg"]["available"],
            "ffprobe_available": tools["ffprobe"]["available"],
            "ffmpeg_version": tools["ffmpeg"]["version"],
        },
    }
