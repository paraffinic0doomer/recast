import pytest

from app.schemas.content_dna import ContentDNA
from app.schemas.moment import BestMoment, MomentScores
from app.services.analysis_service import AnalysisError
from app.services.moment_service import (
    build_candidate_windows,
    build_moment_prompt,
    detect_moments,
    remove_overlapping,
)

SEGMENTS = [
    {"start": 0.0, "end": 8.0, "text": "Welcome back to the channel."},
    {"start": 8.0, "end": 19.0, "text": "Most creators waste hours repurposing."},
    {"start": 19.0, "end": 29.0, "text": "What if one upload did everything?"},
    {"start": 29.0, "end": 40.0, "text": "Our tool finds the best moments."},
    {"start": 40.0, "end": 52.0, "text": "Subscribe for more breakdowns."},
]


# --- windowing ---------------------------------------------------------------


def test_windows_align_to_real_segment_boundaries():
    windows = build_candidate_windows(SEGMENTS)
    starts = {s["start"] for s in SEGMENTS}
    ends = {s["end"] for s in SEGMENTS}
    assert windows
    for w in windows:
        assert w.start in starts, f"{w.start} is not a real segment start"
        assert w.end in ends, f"{w.end} is not a real segment end"


def test_windows_respect_duration_bounds():
    windows = build_candidate_windows(SEGMENTS, min_duration=12.0, max_duration=30.0)
    assert windows
    for w in windows:
        assert 12.0 <= w.duration <= 30.0


def test_windows_are_unique():
    windows = build_candidate_windows(SEGMENTS)
    keys = [(w.start, w.end) for w in windows]
    assert len(keys) == len(set(keys))


def test_short_transcript_falls_back_to_whole_window():
    """A video shorter than the minimum must still yield a candidate."""
    short = [{"start": 0.0, "end": 5.0, "text": "Very short clip."}]
    windows = build_candidate_windows(short, min_duration=12.0)
    assert len(windows) == 1
    assert windows[0].start == 0.0
    assert windows[0].end == 5.0


def test_empty_segments_yield_no_windows():
    assert build_candidate_windows([]) == []
    assert build_candidate_windows([{"text": "no timings"}]) == []


def test_window_text_concatenates_covered_segments():
    windows = build_candidate_windows(SEGMENTS, min_duration=12.0, max_duration=20.0)
    w = next(w for w in windows if w.start == 0.0 and w.end == 19.0)
    assert "Welcome back" in w.text
    assert "waste hours" in w.text


def test_candidate_count_is_capped():
    many = [
        {"start": float(i * 5), "end": float((i + 1) * 5), "text": f"seg {i}"}
        for i in range(60)
    ]
    windows = build_candidate_windows(many)
    assert len(windows) <= 40
    assert [w.id for w in windows] == list(range(len(windows)))  # ids re-indexed


# --- overlap suppression -----------------------------------------------------


def _moment(start, end, score):
    return BestMoment(
        start=start,
        end=end,
        scores=MomentScores(
            hook_strength=score,
            information_value=score,
            standalone_quality=score,
            emotional_interest=score,
        ),
    )


def test_overlapping_moments_removed_keeping_highest_score():
    moments = [_moment(0, 30, 70), _moment(5, 32, 90), _moment(60, 90, 80)]
    kept = remove_overlapping(moments)
    assert len(kept) == 2
    assert kept[0].start == 5  # the higher-scoring of the overlapping pair
    assert kept[1].start == 60


def test_contained_moment_is_removed():
    """A short clip fully inside a longer one is a duplicate, not a new moment."""
    kept = remove_overlapping([_moment(0, 60, 90), _moment(10, 25, 85)])
    assert len(kept) == 1
    assert kept[0].duration == 60


def test_adjacent_non_overlapping_moments_both_kept():
    kept = remove_overlapping([_moment(0, 30, 90), _moment(30, 60, 85)])
    assert len(kept) == 2


# --- prompt ------------------------------------------------------------------


def test_prompt_lists_window_ids_and_forbids_timestamps():
    windows = build_candidate_windows(SEGMENTS)
    prompt = build_moment_prompt(windows, None)
    assert "id=0" in prompt
    assert "Never output timestamps" in prompt


def test_prompt_includes_content_dna_context():
    dna = ContentDNA.model_validate(
        {"primary_topic": "Repurposing", "audience": "Creators", "tone": "Educational"}
    )
    prompt = build_moment_prompt(build_candidate_windows(SEGMENTS), dna)
    assert "Repurposing" in prompt
    assert "Creators" in prompt


