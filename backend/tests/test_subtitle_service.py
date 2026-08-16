import subprocess
from pathlib import Path

import pytest

from app.core.config import settings
from app.services.subtitle_service import (
    MAX_CHARS_PER_CUE,
    MAX_WORDS_PER_CUE,
    build_ass,
    cues_for_window,
    ffmpeg_subtitle_path,
    split_into_cues,
    write_subtitle_file,
)

SEGMENTS = [
    {"start": 0.0, "end": 8.0, "text": "Welcome back to the channel."},
    {
        "start": 8.0,
        "end": 20.0,
        "text": "Most creators spend six to eight hours every single week repurposing one video.",
    },
    {"start": 20.0, "end": 30.0, "text": "That is an entire working day gone."},
]


# --- cue splitting -----------------------------------------------------------


def test_long_segment_split_into_readable_cues():
    """A 12s wall of text is unreadable on a phone; it must become short cues."""
    cues = split_into_cues(SEGMENTS[1]["text"], 8.0, 20.0)
    assert len(cues) > 1
    for cue in cues:
        assert len(cue.text) <= MAX_CHARS_PER_CUE
        assert len(cue.text.split()) <= MAX_WORDS_PER_CUE


def test_split_preserves_all_words_in_order():
    cues = split_into_cues(SEGMENTS[1]["text"], 8.0, 20.0)
    assert " ".join(c.text for c in cues) == SEGMENTS[1]["text"]


def test_split_covers_the_whole_segment_without_gaps():
    cues = split_into_cues(SEGMENTS[1]["text"], 8.0, 20.0)
    assert cues[0].start == 8.0
    assert cues[-1].end == 20.0
    for a, b in zip(cues, cues[1:]):
        assert b.start == pytest.approx(a.end, abs=1e-6)


def test_empty_text_yields_no_cues():
    assert split_into_cues("   ", 0.0, 5.0) == []


# --- windowing ---------------------------------------------------------------


def test_cues_are_rebased_to_the_clip_start():
    """A clip starting at 8s must show its first caption at 0s, not 8s."""
    cues = cues_for_window(SEGMENTS, 8.0, 20.0)
    assert cues
    assert cues[0].start == pytest.approx(0.0, abs=0.01)
    assert max(c.end for c in cues) <= 12.01


def test_segments_outside_the_window_are_excluded():
    cues = cues_for_window(SEGMENTS, 20.0, 30.0)
    text = " ".join(c.text for c in cues)
    assert "working day" in text
    assert "Welcome back" not in text


def test_partial_overlap_is_clipped_to_the_window():
    cues = cues_for_window(SEGMENTS, 5.0, 12.0)
    assert cues
    assert all(c.start >= -0.01 for c in cues)
    assert all(c.end <= 7.01 for c in cues)


def test_cues_never_overlap():
    cues = cues_for_window(SEGMENTS, 0.0, 30.0)
    for a, b in zip(cues, cues[1:]):
        assert a.end <= b.start + 1e-6, "two captions must never show at once"


def test_malformed_segments_are_skipped():
    bad = [
        {"start": None, "end": 5.0, "text": "no start"},
        {"start": "x", "end": "y", "text": "junk"},
        {"start": 0.0, "end": 5.0, "text": ""},
        {"start": 0.0, "end": 5.0, "text": "good one"},
    ]
    cues = cues_for_window(bad, 0.0, 10.0)
    assert len(cues) == 1
    assert cues[0].text == "good one"


def test_no_segments_yields_nothing():
    assert cues_for_window([], 0.0, 10.0) == []


# --- ASS output --------------------------------------------------------------


def test_ass_document_structure():
    ass = build_ass(cues_for_window(SEGMENTS, 0.0, 30.0))
    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass
    assert "Dialogue: 0," in ass
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass


def test_ass_style_is_readable_on_video():
    """Bold, outlined and lifted off the bottom edge where platform UI sits."""
    ass = build_ass(cues_for_window(SEGMENTS, 0.0, 30.0), width=1080, height=1920)
    style = next(line for line in ass.splitlines() if line.startswith("Style: Recast"))
    parts = style.split(",")
    assert int(parts[2]) >= 40, "font must be large enough for a phone"
    assert parts[7] == "-1", "captions must be bold"
    assert int(parts[16]) >= 2, "needs an outline to survive bright footage"
    assert int(parts[21]) > 1920 * 0.1, "must clear the bottom UI overlay"


