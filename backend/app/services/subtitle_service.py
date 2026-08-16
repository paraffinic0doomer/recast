"""Burned-in captions for generated shorts.

Short-form video is overwhelmingly watched on mute, so captions are not a nice
to have. RECAST already has a timestamped transcript, so a clip's captions are
derived from it rather than re-transcribing.

Subtitles are written as ASS (not SRT) because ASS carries styling: the large,
bold, outlined, centre-lower look that reads on a phone over any footage.

Timing note: Whisper returns *segment* level timings, not word level. A long
segment is split into short readable cues and the segment's duration is shared
between them in proportion to their length. Cue boundaries inside a segment are
therefore approximate; segment boundaries themselves are exact.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Roughly one comfortable line of phone-width caption.
MAX_CHARS_PER_CUE = 42
MAX_WORDS_PER_CUE = 7
MIN_CUE_SECONDS = 0.6


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _format_time(seconds: float) -> str:
    """ASS timestamps: H:MM:SS.cc (centiseconds)."""
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _escape(text: str) -> str:
    """ASS treats braces and backslashes as markup."""
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", " ")
        .strip()
    )


def split_into_cues(text: str, start: float, end: float) -> list[Cue]:
    """Break one transcript segment into short cues sharing its duration."""
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and (
            len(candidate) > MAX_CHARS_PER_CUE or len(current) >= MAX_WORDS_PER_CUE
        ):
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))

    total_chars = sum(len(c) for c in chunks) or 1
    duration = max(0.0, end - start)

    cues: list[Cue] = []
    cursor = start
    for i, chunk in enumerate(chunks):
        share = duration * (len(chunk) / total_chars)
        cue_end = end if i == len(chunks) - 1 else cursor + share
        cues.append(Cue(start=cursor, end=max(cue_end, cursor + 0.01), text=chunk))
        cursor = cue_end
    return cues


def cues_for_window(
    segments: list[dict], window_start: float, window_end: float
) -> list[Cue]:
    """Cues covering [window_start, window_end), re-timed to start at zero."""
    cues: list[Cue] = []

    for segment in segments:
        try:
            seg_start = float(segment.get("start"))
            seg_end = float(segment.get("end"))
        except (TypeError, ValueError):
            continue
        text = str(segment.get("text") or "").strip()
        if not text or seg_end <= window_start or seg_start >= window_end:
            continue

        for cue in split_into_cues(text, seg_start, seg_end):
            # Clip to the window, then rebase so 0 is the start of the clip.
            start = max(cue.start, window_start) - window_start
            end = min(cue.end, window_end) - window_start
            if end - start < 0.05:
                continue
            cues.append(Cue(start=start, end=end, text=cue.text))

    # Never let two cues show at once.
    cues.sort(key=lambda c: c.start)
    for earlier, later in zip(cues, cues[1:]):
        if earlier.end > later.start:
            earlier.end = later.start
    return [c for c in cues if c.end > c.start]


def build_ass(
    cues: list[Cue],
    width: int = 1080,
    height: int = 1920,
    font_size: int | None = None,
) -> str:
    """An ASS document styled for vertical short-form video."""
    # Scale with the canvas so the same style works at any resolution.
    size = font_size or max(28, round(height * 0.042))
    outline = max(2, round(size * 0.10))
    shadow = max(1, round(size * 0.05))
    # Sit above the platform UI that overlays the bottom of the screen.
    margin_v = round(height * 0.18)
    margin_h = round(width * 0.08)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Recast,Arial,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [
        f"Dialogue: 0,{_format_time(c.start)},{_format_time(c.end)},Recast,,0,0,0,,{_escape(c.text)}"
        for c in cues
    ]
    return header + "\n".join(lines) + "\n"


def write_subtitle_file(
    segments: list[dict],
    window_start: float,
    window_end: float,
    destination: Path,
    width: int = 1080,
    height: int = 1920,
) -> Path | None:
    """Write an .ass file for a clip window. Returns None when there is nothing to show."""
    cues = cues_for_window(segments, window_start, window_end)
    if not cues:
        logger.info("No transcript cues fall inside %.1f-%.1fs; skipping captions",
                    window_start, window_end)
        return None

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_ass(cues, width, height), encoding="utf-8")
    logger.info("Wrote %d caption cues to %s", len(cues), destination.name)
    return destination


def ffmpeg_subtitle_path(path: Path) -> str:
    """Escape a path for use inside FFmpeg's `subtitles=` filter.

    The filter parser treats ':' and '\\' specially, which breaks Windows paths
    like C:\\Users\\... unless both are escaped.
    """
    text = str(path.resolve()).replace("\\", "/")
    return text.replace(":", "\\:")
