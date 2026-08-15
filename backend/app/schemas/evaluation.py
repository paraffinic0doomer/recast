"""Campaign evaluation schemas.

Distinct from the deterministic `campaign_score` in platform_service, which
measures *completeness* (how many platforms produced content, how rich the
Content DNA was). This is a quality judgement of the copy itself.
"""

from pydantic import BaseModel, Field, field_validator, model_validator

DIMENSIONS = [
    "content_quality",
    "platform_adaptation",
    "hook_strength",
    "source_consistency",
    "seo",
    "cta",
]

DIMENSION_LABELS = {
    "content_quality": "Content quality",
    "platform_adaptation": "Platform adaptation",
    "hook_strength": "Hook strength",
    "source_consistency": "Source consistency",
    "seo": "SEO quality",
    "cta": "CTA quality",
}

PRIORITIES = {"high", "medium", "low"}


def _clamp(value: object) -> int:
    try:
        return int(max(0, min(100, round(float(value)))))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


class Improvement(BaseModel):
    """One actionable recommendation."""

    area: str = ""
    suggestion: str = ""
    priority: str = "medium"

    @field_validator("area", "suggestion", mode="before")
    @classmethod
    def _text(cls, v: object) -> str:
        return "" if v is None else str(v).strip()

    @field_validator("priority", mode="before")
    @classmethod
    def _priority(cls, v: object) -> str:
        text = str(v or "medium").strip().lower()
        return text if text in PRIORITIES else "medium"


class CampaignEvaluation(BaseModel):
    overall: int = 0
    content_quality: int = 0
    platform_adaptation: int = 0
    hook_strength: int = 0
    source_consistency: int = 0
    seo: int = 0
    cta: int = 0
    summary: str = ""
    improvements: list[Improvement] = Field(default_factory=list)

    @field_validator(*DIMENSIONS, "overall", mode="before")
    @classmethod
    def _scores(cls, v: object) -> int:
        return _clamp(v)

    @field_validator("summary", mode="before")
    @classmethod
    def _summary(cls, v: object) -> str:
        return "" if v is None else str(v).strip()

    @field_validator("improvements", mode="before")
    @classmethod
    def _improvements(cls, v: object) -> list:
        """Accept plain strings as well as objects -- models mix both."""
        if not v:
            return []
        if isinstance(v, str):
            v = [v]
        out = []
        for item in v:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    out.append({"area": "General", "suggestion": text})
            elif isinstance(item, dict):
                out.append(item)
        return out

    @model_validator(mode="after")
    def _finalise(self) -> "CampaignEvaluation":
        # Overall is always derived: models routinely state an overall that
        # contradicts their own dimension scores.
        scores = [getattr(self, d) for d in DIMENSIONS]
        if any(scores):
            self.overall = int(round(sum(scores) / len(scores)))

        # Drop empty suggestions, then keep the most useful few.
        useful = [i for i in self.improvements if i.suggestion]
        order = {"high": 0, "medium": 1, "low": 2}
        useful.sort(key=lambda i: order.get(i.priority, 1))
        self.improvements = useful[:5]
        return self

    @property
    def weakest_dimension(self) -> str:
        return min(DIMENSIONS, key=lambda d: getattr(self, d))


class EvaluationResponse(BaseModel):
    project_id: str
    evaluation: CampaignEvaluation | None = None
    # Completeness score from platform_service; kept so the UI can show both.
    completeness_score: float | None = None
