from fastapi import APIRouter

from app.core.config import groq_key_pool, settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    """Liveness plus the AI engine's real capacity.

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
    }
