import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import AUDIO_DIR, CLIPS_DIR, settings

logger = logging.getLogger(__name__)


class MediaProcessingError(RuntimeError):
    """Raised when ffmpeg/ffprobe fails or a file is not a valid, readable video."""


@dataclass
class VideoMetadata:
    duration_seconds: float
    width: int
    height: int
    fps: float
    size_bytes: int


def _run(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise MediaProcessingError(
            f"'{command[0]}' was not found on PATH. Install FFmpeg and ensure it is accessible."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaProcessingError(f"Command timed out: {' '.join(command)}") from exc

    if result.returncode != 0:
        raise MediaProcessingError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n{result.stderr.strip()}"
        )
    return result.stdout


def _parse_fps(rate: str) -> float:
    if "/" in rate:
        num, _, denom = rate.partition("/")
        denom_val = float(denom) if float(denom) != 0 else 1.0
        return round(float(num) / denom_val, 3)
    return round(float(rate), 3)


def extract_metadata(video_path: Path) -> VideoMetadata:
    """Run ffprobe against a real file and parse duration/resolution/fps/size."""
    if not video_path.exists():
        raise MediaProcessingError(f"Video file not found: {video_path}")

    stdout = _run(
        [
            settings.ffprobe_bin,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            "-select_streams",
            "v:0",
            str(video_path),
        ]
    )

    try:
        probe = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise MediaProcessingError(f"Could not parse ffprobe output for {video_path.name}") from exc

    streams = probe.get("streams") or []
    if not streams:
        raise MediaProcessingError(f"No video stream found in {video_path.name}")
    video_stream = streams[0]
    fmt = probe.get("format") or {}

    duration_raw = video_stream.get("duration") or fmt.get("duration")
    if duration_raw is None:
        raise MediaProcessingError(f"Could not determine duration for {video_path.name}")

    return VideoMetadata(
        duration_seconds=round(float(duration_raw), 3),
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        fps=_parse_fps(video_stream.get("r_frame_rate", "0/1")),
        size_bytes=video_path.stat().st_size,
    )


def cut_clip(video_path: Path, start: float, end: float, output_name: str) -> Path:
    """Cut [start, end) out of a video into CLIPS_DIR, re-encoding for frame accuracy."""
    if not video_path.exists():
        raise MediaProcessingError(f"Video file not found: {video_path}")
    if end <= start:
        raise MediaProcessingError(f"Invalid clip range: {start}s to {end}s")

    # Clamp to the real video length: a range past the end yields an empty file.
    video_duration = extract_metadata(video_path).duration_seconds
    if start >= video_duration:
        raise MediaProcessingError(
            f"Clip starts at {start:.1f}s but the video is only {video_duration:.1f}s long"
        )
    end = min(end, video_duration)

    clip_path = CLIPS_DIR / f"{output_name}.mp4"
    _run(
        [
            settings.ffmpeg_bin,
            "-y",
            # -ss before -i seeks fast; re-encoding keeps the cut frame-accurate
            # so the clip starts exactly on the spoken word.
            "-ss",
            f"{start:.3f}",
            "-to",
            f"{end:.3f}",
            "-i",
            str(video_path),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(clip_path),
        ]
    )

    if not clip_path.exists() or clip_path.stat().st_size == 0:
        raise MediaProcessingError(f"Clip generation produced no output for {video_path.name}")

    logger.info(
        "Cut clip %s (%.1fs-%.1fs, %d bytes)",
        clip_path.name,
        start,
        end,
        clip_path.stat().st_size,
    )
    return clip_path


def compress_audio_for_upload(audio_path: Path) -> Path:
    """Losslessly compress 16kHz mono WAV to FLAC for hosted transcription APIs.

    Hosted APIs cap upload size (25MB on Groq's free tier). FLAC roughly halves
    the payload, which about doubles the length of video that fits.
    """
    if not audio_path.exists():
        raise MediaProcessingError(f"Audio file not found: {audio_path}")

    flac_path = audio_path.with_suffix(".flac")
    _run([settings.ffmpeg_bin, "-y", "-i", str(audio_path), "-c:a", "flac", str(flac_path)])

    if not flac_path.exists() or flac_path.stat().st_size == 0:
        raise MediaProcessingError(f"FLAC conversion produced no output for {audio_path.name}")

    logger.info(
        "Compressed %s for upload: %d -> %d bytes",
        audio_path.name,
        audio_path.stat().st_size,
        flac_path.stat().st_size,
    )
    return flac_path


def extract_audio(video_path: Path, project_id: str) -> Path:
    """Extract 16kHz mono PCM WAV audio from a video, suitable for transcription."""
    if not video_path.exists():
        raise MediaProcessingError(f"Video file not found: {video_path}")

    audio_path = AUDIO_DIR / f"{project_id}.wav"
    _run(
        [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            str(audio_path),
        ]
    )

    if not audio_path.exists() or audio_path.stat().st_size == 0:
        raise MediaProcessingError(f"Audio extraction produced no output for {video_path.name}")

    logger.info("Extracted audio for project %s: %s (%d bytes)", project_id, audio_path.name, audio_path.stat().st_size)
    return audio_path
