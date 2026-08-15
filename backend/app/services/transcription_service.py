"""Transcription service interface.

The pipeline depends only on `TranscriptionService` / `get_transcription_service()`,
so backends can be swapped via environment variables without touching the pipeline.

Backends (selected by TRANSCRIPTION_BACKEND):
  - "groq"   : Groq hosted Whisper (OpenAI-compatible). Fast. Requires GROQ_API_KEY.
  - "local"  : faster-whisper running on this machine. Free, offline, no size limit.
  - "openai" : OpenAI Whisper API. Requires OPENAI_API_KEY.
  - "auto"   : (default) prefer Groq, then local, then OpenAI.

Note: browser speech APIs are deliberately not used. They only transcribe live
microphone input (not uploaded files), do not return segment timestamps -- which
later phases need to cut clips -- and would keep the transcript on the client when
the server needs it for analysis.
"""

import importlib.util
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from openai import OpenAI

from app.core.config import settings
from app.services.media_service import MediaProcessingError, compress_audio_for_upload

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# Groq's free tier caps audio uploads at 25MB.
GROQ_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class TranscriptionError(RuntimeError):
    """Raised when a transcription attempt fails."""


class TranscriptionNotConfiguredError(TranscriptionError):
    """Raised when no transcription backend is configured (e.g. missing API key)."""


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


_LANGUAGE_CODES = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de",
    "italian": "it", "portuguese": "pt", "dutch": "nl", "russian": "ru",
    "chinese": "zh", "japanese": "ja", "korean": "ko", "arabic": "ar",
    "hindi": "hi", "bengali": "bn", "urdu": "ur", "turkish": "tr",
}


def normalize_language(value: str | None) -> str | None:
    """Providers disagree on format: local Whisper returns 'en', Groq returns 'English'."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    return _LANGUAGE_CODES.get(text.lower(), text.lower())


@dataclass
class TranscriptResult:
    text: str
    language: str | None
    duration: float | None
    segments: list[TranscriptSegment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "language": self.language,
            "duration": self.duration,
            "segments": [
                {"start": s.start, "end": s.end, "text": s.text} for s in self.segments
            ],
        }


class TranscriptionService(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptResult: ...


class OpenAIWhisperTranscriptionService(TranscriptionService):
    """Hosted Whisper over any OpenAI-compatible audio API (OpenAI, Groq, ...)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        max_upload_bytes: int = 25 * 1024 * 1024,
        provider: str = "OpenAI",
    ) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        self._model = model
        self._max_upload_bytes = max_upload_bytes
        self._provider = provider

    def _prepare_upload(self, audio_path: Path) -> tuple[Path, bool]:
        """Compress to FLAC to fit the provider's upload cap. Returns (path, is_temp)."""
        try:
            compressed = compress_audio_for_upload(audio_path)
        except MediaProcessingError as exc:
            logger.warning("Could not compress audio, uploading original: %s", exc)
            return audio_path, False
        return compressed, True

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        upload_path, is_temp = self._prepare_upload(audio_path)
        try:
            size = upload_path.stat().st_size
            if size > self._max_upload_bytes:
                raise TranscriptionError(
                    f"Audio is {size / 1024 / 1024:.0f}MB, above the "
                    f"{self._max_upload_bytes / 1024 / 1024:.0f}MB {self._provider} upload limit. "
                    f"Use a shorter video, or set TRANSCRIPTION_BACKEND=local to transcribe "
                    f"on this machine with no size limit."
                )

            logger.info(
                "Transcribing %s with %s model %s (%.1fMB)",
                audio_path.name,
                self._provider,
                self._model,
                size / 1024 / 1024,
            )
            try:
                with upload_path.open("rb") as audio_file:
                    response = self._client.audio.transcriptions.create(
                        model=self._model,
                        file=audio_file,
                        response_format="verbose_json",
                    )
            except Exception as exc:  # SDK raises various APIError subclasses
                raise TranscriptionError(
                    f"{self._provider} transcription request failed: {exc}"
                ) from exc
        finally:
            if is_temp:
                upload_path.unlink(missing_ok=True)

        segments = [
            TranscriptSegment(
                start=float(seg.start), end=float(seg.end), text=seg.text.strip()
            )
            for seg in (response.segments or [])
        ]
        return TranscriptResult(
            text=response.text.strip(),
            language=normalize_language(getattr(response, "language", None)),
            duration=getattr(response, "duration", None),
            segments=segments,
        )


