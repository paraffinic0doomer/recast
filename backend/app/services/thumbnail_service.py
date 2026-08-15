"""Thumbnail concept generation.

Produces 3 render-ready concepts from Content DNA plus the strongest moments.

There is no image-generation backend configured, so instead of inventing a
picture we extract a *real* frame from the video at each concept's moment. The
frontend composes the headline over that frame using the spec's placement and
accent colour, so the preview reflects actual footage.

The LLM selects frames by id, never by raw timestamp -- same discipline as
moment detection, so a concept can never point at a time that does not exist.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.config import THUMBNAILS_DIR, settings
from app.schemas.content_dna import ContentDNA
from app.schemas.moment import BestMoment
from app.schemas.thumbnail import ThumbnailConcept
from app.services.analysis_service import AnalysisError, get_analysis_service
from app.services.media_service import MediaProcessingError, _run, extract_metadata

logger = logging.getLogger(__name__)

CONCEPT_COUNT = 3
MAX_FRAME_OPTIONS = 8


@dataclass
class FrameOption:
    id: int
    timestamp: float
    label: str


SYSTEM_PROMPT = (
    "You are a YouTube thumbnail strategist. You design thumbnails that earn the "
    "click without lying about the content. Headlines are 3-6 words, readable at "
    "small sizes. Base everything strictly on the supplied content. Respond with "
    "JSON only."
)


def image_generation_available() -> bool:
    """No image backend is wired up today; kept as the single check to flip later."""
    return bool(settings.image_generation_backend.strip())


def build_frame_options(
    dna: ContentDNA, moments: list[BestMoment], duration: float | None
) -> list[FrameOption]:
    """Candidate frames, drawn from real moment timestamps."""
    seen: set[float] = set()
    options: list[FrameOption] = []

    def add(timestamp: float, label: str) -> None:
        if duration is not None and timestamp >= duration:
            return
        key = round(timestamp, 1)
        if key in seen:
            return
        seen.add(key)
        options.append(FrameOption(id=len(options), timestamp=timestamp, label=label))

    # Mid-clip frames from the best moments are most likely to show the subject
    # mid-sentence rather than mid-blink at a boundary.
    for moment in moments:
        add((moment.start + moment.end) / 2, moment.title or "Best moment")
    for key_moment in dna.key_moments:
        if key_moment.timestamp is not None:
            add(float(key_moment.timestamp), key_moment.title)

    return options[:MAX_FRAME_OPTIONS]


def build_thumbnail_prompt(
    dna: ContentDNA, options: list[FrameOption]
) -> str:
    frames = "\n".join(f"id={o.id} [{o.timestamp:.1f}s] {o.label}" for o in options)
    return (
        f"Design {CONCEPT_COUNT} DISTINCT thumbnail concepts for this video.\n\n"
        f"CONTENT DNA:\n"
        f"- Primary topic: {dna.primary_topic}\n"
        f"- Audience: {dna.audience}\n"
        f"- Tone: {dna.tone}\n"
        f"- Core message: {dna.core_message}\n"
        f"- Key points: {' | '.join(dna.key_points) or 'n/a'}\n"
        f"- Hooks: {' | '.join(dna.hooks) or 'n/a'}\n\n"
        f"AVAILABLE FRAMES (choose one per concept, by id):\n{frames}\n\n"
        'Return JSON: {"concepts": [{"frame_id": 0, "headline": "...", '
        '"visual_concept": "...", "subject_placement": "left|right|center|full", '
        '"emotional_angle": "...", "why_it_works": "...", '
        '"recommended_use_case": "...", "text_position": "left|right|center", '
        '"accent_color": "#RRGGBB"}]}\n\n'
        "Rules:\n"
        f"- Exactly {CONCEPT_COUNT} concepts, each a genuinely different angle "
        "(e.g. curiosity, problem/pain, outcome). Do not reword one idea.\n"
        "- headline is 3-6 words of ON-IMAGE text. Not a sentence, not the title.\n"
        "- Reference frames only by id.\n"
        "- recommended_use_case says where this concept performs best "
        "(e.g. 'search traffic', 'suggested video', 'A/B test against the outcome angle').\n"
        "- accent_color must contrast with typical footage; avoid mid greys.\n"
        "- Never promise anything the content does not deliver.\n"
    )


def extract_frame(video_path: Path, at_seconds: float, name: str) -> Path:
    """Pull a single real frame out of the source video."""
    if not video_path.exists():
        raise MediaProcessingError(f"Video file not found: {video_path}")

    out_path = THUMBNAILS_DIR / f"{name}.jpg"
    _run(
        [
            settings.ffmpeg_bin,
            "-y",
            "-ss",
            f"{at_seconds:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out_path),
        ]
    )
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise MediaProcessingError(f"Frame extraction produced no output at {at_seconds:.1f}s")
    return out_path


def generate_thumbnail_concepts(
    project_id: str,
    video_path: Path | None,
    dna: ContentDNA,
    moments: list[BestMoment],
    duration: float | None = None,
    service=None,
) -> list[ThumbnailConcept]:
    """Generate 3 thumbnail concepts, each backed by a real extracted frame."""
    options = build_frame_options(dna, moments, duration)
    if not options:
        raise AnalysisError(
            "No usable timestamps for thumbnails. Run moment detection or analysis first."
        )

    by_id = {o.id: o for o in options}
    service = service or get_analysis_service()

    payload = service.complete_json(build_thumbnail_prompt(dna, options), SYSTEM_PROMPT)
    if not isinstance(payload, dict):
        raise AnalysisError("Model did not return a JSON object for thumbnails")

    entries = payload.get("concepts")
    if not isinstance(entries, list) or not entries:
        raise AnalysisError("Model returned no thumbnail concepts")

    concepts: list[ThumbnailConcept] = []
    for index, entry in enumerate(entries[:CONCEPT_COUNT]):
        if not isinstance(entry, dict):
            continue

        # Fall back to spreading across options if the model picks a bad id,
        # rather than dropping the concept entirely.
        try:
            frame_id = int(entry.get("frame_id"))
        except (TypeError, ValueError):
            frame_id = -1
        option = by_id.get(frame_id) or options[index % len(options)]

        concept = ThumbnailConcept(
            id=f"t{index + 1}",
            headline=entry.get("headline") or "",
            visual_concept=entry.get("visual_concept") or "",
            subject_placement=entry.get("subject_placement") or "center",
            emotional_angle=entry.get("emotional_angle") or "",
            why_it_works=entry.get("why_it_works") or "",
            recommended_use_case=entry.get("recommended_use_case") or "",
            text_position=entry.get("text_position") or "left",
            accent_color=entry.get("accent_color") or "#FACC15",
            timestamp=option.timestamp,
        )

        # A missing frame must not lose the concept -- the spec is still useful.
        if video_path is not None:
            try:
                frame = extract_frame(
                    video_path, option.timestamp, f"{project_id}_thumb_{concept.id}"
                )
                concept.frame_url = f"/media/thumbnails/{frame.name}"
            except MediaProcessingError as exc:
                logger.warning("Could not extract thumbnail frame: %s", exc)

        concepts.append(concept)

    if not concepts:
        raise AnalysisError("No valid thumbnail concepts could be built")

    logger.info("Generated %d thumbnail concepts for project %s", len(concepts), project_id)
    return concepts
