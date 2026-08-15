"""Real FFmpeg tests for short-video generation. No mocking of ffmpeg."""

import subprocess

import pytest

from app.core.config import settings
from app.services.clip_service import (
    _is_already_vertical,
    generate_clip,
    generate_thumbnail,
)
from app.services.media_service import MediaProcessingError, extract_metadata


def _make_video(path, width, height, duration=20, gop=None):
    cmd = [
        settings.ffmpeg_bin, "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc=duration={duration}:size={width}x{height}:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264",
    ]
    if gop:
        cmd += ["-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0"]
    cmd += ["-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


@pytest.fixture(scope="session")
def landscape_video(tmp_path_factory):
    return _make_video(tmp_path_factory.mktemp("land") / "land.mp4", 1920, 1080)


@pytest.fixture(scope="session")
def portrait_video(tmp_path_factory):
    return _make_video(tmp_path_factory.mktemp("port") / "port.mp4", 1080, 1920)


@pytest.fixture(scope="session")
def square_video(tmp_path_factory):
    return _make_video(tmp_path_factory.mktemp("sq") / "sq.mp4", 1080, 1080)


@pytest.fixture(scope="session")
def portrait_dense_gop(tmp_path_factory):
    """Portrait source with 1s keyframes, so a stream copy can be accurate."""
    return _make_video(tmp_path_factory.mktemp("gop") / "gop.mp4", 1080, 1920, gop=30)


# --- aspect detection --------------------------------------------------------


def test_is_already_vertical():
    assert _is_already_vertical(1080, 1920)
    assert _is_already_vertical(720, 1280)
    assert not _is_already_vertical(1920, 1080)
    assert not _is_already_vertical(1080, 1080)
    assert not _is_already_vertical(0, 0)


# --- real rendering ----------------------------------------------------------


def test_landscape_is_reframed_to_vertical(landscape_video):
    clip = generate_clip(landscape_video, 3.0, 11.0, "t_land")
    meta = extract_metadata(clip.video_path)
    assert (meta.width, meta.height) == (1080, 1920)
    assert clip.vertical is True
    assert abs(clip.duration - 8.0) < 0.5
    assert meta.size_bytes > 10_000  # a real encode, not an empty container


def test_square_is_reframed_to_vertical(square_video):
    clip = generate_clip(square_video, 2.0, 10.0, "t_square")
    meta = extract_metadata(clip.video_path)
    assert (meta.width, meta.height) == (1080, 1920)
    assert clip.vertical is True


def test_portrait_source_keeps_its_dimensions(portrait_video):
    """Already 9:16 -- must not be needlessly re-scaled."""
    clip = generate_clip(portrait_video, 2.0, 10.0, "t_port")
    meta = extract_metadata(clip.video_path)
    assert (meta.width, meta.height) == (1080, 1920)
    assert clip.vertical is True


def test_stream_copy_used_when_cut_is_accurate(portrait_dense_gop):
    """'Avoid unnecessary re-encoding' must actually happen, not be dead code."""
    clip = generate_clip(portrait_dense_gop, 6.0, 14.0, "t_copy")
    assert clip.reencoded is False
    assert abs(clip.duration - 8.0) < 0.75


def test_reencodes_when_stream_copy_would_be_inaccurate(portrait_video):
    """Sparse keyframes make a copy drift, so accuracy must win over speed."""
    clip = generate_clip(portrait_video, 3.3, 9.7, "t_accurate")
    assert clip.reencoded is True
    assert abs(clip.duration - 6.4) < 0.5


def test_vertical_disabled_keeps_landscape(landscape_video):
    clip = generate_clip(landscape_video, 2.0, 8.0, "t_noreframe", vertical=False)
    meta = extract_metadata(clip.video_path)
    assert meta.width > meta.height
    assert clip.vertical is False


def test_audio_stream_is_preserved(landscape_video):
    clip = generate_clip(landscape_video, 2.0, 8.0, "t_audio")
    result = subprocess.run(
        [
            settings.ffprobe_bin, "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=codec_name", "-of", "csv=p=0",
            str(clip.video_path),
        ],
        capture_output=True, text=True, check=True,
    )
    assert "aac" in result.stdout


def test_clip_is_playable_and_decodes(landscape_video):
    """Decode every frame -- catches truncated or corrupt output."""
    clip = generate_clip(landscape_video, 2.0, 6.0, "t_decode")
    result = subprocess.run(
        [settings.ffmpeg_bin, "-v", "error", "-i", str(clip.video_path), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert result.stderr.strip() == "", f"decode errors: {result.stderr}"


# --- thumbnails --------------------------------------------------------------


def test_thumbnail_generated_with_clip(landscape_video):
    clip = generate_clip(landscape_video, 2.0, 10.0, "t_thumb")
    assert clip.thumbnail_path.exists()
    assert clip.thumbnail_path.suffix == ".jpg"
    assert clip.thumbnail_path.stat().st_size > 1000

    meta = extract_metadata(clip.thumbnail_path)
    assert (meta.width, meta.height) == (1080, 1920)


def test_thumbnail_from_missing_clip_raises(tmp_path):
    with pytest.raises(MediaProcessingError, match="Clip not found"):
        generate_thumbnail(tmp_path / "nope.mp4", "x")


# --- validation --------------------------------------------------------------


def test_invalid_range_rejected(landscape_video):
    with pytest.raises(MediaProcessingError, match="Invalid clip range"):
        generate_clip(landscape_video, 10.0, 10.0, "t_bad")
    with pytest.raises(MediaProcessingError, match="Invalid clip range"):
        generate_clip(landscape_video, 10.0, 5.0, "t_bad2")


def test_start_beyond_video_rejected(landscape_video):
    with pytest.raises(MediaProcessingError, match="only"):
        generate_clip(landscape_video, 500.0, 520.0, "t_past")


def test_end_beyond_video_is_clamped(landscape_video):
    """A moment running to the very end must not silently produce an empty file."""
    clip = generate_clip(landscape_video, 15.0, 999.0, "t_clamp")
    assert clip.end <= 20.5
    assert clip.duration > 1.0
    assert clip.video_path.stat().st_size > 10_000


def test_missing_source_raises(tmp_path):
    with pytest.raises(MediaProcessingError, match="Video file not found"):
        generate_clip(tmp_path / "nope.mp4", 0.0, 5.0, "t_missing")