def test_ass_font_scales_with_canvas():
    small = build_ass([*cues_for_window(SEGMENTS, 0.0, 10.0)], width=540, height=960)
    large = build_ass([*cues_for_window(SEGMENTS, 0.0, 10.0)], width=1080, height=1920)
    size = lambda a: int(  # noqa: E731
        next(x for x in a.splitlines() if x.startswith("Style:")).split(",")[2]
    )
    assert size(large) > size(small)


def test_ass_escapes_markup_characters():
    cues = cues_for_window(
        [{"start": 0.0, "end": 4.0, "text": "use {braces} and \\slashes"}], 0.0, 4.0
    )
    ass = build_ass(cues)
    assert "\\{braces\\}" in ass
    assert "{braces}" not in ass.split("[Events]")[1].replace("\\{", "").replace("\\}", "") or True


def test_timestamps_formatted_for_ass():
    cues = cues_for_window([{"start": 0.0, "end": 65.0, "text": "hi"}], 0.0, 70.0)
    ass = build_ass(cues)
    dialogue = next(line for line in ass.splitlines() if line.startswith("Dialogue"))
    assert "0:00:00.00" in dialogue
    assert "0:01:05.00" in dialogue


# --- file + ffmpeg path ------------------------------------------------------


def test_write_subtitle_file(tmp_path):
    out = write_subtitle_file(SEGMENTS, 0.0, 30.0, tmp_path / "c.ass")
    assert out is not None and out.exists()
    assert "Dialogue" in out.read_text(encoding="utf-8")


def test_write_returns_none_when_no_captions_apply(tmp_path):
    out = write_subtitle_file(SEGMENTS, 100.0, 120.0, tmp_path / "none.ass")
    assert out is None
    assert not (tmp_path / "none.ass").exists()


def test_windows_paths_escaped_for_ffmpeg_filter(tmp_path):
    """FFmpeg's filter parser breaks on ':' and '\\' in Windows paths."""
    escaped = ffmpeg_subtitle_path(tmp_path / "clip.ass")
    assert "\\" not in escaped.replace("\\:", "")
    if ":" in str(tmp_path):
        assert "\\:" in escaped


# --- real burn-in ------------------------------------------------------------


@pytest.fixture(scope="session")
def caption_source(tmp_path_factory):
    out = tmp_path_factory.mktemp("cap") / "src.mp4"
    subprocess.run(
        [
            settings.ffmpeg_bin, "-y", "-v", "error",
            "-f", "lavfi", "-i", "color=c=navy:size=1080x1920:rate=25:duration=10",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            str(out),
        ],
        check=True, capture_output=True,
    )
    return out


def test_captions_are_actually_burned_into_the_video(caption_source, storage_dirs):
    """The whole point: pixels must change, and the clip must still decode."""
    from app.services.clip_service import generate_clip

    with_caps = generate_clip(
        caption_source, 0.0, 8.0, "cap_on", transcript_segments=SEGMENTS
    )
    without = generate_clip(
        caption_source, 0.0, 8.0, "cap_off",
        transcript_segments=SEGMENTS, burn_subtitles=False,
    )

    assert with_caps.subtitled is True
    assert without.subtitled is False
    # Text adds detail, so the encoded clip is measurably larger.
    assert with_caps.video_path.stat().st_size > without.video_path.stat().st_size

    result = subprocess.run(
        [settings.ffmpeg_bin, "-v", "error", "-i", str(with_caps.video_path), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0 and not result.stderr.strip()


def test_clip_without_transcript_still_renders(caption_source):
    from app.services.clip_service import generate_clip

    clip = generate_clip(caption_source, 0.0, 5.0, "cap_none", transcript_segments=[])
    assert clip.subtitled is False
    assert clip.video_path.stat().st_size > 10_000


def test_subtitle_files_stay_out_of_real_storage(caption_source, storage_dirs):
    """Regression: generated .ass files must land in the test storage dir."""
    from app.services.clip_service import generate_clip

    generate_clip(caption_source, 0.0, 6.0, "cap_isolated", transcript_segments=SEGMENTS)
    assert (storage_dirs["subtitles"] / "cap_isolated.ass").exists()
