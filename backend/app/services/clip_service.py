"""Short-video generation.

Cuts a detected moment out of the source video and renders it as a real MP4,
plus a thumbnail frame.

Reframing strategy:
  - Source already ~9:16      -> no reframe needed; stream-copy when the cut is
                                 accurate enough, avoiding a pointless re-encode.
  - Landscape / square source -> 1080x1920 canvas with the footage scaled to fit
                                 and a blurred, zoomed copy behind it. Nothing is
                                 cropped away, so faces and text survive.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.config import CLIPS_DIR, SUBTITLES_DIR, THUMBNAILS_DIR, settings
from app.services.media_service import (
    MediaProcessingError,
    _run,
    extract_metadata,
)
from app.services.subtitle_service import ffmpeg_subtitle_path, write_subtitle_file

logger = logging.getLogger(__name__)

VERTICAL_WIDTH = 1080
VERTICAL_HEIGHT = 1920
TARGET_ASPECT = VERTICAL_WIDTH / VERTICAL_HEIGHT  # 0.5625
ASPECT_TOLERANCE = 0.02
# Accuracy we require from a stream copy before falling back to re-encoding.
COPY_DURATION_TOLERANCE = 0.75
CRF = "20"
PRESET = "veryfast"
# Backdrop blur is computed at 1/4 resolution; sigma scales with it so the
# apparent radius stays the same. See _vertical_filter.
BLUR_DIVISOR = 4
BLUR_SIGMA = 6
# x264 allocates per-thread frame buffers. Small hosts (a 512MB container) run
# out of memory long before they run out of cores, so cap it rather than let
# ffmpeg spawn one thread per CPU.
ENCODE_THREADS = "2"


@dataclass
class GeneratedClip:
    clip_id: str
    video_path: Path
    thumbnail_path: Path
    start: float
    end: float
    duration: float
    width: int
    height: int
    vertical: bool
    reencoded: bool
    subtitled: bool = False


def clip_path_for(clip_id: str) -> Path:
    """Where a rendered clip lives. Single owner of this path convention."""
    return CLIPS_DIR / f"{clip_id}.mp4"


def _vertical_filter() -> str:
    """Blurred-background 9:16 canvas. Keeps the whole frame visible.

    The backdrop is blurred at a quarter resolution and then scaled back up.
    A heavy gaussian on a full 1080x1920 frame is the most memory-hungry step
    in the whole pipeline, and blurring small then upscaling is visually
    indistinguishable -- the result is a blur either way. Sigma is divided by
    the same factor as the resolution so the apparent radius is unchanged.
    """
    bg_w, bg_h = VERTICAL_WIDTH // BLUR_DIVISOR, VERTICAL_HEIGHT // BLUR_DIVISOR
    return (
        "[0:v]split=2[bg][fg];"
        f"[bg]scale={bg_w}:{bg_h}:force_original_aspect_ratio=increase,"
        f"crop={bg_w}:{bg_h},gblur=sigma={BLUR_SIGMA},"
        f"scale={VERTICAL_WIDTH}:{VERTICAL_HEIGHT}[bgblur];"
        f"[fg]scale={VERTICAL_WIDTH}:{VERTICAL_HEIGHT}:force_original_aspect_ratio=decrease[fgscaled];"
        "[bgblur][fgscaled]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )


def _is_already_vertical(width: int, height: int) -> bool:
    if width <= 0 or height <= 0:
        return False
    return abs((width / height) - TARGET_ASPECT) <= ASPECT_TOLERANCE


def _try_stream_copy(video_path: Path, start: float, end: float, out_path: Path) -> bool:
    """Attempt a no-re-encode cut. Returns False if the result is inaccurate.

    Stream copy can only cut on keyframes, so the output can drift. We keep it
    only when the duration lands close to what was asked for.
    """
    requested = end - start
    try:
        _run(
            [
                settings.ffmpeg_bin,
                "-y",
                "-ss",
                f"{start:.3f}",
                "-to",
                f"{end:.3f}",
                "-i",
                str(video_path),
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                "-movflags",
                "+faststart",
                str(out_path),
            ]
        )
    except MediaProcessingError as exc:
        logger.info("Stream copy failed, will re-encode: %s", exc)
        return False

    if not out_path.exists() or out_path.stat().st_size == 0:
        return False

    try:
        actual = extract_metadata(out_path).duration_seconds
    except MediaProcessingError:
        return False

    if abs(actual - requested) > COPY_DURATION_TOLERANCE:
        logger.info(
            "Stream copy drifted (%.2fs vs %.2fs requested); re-encoding for accuracy",
            actual,
            requested,
        )
        return False

    logger.info("Cut %s without re-encoding (%.2fs)", out_path.name, actual)
    return True


def _encode(
    video_path: Path,
    start: float,
    end: float,
    out_path: Path,
    vf: str | None,
    subtitle_file: Path | None = None,
) -> None:
    command = [
        settings.ffmpeg_bin,
        "-y",
        "-ss",
        f"{start:.3f}",
        "-to",
        f"{end:.3f}",
        "-i",
        str(video_path),
    ]
    # Captions are burned in as the final filter step so they sit on top of the
    # reframed picture rather than being scaled with the source.
    if subtitle_file is not None:
        burn = f"subtitles='{ffmpeg_subtitle_path(subtitle_file)}'"
        vf = f"{vf},{burn}" if vf else burn

    if vf:
        command += ["-filter_complex", vf]
    command += [
        "-threads",
        ENCODE_THREADS,
        "-c:v",
        "libx264",
        "-preset",
        PRESET,
        "-crf",
        CRF,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    _run(command)


def generate_thumbnail(clip_path: Path, clip_id: str, at_seconds: float | None = None) -> Path:
    """Grab a representative frame from the clip."""
    if not clip_path.exists():
        raise MediaProcessingError(f"Clip not found: {clip_path}")

    if at_seconds is None:
        # Midpoint avoids fades and black frames at the edges.
        at_seconds = max(0.0, extract_metadata(clip_path).duration_seconds / 2)

    thumb_path = THUMBNAILS_DIR / f"{clip_id}.jpg"
    _run(
        [
            settings.ffmpeg_bin,
            "-y",
            "-ss",
            f"{at_seconds:.3f}",
            "-i",
            str(clip_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(thumb_path),
        ]
    )

    if not thumb_path.exists() or thumb_path.stat().st_size == 0:
        raise MediaProcessingError(f"Thumbnail generation produced no output for {clip_path.name}")

    logger.info("Generated thumbnail %s (%d bytes)", thumb_path.name, thumb_path.stat().st_size)
    return thumb_path


def generate_clip(
    video_path: Path,
    start: float,
    end: float,
    clip_id: str,
    vertical: bool = True,
    transcript_segments: list[dict] | None = None,
    burn_subtitles: bool | None = None,
) -> GeneratedClip:
    """Render a real short video for [start, end) plus a thumbnail.

    When transcript segments are supplied, captions for that window are burned
    into the picture -- short-form is mostly watched on mute.
    """
    if not video_path.exists():
        raise MediaProcessingError(f"Video file not found: {video_path}")
    if end <= start:
        raise MediaProcessingError(f"Invalid clip range: {start}s to {end}s")

    source = extract_metadata(video_path)
    if start >= source.duration_seconds:
        raise MediaProcessingError(
            f"Clip starts at {start:.1f}s but the video is only "
            f"{source.duration_seconds:.1f}s long"
        )
    end = min(end, source.duration_seconds)

    clip_path = clip_path_for(clip_id)
    already_vertical = _is_already_vertical(source.width, source.height)
    needs_reframe = vertical and not already_vertical

    want_subtitles = (
        settings.burn_subtitles if burn_subtitles is None else burn_subtitles
    )
    subtitle_file: Path | None = None
    if want_subtitles and transcript_segments:
        out_w = VERTICAL_WIDTH if needs_reframe else source.width
        out_h = VERTICAL_HEIGHT if needs_reframe else source.height
        try:
            subtitle_file = write_subtitle_file(
                segments=transcript_segments,
                window_start=start,
                window_end=end,
                destination=SUBTITLES_DIR / f"{clip_id}.ass",
                width=out_w,
                height=out_h,
            )
        except OSError as exc:
            # Captions are an enhancement; never lose the clip over them.
            logger.warning("Could not write captions for %s: %s", clip_id, exc)

    reencoded = True
    if not needs_reframe and subtitle_file is None:
        # Nothing to transform, so try to avoid re-encoding entirely.
        if _try_stream_copy(video_path, start, end, clip_path):
            reencoded = False
        else:
            _encode(video_path, start, end, clip_path, None)
    elif not needs_reframe:
        _encode(video_path, start, end, clip_path, None, subtitle_file)
    else:
        logger.info(
            "Reframing %dx%d source to %dx%d vertical",
            source.width,
            source.height,
            VERTICAL_WIDTH,
            VERTICAL_HEIGHT,
        )
        _encode(video_path, start, end, clip_path, _vertical_filter(), subtitle_file)

    if not clip_path.exists() or clip_path.stat().st_size == 0:
        raise MediaProcessingError(f"Clip generation produced no output for {video_path.name}")

    result = extract_metadata(clip_path)
    thumbnail_path = generate_thumbnail(clip_path, clip_id)

    logger.info(
        "Generated clip %s: %dx%d, %.2fs, %d bytes (%s%s)",
        clip_path.name,
        result.width,
        result.height,
        result.duration_seconds,
        result.size_bytes,
        "re-encoded" if reencoded else "stream copy",
        ", captions burned in" if subtitle_file else "",
    )

    return GeneratedClip(
        clip_id=clip_id,
        video_path=clip_path,
        thumbnail_path=thumbnail_path,
        start=start,
        end=end,
        duration=round(result.duration_seconds, 3),
        width=result.width,
        height=result.height,
        vertical=_is_already_vertical(result.width, result.height),
        reencoded=reencoded,
        subtitled=subtitle_file is not None,
    )
