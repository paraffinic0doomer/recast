"""Content DNA — the structured understanding of a piece of content.

This is the single source of truth for every downstream generation step
(YouTube/Instagram/TikTok/LinkedIn/X copy, thumbnails, clip selection).
Platform generators must consume ContentDNA + transcript rather than
re-deriving their own understanding of the video.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _clean_list(values: list[str] | None, limit: int) -> list[str]:
    if not values:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = (value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


class KeyMoment(BaseModel):
    """An important moment or idea, anchored to the transcript where possible."""

    model_config = ConfigDict(populate_by_name=True)

    timestamp: float | None = Field(
        default=None, description="Start time in seconds, if it maps to the transcript"
    )
    title: str = Field(description="Short label for the moment")
    description: str = Field(default="", description="Why this moment matters")

    @field_validator("timestamp")
    @classmethod
    def _non_negative(cls, v: float | None) -> float | None:
        if v is None:
            return None
        return max(0.0, float(v))


class ContentDNA(BaseModel):
    """Structured semantic understanding of the source video."""

    primary_topic: str = ""
    secondary_topics: list[str] = Field(default_factory=list)
    audience: str = ""
    tone: str = ""
    content_type: str = ""
    core_message: str = ""

    key_points: list[str] = Field(
        default_factory=list, description="Important claims made in the content"
    )
    important_concepts: list[str] = Field(default_factory=list)
    entities: list[str] = Field(
        default_factory=list, description="People, products, brands, places mentioned"
    )
    keywords: list[str] = Field(default_factory=list)
    hooks: list[str] = Field(
        default_factory=list, description="Attention-grabbing openers usable on social"
    )
    cta: str | None = Field(default=None, description="Call to action, if present")
    key_moments: list[KeyMoment] = Field(default_factory=list)

    @field_validator(
        "primary_topic", "audience", "tone", "content_type", "core_message", mode="before"
    )
    @classmethod
    def _stringify(cls, v: object) -> str:
        if v is None:
            return ""
        if isinstance(v, list):
            return ", ".join(str(item).strip() for item in v if str(item).strip())
        return str(v).strip()

    @field_validator("cta", mode="before")
    @classmethod
    def _clean_cta(cls, v: object) -> str | None:
        if v is None:
            return None
        text = str(v).strip()
        if not text or text.lower() in {"none", "n/a", "null", "no cta", "not present"}:
            return None
        return text

    @field_validator("secondary_topics", "key_points", "important_concepts", mode="before")
    @classmethod
    def _limit_medium(cls, v: list[str] | None) -> list[str]:
        return _clean_list(v, limit=12)

    @field_validator("entities", "keywords", "hooks", mode="before")
    @classmethod
    def _limit_long(cls, v: list[str] | None) -> list[str]:
        return _clean_list(v, limit=20)

    @model_validator(mode="after")
    def _dedupe_key_moments(self) -> "ContentDNA":
        """Keep one moment per timestamp, in chronological order.

        Models padding toward the requested 5-10 moments tend to emit several
        entries pointing at the same timestamp. Downstream clip generation would
        turn those into duplicate clips, so collapse them here.
        """
        seen_times: set[float] = set()
        seen_titles: set[str] = set()
        unique: list[KeyMoment] = []

        for moment in self.key_moments:
            title_key = moment.title.strip().lower()
            if title_key and title_key in seen_titles:
                continue
            if moment.timestamp is not None:
                if moment.timestamp in seen_times:
                    continue
                seen_times.add(moment.timestamp)
            if title_key:
                seen_titles.add(title_key)
            unique.append(moment)

        unique.sort(
            key=lambda m: (m.timestamp is None, m.timestamp if m.timestamp is not None else 0.0)
        )
        self.key_moments = unique[:10]
        return self


class ContentDNAResponse(BaseModel):
    """Payload returned by GET /api/projects/{id}/content-dna."""

    project_id: str
    content_dna: ContentDNA
