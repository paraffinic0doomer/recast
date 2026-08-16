import enum
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProjectStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    # Terminal state for the current phase: media + transcript are ready, and the
    # analysis/generation stages are not implemented yet.
    TRANSCRIBED = "transcribed"
    ANALYZING = "analyzing"
    # Terminal state for the current phase: Content DNA is ready, but moment
    # detection and platform generation are not implemented yet.
    ANALYZED = "analyzed"
    DETECTING_MOMENTS = "detecting_moments"
    # Terminal state for the current phase: best moments are ready, but clip
    # rendering and platform content are not implemented yet.
    MOMENTS_READY = "moments_ready"
    GENERATING = "generating"
    # Terminal success state: the full campaign package is ready.
    COMPLETED = "completed"
    FAILED = "failed"


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String, default="Untitled Project")
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    video_path: Mapped[str | None] = mapped_column(String, nullable=True)
    video_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    video_width: Mapped[int | None] = mapped_column(nullable=True)
    video_height: Mapped[int | None] = mapped_column(nullable=True)
    video_fps: Mapped[float | None] = mapped_column(nullable=True)
    video_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # Pipeline outputs, stored as JSON text and parsed by the API layer.
    transcript_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_dna_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_topics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_moments_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    clips_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_concepts_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_score: Mapped[float | None] = mapped_column(nullable=True)
    campaign_evaluation_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def _json_len(self, raw: str | None) -> int:
        if not raw:
            return 0
        try:
            data = json.loads(raw)
        except ValueError:
            return 0
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return sum(1 for v in data.values() if v)
        return 0

    @property
    def clip_count(self) -> int:
        return self._json_len(self.clips_json)

    @property
    def post_count(self) -> int:
        """Platforms that actually produced content."""
        return self._json_len(self.platform_content_json)

    @property
    def moment_count(self) -> int:
        return self._json_len(self.best_moments_json)

    @property
    def has_content_dna(self) -> bool:
        return bool(self.content_dna_json)

    @property
    def video_url(self) -> str | None:
        if not self.video_path:
            return None
        return f"/media/uploads/{Path(self.video_path).name}"
