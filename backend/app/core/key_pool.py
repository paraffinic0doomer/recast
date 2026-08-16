"""Rotating pool of Groq API keys.

Groq's free tier caps tokens-per-day per key. With a single key a heavy demo
day stops working entirely. This pool holds several keys, marks one as cooling
down when it returns a rate-limit error, and transparently moves to the next —
so the effective daily budget is the sum of every key in the pool.

Keys are read from (in order of preference):
  1. backend/groq_keys.txt  — one key per line, '#' comments allowed
  2. GROQ_API_KEYS          — comma-separated
  3. GROQ_API_KEY           — single key

State is per-process and in-memory: a restart simply retries every key, which
is the right behaviour since limits reset on Groq's clock, not ours.
"""

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Fallback cooldown when the provider does not tell us how long to wait.
DEFAULT_COOLDOWN_SECONDS = 60 * 60


def parse_retry_after(message: str) -> float:
    """Pull 'try again in 27m50.976s' out of a provider error message."""
    match = re.search(
        r"try again in\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:([\d.]+)s)?",
        message or "",
        re.IGNORECASE,
    )
    if not match:
        return DEFAULT_COOLDOWN_SECONDS
    hours, minutes, seconds = match.groups()
    total = (
        float(hours or 0) * 3600 + float(minutes or 0) * 60 + float(seconds or 0)
    )
    return total if total > 0 else DEFAULT_COOLDOWN_SECONDS


def is_rate_limit_error(exc: BaseException) -> bool:
    """True for provider rate-limit / quota errors, whatever SDK raised them."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status == 429 or status == "rate_limit_exceeded":
        return True
    text = str(exc).lower()
    return "429" in text or "rate limit" in text or "rate_limit_exceeded" in text


def is_invalid_key_error(exc: BaseException) -> bool:
    """True when the provider rejects the key itself (revoked, mistyped, wrong org)."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status in (401, 403, "invalid_api_key"):
        return True
    text = str(exc).lower()
    return "invalid api key" in text or "invalid_api_key" in text or "401" in text


@dataclass
class _KeyState:
    key: str
    cooling_until: float = 0.0
    failures: int = 0

    @property
    def available(self) -> bool:
        return time.time() >= self.cooling_until

    @property
    def cooldown_remaining(self) -> float:
        if self.cooling_until == float("inf"):
            return float("inf")
        return max(0.0, self.cooling_until - time.time())


@dataclass
class KeyPool:
    """Thread-safe rotation over a list of API keys."""

    _states: list[_KeyState] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @staticmethod
    def _read_key_file(path: Path) -> list[str]:
        keys: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                keys.append(line)
        return keys

    @classmethod
    def from_sources(
        cls,
        keys_file: Path | None = None,
        keys_csv: str = "",
        single_key: str = "",
        extra_files: list[Path] | None = None,
    ) -> "KeyPool":
        keys: list[str] = []

        # Key files are additive so keys can live outside the repo.
        for path in [keys_file, *(extra_files or [])]:
            if path and path.exists():
                found = cls._read_key_file(path)
                if found:
                    logger.info("Loaded %d key(s) from %s", len(found), path.name)
                    keys.extend(found)

        if not keys and keys_csv:
            keys = [k.strip() for k in keys_csv.split(",")]

        if not keys and single_key:
            keys = [single_key.strip()]

        # De-duplicate while preserving order; ignore obvious placeholders.
        seen: set[str] = set()
        cleaned = []
        for key in keys:
            if not key or key in seen or key.lower().endswith("your_key_here"):
                continue
            seen.add(key)
            cleaned.append(key)

        if cleaned:
            logger.info("Groq key pool initialised with %d key(s)", len(cleaned))
        return cls(_states=[_KeyState(key=k) for k in cleaned])

    @property
    def size(self) -> int:
        return len(self._states)

    @property
    def configured(self) -> bool:
        return bool(self._states)

    def acquire(self) -> str | None:
        """Next usable key, or None when every key is cooling down."""
        with self._lock:
            for state in self._states:
                if state.available:
                    return state.key
        return None

    def disable(self, key: str, reason: str) -> None:
        """Retire a key for the life of the process (revoked / invalid)."""
        with self._lock:
            for state in self._states:
                if state.key == key:
                    state.cooling_until = float("inf")
                    state.failures += 1
                    logger.error(
                        "Groq key ...%s disabled: %s. Remove it from "
                        "backend/groq_keys.txt. %d key(s) still usable.",
                        key[-6:],
                        reason,
                        sum(1 for s in self._states if s.available),
                    )
                    return

    def mark_exhausted(self, key: str, message: str = "") -> None:
        cooldown = parse_retry_after(message)
        with self._lock:
            for state in self._states:
                if state.key == key:
                    state.cooling_until = time.time() + cooldown
                    state.failures += 1
                    logger.warning(
                        "Groq key ...%s rate-limited; cooling down %.0f min "
                        "(%d/%d keys still available)",
                        key[-6:],
                        cooldown / 60,
                        sum(1 for s in self._states if s.available),
                        len(self._states),
                    )
                    return

    def status(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "key_suffix": s.key[-6:],
                    "available": s.available,
                    "cooldown_seconds": (
                        -1 if s.cooldown_remaining == float("inf")
                        else round(s.cooldown_remaining)
                    ),
                    "failures": s.failures,
                }
                for s in self._states
            ]

    def reset(self) -> None:
        with self._lock:
            for state in self._states:
                state.cooling_until = 0.0


def call_with_rotation(pool: KeyPool, run, *, what: str = "request"):
    """Run `run(key)`, moving to the next key whenever one is rate-limited.

    Raises the last error if every key is exhausted, so the caller still gets a
    clear, actionable message rather than a silent failure.
    """
    if not pool.configured:
        raise RuntimeError("No Groq API keys configured")

    last_error: BaseException | None = None
    tried: set[str] = set()

    for _ in range(pool.size):
        key = pool.acquire()
        if key is None or key in tried:
            break
        tried.add(key)
        try:
            return run(key)
        except Exception as exc:
            if is_invalid_key_error(exc):
                # A bad key in the file must not block every request behind it.
                pool.disable(key, "invalid or revoked")
            elif is_rate_limit_error(exc):
                pool.mark_exhausted(key, str(exc))
            else:
                raise
            last_error = exc
            logger.info("Retrying %s with the next key", what)

    if last_error is not None:
        raise last_error
    raise RuntimeError(
        f"All {pool.size} Groq keys are rate-limited. "
        "Add another key to backend/groq_keys.txt or wait for the limit to reset."
    )
