import pytest

from app.schemas.content_dna import ContentDNA
from app.schemas.moment import BestMoment, MomentScores
from app.schemas.thumbnail import HEADLINE_MAX, ThumbnailConcept
from app.services.analysis_service import AnalysisError
from app.services.thumbnail_service import (
    build_frame_options,
    build_thumbnail_prompt,
    generate_thumbnail_concepts,
)

DNA = ContentDNA.model_validate(
    {
        "primary_topic": "Repurposing video content",
        "audience": "Content creators",
        "tone": "Educational",
        "core_message": "One video can become a whole campaign.",
        "key_points": ["Manual repurposing wastes hours"],
        "hooks": ["Nobody wants to watch you say hello"],
        "key_moments": [
            {"timestamp": 0.0, "title": "Intro"},
            {"timestamp": 30.0, "title": "The problem"},
        ],
    }
)

MOMENTS = [
    BestMoment(
        id="m1", start=40.0, end=60.0, title="The fix", hook="So what is the fix?",
        scores=MomentScores(hook_strength=90, information_value=90,
                            standalone_quality=90, emotional_interest=90),
    )
]


def _entry(frame_id=0, headline="Stop Wasting Hours"):
    return {
        "frame_id": frame_id,
        "headline": headline,
        "visual_concept": "Creator mid-gesture, split screen of clips",
        "subject_placement": "right",
        "emotional_angle": "frustration",
        "why_it_works": "Names a pain the viewer already feels",
        "recommended_use_case": "search traffic",
        "text_position": "left",
        "accent_color": "#FACC15",
    }


class StubService:
    def __init__(self, payload=None):
        self.payload = payload or {"concepts": [_entry(0), _entry(1, "The Real Mistake"), _entry(0, "One Video, Full Campaign")]}
        self.prompts = []

    def complete_json(self, prompt, system=None):
        self.prompts.append(prompt)
        return self.payload


# --- frame options -----------------------------------------------------------


def test_frame_options_use_real_timestamps():
    options = build_frame_options(DNA, MOMENTS, duration=120.0)
    assert options
    # Moment midpoint plus DNA key moments.
    assert 50.0 in [o.timestamp for o in options]
    assert 30.0 in [o.timestamp for o in options]


def test_frame_options_exclude_times_past_the_video():
    options = build_frame_options(DNA, MOMENTS, duration=20.0)
    assert all(o.timestamp < 20.0 for o in options)


def test_frame_options_deduplicated():
    options = build_frame_options(DNA, MOMENTS, duration=200.0)
    stamps = [round(o.timestamp, 1) for o in options]
    assert len(stamps) == len(set(stamps))


def test_no_options_without_timestamps():
    assert build_frame_options(ContentDNA(), [], duration=60.0) == []


def test_prompt_lists_frames_by_id():
    prompt = build_thumbnail_prompt(DNA, build_frame_options(DNA, MOMENTS, 120.0))
    assert "id=0" in prompt
    assert "Reference frames only by id" in prompt
    assert "One video can become a whole campaign." in prompt


# --- validation --------------------------------------------------------------


def test_headline_truncated_and_unquoted():
    c = ThumbnailConcept.model_validate({"headline": '"' + "x" * 100 + '"'})
    assert len(c.headline) <= HEADLINE_MAX
    assert not c.headline.startswith('"')


def test_invalid_placement_and_position_fall_back():
    c = ThumbnailConcept.model_validate(
        {"subject_placement": "diagonal", "text_position": "sideways"}
    )
    assert c.subject_placement == "center"
    assert c.text_position == "left"


def test_accent_colour_validated():
    assert ThumbnailConcept.model_validate({"accent_color": "#ff0000"}).accent_color == "#FF0000"
    assert ThumbnailConcept.model_validate({"accent_color": "bright red"}).accent_color == "#FACC15"
    assert ThumbnailConcept.model_validate({"accent_color": "#GGGGGG"}).accent_color == "#FACC15"


def test_negative_timestamp_clamped():
    assert ThumbnailConcept.model_validate({"timestamp": -5.0}).timestamp == 0.0


# --- generation --------------------------------------------------------------


def test_generates_three_concepts_with_real_timestamps(long_sample_video):
    concepts = generate_thumbnail_concepts(
        "p1", long_sample_video, DNA, MOMENTS, duration=60.0, service=StubService()
    )
    assert len(concepts) == 3
    assert [c.id for c in concepts] == ["t1", "t2", "t3"]
    valid = {o.timestamp for o in build_frame_options(DNA, MOMENTS, 60.0)}
    assert all(c.timestamp in valid for c in concepts)


def test_frames_extracted_from_real_video(long_sample_video, storage_dirs):
    concepts = generate_thumbnail_concepts(
        "p2", long_sample_video, DNA, MOMENTS, duration=60.0, service=StubService()
    )
    for concept in concepts:
        assert concept.frame_url is not None
        path = storage_dirs["thumbnails"] / concept.frame_url.rsplit("/", 1)[-1]
        assert path.exists() and path.stat().st_size > 1000


def test_bad_frame_id_falls_back_instead_of_dropping(long_sample_video):
    payload = {"concepts": [_entry(999), _entry(-4), _entry(0)]}
    concepts = generate_thumbnail_concepts(
        "p3", long_sample_video, DNA, MOMENTS, duration=60.0, service=StubService(payload)
    )
    assert len(concepts) == 3
    assert all(c.timestamp is not None for c in concepts)


def test_missing_video_still_returns_specs():
    """Specs are useful even when no frame can be rendered."""
    concepts = generate_thumbnail_concepts(
        "p4", None, DNA, MOMENTS, duration=60.0, service=StubService()
    )
    assert len(concepts) == 3
    assert all(c.frame_url is None for c in concepts)
    assert all(c.headline for c in concepts)


def test_capped_at_three_concepts(long_sample_video):
    payload = {"concepts": [_entry(0, f"H{i}") for i in range(9)]}
    concepts = generate_thumbnail_concepts(
        "p5", long_sample_video, DNA, MOMENTS, duration=60.0, service=StubService(payload)
    )
    assert len(concepts) == 3


def test_no_timestamps_raises():
    with pytest.raises(AnalysisError, match="No usable timestamps"):
        generate_thumbnail_concepts("p6", None, ContentDNA(), [], service=StubService())


def test_empty_model_response_raises():
    with pytest.raises(AnalysisError, match="no thumbnail concepts"):
        generate_thumbnail_concepts(
            "p7", None, DNA, MOMENTS, service=StubService({"concepts": []})
        )