# --- detection ---------------------------------------------------------------


class StubService:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def complete_json(self, prompt, system=None):
        self.prompts.append(prompt)
        return self.payload


def _entry(window_id, score=90, title="T"):
    return {
        "id": window_id,
        "title": title,
        "hook": "hook line",
        "reason": "because it stands alone",
        "scores": {
            "hook_strength": score,
            "information_value": score,
            "standalone_quality": score,
            "emotional_interest": score,
        },
    }


def test_detect_moments_uses_window_timestamps_not_model_values():
    """Even if the model emits its own timestamps, real window bounds must win."""
    windows = build_candidate_windows(SEGMENTS)
    target = windows[0]
    rogue = dict(_entry(target.id))
    rogue["start"] = 999.0
    rogue["end"] = 1234.0

    moments = detect_moments({"segments": SEGMENTS}, None, StubService({"moments": [rogue]}))
    assert len(moments) == 1
    assert moments[0].start == target.start
    assert moments[0].end == target.end


def test_unknown_window_id_is_discarded():
    windows = build_candidate_windows(SEGMENTS)
    payload = {"moments": [_entry(windows[0].id), _entry(9999)]}
    moments = detect_moments({"segments": SEGMENTS}, None, StubService(payload))
    assert len(moments) == 1


def test_all_ids_invalid_raises_rather_than_guessing():
    payload = {"moments": [_entry(4242), _entry(777)]}
    with pytest.raises(AnalysisError, match="valid candidate window"):
        detect_moments({"segments": SEGMENTS}, None, StubService(payload))


def test_detect_moments_returns_at_most_five():
    windows = build_candidate_windows(SEGMENTS)
    payload = {"moments": [_entry(w.id, score=90 - i) for i, w in enumerate(windows[:12])]}
    moments = detect_moments({"segments": SEGMENTS}, None, StubService(payload))
    assert 1 <= len(moments) <= 5


def test_detect_moments_sorted_by_score_desc():
    windows = build_candidate_windows(SEGMENTS)
    non_overlapping = [w for w in windows if w.start == 0.0][:1] + [
        w for w in windows if w.start >= 29.0
    ][:1]
    payload = {
        "moments": [
            _entry(non_overlapping[0].id, score=60),
            _entry(non_overlapping[1].id, score=95, title="Better"),
        ]
    }
    moments = detect_moments({"segments": SEGMENTS}, None, StubService(payload))
    assert moments[0].score >= moments[-1].score
    assert moments[0].title == "Better"


def test_overall_score_derived_from_components():
    windows = build_candidate_windows(SEGMENTS)
    entry = _entry(windows[0].id)
    entry["scores"] = {
        "hook_strength": 100,
        "information_value": 80,
        "standalone_quality": 60,
        "emotional_interest": 40,
    }
    entry["score"] = 5  # model contradicts its own breakdown
    moments = detect_moments({"segments": SEGMENTS}, None, StubService({"moments": [entry]}))
    assert moments[0].score == 70


def test_no_segments_raises():
    with pytest.raises(AnalysisError, match="no usable timestamped segments"):
        detect_moments({"segments": []}, None, StubService({"moments": []}))


def test_empty_model_response_raises():
    with pytest.raises(AnalysisError, match="no moments"):
        detect_moments({"segments": SEGMENTS}, None, StubService({"moments": []}))


def test_scores_are_clamped_to_valid_range():
    windows = build_candidate_windows(SEGMENTS)
    entry = _entry(windows[0].id)
    entry["scores"] = {
        "hook_strength": 150,
        "information_value": -20,
        "standalone_quality": "88",
        "emotional_interest": None,
    }
    moments = detect_moments({"segments": SEGMENTS}, None, StubService({"moments": [entry]}))
    s = moments[0].scores
    assert s.hook_strength == 100
    assert s.information_value == 0
    assert s.standalone_quality == 88
    assert s.emotional_interest == 0


def test_window_bounds_are_exact_segment_values_not_rounded():
    """Rounding would break joining moments back to transcript segments by equality."""
    precise = [
        {"start": 0.0, "end": 27.199999, "text": "a"},
        {"start": 27.199999, "end": 43.859997, "text": "b"},
        {"start": 43.859997, "end": 69.964, "text": "c"},
    ]
    windows = build_candidate_windows(precise)
    starts = {s["start"] for s in precise}
    ends = {s["end"] for s in precise}
    assert windows
    for w in windows:
        assert w.start in starts, f"{w.start!r} is not an exact segment start"
        assert w.end in ends, f"{w.end!r} is not an exact segment end"
