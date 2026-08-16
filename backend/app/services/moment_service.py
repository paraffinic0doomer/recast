"""Best-moment detection.

Pipeline:
  1. group nearby transcript segments into candidate windows
  2. ask the LLM to select and score windows *by id* (never by timestamp)
  3. map ids back to real segment boundaries
  4. suppress overlapping candidates
  5. return the top 3-5

The LLM never supplies timestamps. It chooses among windows that were built from
real transcript segments, so every returned start/end is guaranteed to line up
with something actually said in the video.
"""

import json
import logging
from dataclasses import dataclass

from app.schemas.content_dna import ContentDNA
from app.schemas.moment import BestMoment, MomentScores
from app.services.analysis_service import (
    AnalysisError,
    extract_json,
    get_analysis_service,
)

logger = logging.getLogger(__name__)

# Short-form targets. Most platforms cap around 60-90s; below ~8s there is no
# room for a hook plus a payoff.
MIN_DURATION = 12.0
MAX_DURATION = 75.0
IDEAL_DURATION = 40.0
MAX_CANDIDATES = 40
OVERLAP_THRESHOLD = 0.5
MIN_MOMENTS = 3
MAX_MOMENTS = 5


@dataclass
class CandidateWindow:
    id: int
    start: float
    end: float
    text: str
    segment_indices: list[int]

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)


def build_candidate_windows(
    segments: list[dict],
    min_duration: float = MIN_DURATION,
    max_duration: float = MAX_DURATION,
) -> list[CandidateWindow]:
    """Group consecutive transcript segments into candidate windows.

    Windows always begin and end on real segment boundaries. Short videos fall
    back to a single whole-transcript window rather than returning nothing.
    """
    usable = [
        s
        for s in segments
        if s.get("start") is not None and s.get("end") is not None
    ]
    if not usable:
        return []

    windows: list[CandidateWindow] = []
    seen: set[tuple[float, float]] = set()

    for i in range(len(usable)):
        for j in range(i, len(usable)):
            start = float(usable[i]["start"])
            end = float(usable[j]["end"])
            duration = end - start

            if duration > max_duration:
                break
            if duration < min_duration:
                continue

            key = (round(start, 2), round(end, 2))
            if key in seen:
                continue
            seen.add(key)

            windows.append(
                CandidateWindow(
                    id=len(windows),
                    # Exact segment values, never rounded: downstream code joins
                    # moments back to transcript segments by timestamp equality.
                    start=start,
                    end=end,
                    text=" ".join(str(usable[k].get("text", "")).strip() for k in range(i, j + 1)),
                    segment_indices=list(range(i, j + 1)),
                )
            )

    if not windows:
        # Video shorter than min_duration: offer the whole thing as one window.
        start = float(usable[0]["start"])
        end = float(usable[-1]["end"])
        windows.append(
            CandidateWindow(
                id=0,
                start=start,
                end=end,
                text=" ".join(str(s.get("text", "")).strip() for s in usable),
                segment_indices=list(range(len(usable))),
            )
        )
        logger.info("Transcript shorter than %.0fs; using whole-transcript window", min_duration)
        return windows

    # Too many windows blows up the prompt. Prefer durations near the sweet spot.
    if len(windows) > MAX_CANDIDATES:
        windows.sort(key=lambda w: abs(w.duration - IDEAL_DURATION))
        windows = windows[:MAX_CANDIDATES]
        windows.sort(key=lambda w: (w.start, w.end))
        for new_id, window in enumerate(windows):
            window.id = new_id

    return windows


def _overlap_ratio(a: BestMoment, b: BestMoment) -> float:
    """Intersection over the shorter clip -- catches a small clip inside a big one."""
    overlap = min(a.end, b.end) - max(a.start, b.start)
    if overlap <= 0:
        return 0.0
    shortest = min(a.duration, b.duration)
    return overlap / shortest if shortest > 0 else 0.0


