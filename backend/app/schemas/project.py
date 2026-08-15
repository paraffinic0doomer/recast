from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.project import ProjectStatus
from app.schemas.campaign import Campaign
from app.schemas.content_dna import ContentDNA
from app.schemas.evaluation import CampaignEvaluation
from app.schemas.thumbnail import ThumbnailConcept


class ProjectCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class TranscriptSegmentSchema(BaseModel):
    start: float
    end: float
    text: str


class TranscriptResponse(BaseModel):
    """Transcript payload returned by GET /api/projects/{id}/transcript."""

    project_id: str
    text: str
    language: str | None = None
    duration: float | None = None
    segments: list[TranscriptSegmentSchema] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: ProjectStatus
    error_message: str | None = None
    video_filename: str | None = None
    video_url: str | None = None
    duration_seconds: float | None = None
    video_width: int | None = None
    video_height: int | None = None
    video_fps: float | None = None
    video_size_bytes: int | None = None
    campaign_score: float | None = None
    # Lightweight counts so the dashboard can summarise without fetching details.
    clip_count: int = 0
    post_count: int = 0
    moment_count: int = 0
    has_content_dna: bool = False
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectSummary):
    transcript: dict | list | None = None
    content_dna: ContentDNA | None = None
    key_topics: dict | list | None = None
    best_moments: dict | list | None = None
    clips: dict | list | None = None
    platform_content: Campaign | None = None
    thumbnail_concepts: list[ThumbnailConcept] | None = None
    campaign_evaluation: CampaignEvaluation | None = None
