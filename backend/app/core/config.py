from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.key_pool import KeyPool

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
AUDIO_DIR = STORAGE_DIR / "audio"
CLIPS_DIR = STORAGE_DIR / "clips"
THUMBNAILS_DIR = STORAGE_DIR / "thumbnails"
SUBTITLES_DIR = STORAGE_DIR / "subtitles"
GROQ_KEYS_FILE = BASE_DIR / "groq_keys.txt"

_PLACEHOLDER_KEYS = {"", "sk-your-key-here"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_transcription_model: str = "whisper-1"
    # "auto" | "local" | "openai" -- see services/transcription_service.py
    transcription_backend: str = "auto"
    whisper_model_size: str = "base"
    whisper_compute_type: str = "int8"

    # Content analysis: "auto" | "groq" | "local" (Ollama) | "openai"
    analysis_backend: str = "auto"
    groq_api_key: str = ""
    # Comma-separated alternative to groq_keys.txt
    groq_api_keys: str = ""
    # Optional extra keys file, e.g. one kept outside the repo
    groq_keys_file: str = ""
    groq_analysis_model: str = "llama-3.3-70b-versatile"
    groq_transcription_model: str = "whisper-large-v3-turbo"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_timeout: float = 300.0
    openai_analysis_model: str = "gpt-4o-mini"
    # Empty = no image generation backend; thumbnails ship as render-ready specs
    # over real extracted frames. Set when an image API is wired up.
    image_generation_backend: str = ""

    database_url: str = f"sqlite:///{STORAGE_DIR / 'recast.db'}"
    cors_origins: str = "http://localhost:3000"
    # Shared secret required on every request when set. Leave empty for local
    # development; set it before exposing the API through a tunnel.
    access_key: str = ""
    # Burn transcript captions into generated shorts (watched on mute).
    burn_subtitles: bool = True
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def openai_configured(self) -> bool:
        return self.openai_api_key.strip() not in _PLACEHOLDER_KEYS

    @property
    def groq_configured(self) -> bool:
        return groq_key_pool().configured


settings = Settings()

for directory in (
    STORAGE_DIR,
    UPLOADS_DIR,
    AUDIO_DIR,
    CLIPS_DIR,
    THUMBNAILS_DIR,
    SUBTITLES_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def groq_key_pool() -> KeyPool:
    """Shared rotating pool of Groq keys (built once per process)."""
    extra = [Path(settings.groq_keys_file)] if settings.groq_keys_file.strip() else []
    return KeyPool.from_sources(
        keys_file=GROQ_KEYS_FILE,
        keys_csv=settings.groq_api_keys,
        single_key=settings.groq_api_key,
        extra_files=extra,
    )