def remove_overlapping(
    moments: list[BestMoment], threshold: float = OVERLAP_THRESHOLD
) -> list[BestMoment]:
    """Greedy non-maximum suppression: keep the best, drop anything overlapping it."""
    kept: list[BestMoment] = []
    for moment in sorted(moments, key=lambda m: m.score, reverse=True):
        if any(_overlap_ratio(moment, k) > threshold for k in kept):
            logger.debug("Dropping overlapping moment %.1f-%.1f", moment.start, moment.end)
            continue
        kept.append(moment)
    return kept


def build_moment_prompt(windows: list[CandidateWindow], dna: ContentDNA | None) -> str:
    context = ""
    if dna is not None:
        context = (
            f"\nCONTENT CONTEXT (use this to judge fit):\n"
            f"- Primary topic: {dna.primary_topic}\n"
            f"- Audience: {dna.audience}\n"
            f"- Tone: {dna.tone}\n"
            f"- Core message: {dna.core_message}\n"
        )

    listing = "\n".join(
        f'id={w.id} [{w.start:.1f}s-{w.end:.1f}s, {w.duration:.0f}s] "{w.text}"'
        for w in windows
    )

    return (
        "You are selecting clips for short-form social video (TikTok, Reels, Shorts).\n"
        f"{context}\n"
        "Below are candidate windows taken from the transcript. Choose the "
        f"{MIN_MOMENTS}-{MAX_MOMENTS} STRONGEST windows for standalone short-form clips.\n\n"
        "Return JSON of exactly this shape:\n"
        '{"moments": [{"id": 3, "title": "short punchy title", '
        '"hook": "first line that stops the scroll", '
        '"reason": "why this works as a standalone short", '
        '"scores": {"hook_strength": 0-100, "information_value": 0-100, '
        '"standalone_quality": 0-100, "emotional_interest": 0-100}}]}\n\n'
        "Rules:\n"
        "- Reference windows ONLY by their id. Never output timestamps.\n"
        "- Pick windows that make sense without surrounding context.\n"
        "- Prefer non-overlapping windows covering different ideas.\n"
        "- Score honestly; do not give everything 90+.\n"
        "- hook must be text a viewer would actually see or hear at the start.\n\n"
        f"CANDIDATE WINDOWS:\n{listing}"
    )


def detect_moments(
    transcript: dict,
    dna: ContentDNA | None = None,
    service=None,
) -> list[BestMoment]:
    """Select the best short-form moments from a transcript."""
    segments = transcript.get("segments") or []
    windows = build_candidate_windows(segments)
    if not windows:
        raise AnalysisError("Transcript has no usable timestamped segments to select moments from.")

    by_id = {w.id: w for w in windows}
    service = service or get_analysis_service()
    prompt = build_moment_prompt(windows, dna)

    logger.info("Scoring %d candidate windows for best moments", len(windows))
    raw = service.complete_json(prompt)
    payload = raw if isinstance(raw, dict) else extract_json(str(raw))

    entries = payload.get("moments")
    if not isinstance(entries, list) or not entries:
        raise AnalysisError("Model returned no moments to evaluate.")

    moments: list[BestMoment] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        window = by_id.get(_as_int(entry.get("id")))
        if window is None:
            # The model referenced a window that does not exist -- discard rather
            # than guess, so we never emit a timestamp we cannot justify.
            logger.warning("Discarding moment with unknown window id %r", entry.get("id"))
            continue

        moments.append(
            BestMoment(
                start=window.start,
                end=window.end,
                title=entry.get("title") or "Untitled moment",
                hook=entry.get("hook") or "",
                reason=entry.get("reason") or "",
                scores=MomentScores.model_validate(entry.get("scores") or {}),
            )
        )

    if not moments:
        raise AnalysisError(
            "Model did not reference any valid candidate window; cannot produce moments."
        )

    moments = remove_overlapping(moments)
    moments.sort(key=lambda m: m.score, reverse=True)
    moments = moments[:MAX_MOMENTS]

    # Stable ids so clips can reference a moment without depending on list order.
    for rank, moment in enumerate(moments, start=1):
        moment.id = f"m{rank}"
    return moments


def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