def local_whisper_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


@lru_cache(maxsize=2)
def _load_local_model(model_size: str, compute_type: str):
    """Load (and cache) a faster-whisper model. First call downloads the weights."""
    from faster_whisper import WhisperModel

    logger.info("Loading local Whisper model '%s' (%s)", model_size, compute_type)
    return WhisperModel(model_size, device="cpu", compute_type=compute_type)


class LocalWhisperTranscriptionService(TranscriptionService):
    """Runs Whisper locally via faster-whisper. No API key, no network at inference."""

    def __init__(self, model_size: str, compute_type: str) -> None:
        self._model_size = model_size
        self._compute_type = compute_type

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        logger.info("Transcribing %s with local Whisper (%s)", audio_path.name, self._model_size)
        try:
            model = _load_local_model(self._model_size, self._compute_type)
            segment_iter, info = model.transcribe(
                str(audio_path),
                vad_filter=True,
                # Whisper's default context-carrying makes it terminate early and
                # silently drop trailing speech — which is exactly where CTAs
                # ("subscribe", "link below") live. Disabling it also reduces
                # repetition loops, at the cost of slightly less cross-segment context.
                condition_on_previous_text=False,
            )
            segments = [
                TranscriptSegment(
                    start=round(float(seg.start), 3),
                    end=round(float(seg.end), 3),
                    text=seg.text.strip(),
                )
                for seg in segment_iter
            ]
        except Exception as exc:
            raise TranscriptionError(f"Local Whisper transcription failed: {exc}") from exc

        return TranscriptResult(
            text=" ".join(s.text for s in segments).strip(),
            language=normalize_language(getattr(info, "language", None)),
            duration=round(float(getattr(info, "duration", 0.0)), 3) or None,
            segments=segments,
        )


def _groq_service() -> OpenAIWhisperTranscriptionService:
    return OpenAIWhisperTranscriptionService(
        api_key=settings.groq_api_key,
        model=settings.groq_transcription_model,
        base_url=GROQ_BASE_URL,
        max_upload_bytes=GROQ_MAX_UPLOAD_BYTES,
        provider="Groq",
    )


def get_transcription_service() -> TranscriptionService:
    """Factory for the active transcription backend, selected via environment variables."""
    backend = settings.transcription_backend.strip().lower()

    if backend == "groq":
        if not settings.groq_configured:
            raise TranscriptionNotConfiguredError(
                "TRANSCRIPTION_BACKEND=groq but GROQ_API_KEY is not set in backend/.env."
            )
        return _groq_service()

    if backend == "local":
        if not local_whisper_available():
            raise TranscriptionNotConfiguredError(
                "TRANSCRIPTION_BACKEND=local but faster-whisper is not installed. "
                "Run: pip install faster-whisper"
            )
        return LocalWhisperTranscriptionService(
            settings.whisper_model_size, settings.whisper_compute_type
        )

    if backend == "openai":
        if not settings.openai_configured:
            raise TranscriptionNotConfiguredError(
                "TRANSCRIPTION_BACKEND=openai but OPENAI_API_KEY is not set in backend/.env."
            )
        return OpenAIWhisperTranscriptionService(
            api_key=settings.openai_api_key, model=settings.openai_transcription_model
        )

    if backend != "auto":
        raise TranscriptionNotConfiguredError(
            f"Unknown TRANSCRIPTION_BACKEND '{backend}'. Use 'auto', 'groq', 'local', or 'openai'."
        )

    # auto: hosted Groq is far faster than CPU Whisper; fall back to local, which
    # has no upload-size limit and works offline.
    if settings.groq_configured:
        return _groq_service()
    if local_whisper_available():
        return LocalWhisperTranscriptionService(
            settings.whisper_model_size, settings.whisper_compute_type
        )
    if settings.openai_configured:
        return OpenAIWhisperTranscriptionService(
            api_key=settings.openai_api_key, model=settings.openai_transcription_model
        )

    raise TranscriptionNotConfiguredError(
        "No transcription backend available. Set GROQ_API_KEY in backend/.env, "
        "install local Whisper (pip install faster-whisper), or set OPENAI_API_KEY."
    )
