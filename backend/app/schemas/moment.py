"""Best-moment schemas.

Timestamps here are always derived from real transcript segment boundaries --
never from model output. See services/moment_service.py for how candidate
windows are built and validated.
"""

from pydantic import BaseModel, Field, field_validator, model_validator


def _clamp_score(value: object) -> int:
    try:
        score = float(value)  # models sometimes return "88" or 88.4
    except (TypeError, ValueError):
        return 0
    return int(max(0, min(100, round(score))))


class MomentScores(BaseModel):
    hook_strength: int = 0
    information_value: int = 0
    standalone_quality: int = 0
    emotional_interest: int = 0

    @field_validator("*", mode="before")
    @classmethod
    def _coerce(cls, v: object) -> int:
        return _clamp_score(v)

    @property
    def average(self) -> int:
        values = [
            self.hook_strength,
            self.information_value,
            self.standalone_quality,
            self.emotional_interest,
        ]
        return int(round(sum(values) / len(values)))


class BestMoment(BaseModel):
    # Stable handle used by the clip endpoints; assigned at detection time.
    id: str = ""
    start: float
    end: float
    title: str = ""
    hook: str = ""
    reason: str = ""
    score: int = 0
    scores: MomentScores = Field(default_factory=MomentScores)

    @field_validator("score", mode="before")
    @classmethod
    def _coerce_score(cls, v: object) -> int:
        return _clamp_score(v)

    @field_validator("title", "hook", "reason", mode="before")
    @classmethod
    def _stringify(cls, v: object) -> str:
        return "" if v is None else str(v).strip()

    @model_validator(mode="after")
    def _fill_overall_score(self) -> "BestMoment":
        # Trust the component scores over a separately-stated overall score:
        # models frequently emit an overall that disagrees with its own breakdown.
        computed = self.scores.average
        if computed > 0:
            self.score = computed
        return self

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)


class BestMomentsResponse(BaseModel):
    project_id: str
    moments: list[BestMoment]


class ClipRequest(BaseModel):
    moment_id: str


class Clip(BaseModel):
    """A rendered short video generated from a detected moment."""

    clip_id: str
    moment_id: str
    video_url: str
    thumbnail_url: str
    title: str = ""
    hook: str = ""
    score: int = 0
    start: float
    end: float
    duration: float
    width: int
    height: int
    vertical: bool


class ClipsResponse(BaseModel):
    project_id: str
    clips: list[Clip]
