"""Platform-specific campaign schemas.

Every platform has its own model with its own real-world limits. Content is
generated per platform (separate prompt, separate call) so the results genuinely
differ in length, tone, structure, hook and CTA -- not one caption reworded six
times.
"""

from pydantic import BaseModel, Field, field_validator, model_validator

# Real platform limits.
YOUTUBE_TITLE_MAX = 100
YOUTUBE_DESCRIPTION_MAX = 5000
INSTAGRAM_CAPTION_MAX = 2200
TIKTOK_CAPTION_MAX = 2200
FACEBOOK_CAPTION_MAX = 63_206
LINKEDIN_POST_MAX = 3000
X_POST_MAX = 280

PLATFORM_NAMES = ["youtube", "instagram", "tiktok", "facebook", "linkedin", "x"]


def _clean_text(value: object, limit: int | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        text = "\n\n".join(str(v).strip() for v in value if str(v).strip())
    else:
        text = str(value).strip()
    if limit is not None and len(text) > limit:
        text = text[:limit].rstrip()
    return text


def _clean_hashtags(values: object, limit: int) -> list[str]:
    """Normalise to '#tag' form, de-duplicated, capped."""
    if not values:
        return []
    if isinstance(values, str):
        values = values.replace(",", " ").split()

    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        tag = str(raw).strip().lstrip("#").strip()
        tag = "".join(ch for ch in tag if ch.isalnum() or ch == "_")
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(f"#{tag}")
        if len(out) >= limit:
            break
    return out


def _clean_list(values: object, limit: int) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [v.strip() for v in values.split(",")]
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        text = str(raw).strip()
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


class Chapter(BaseModel):
    """A YouTube chapter. Timestamps come from the transcript, never the model."""

    timestamp: float
    label: str

    @property
    def formatted(self) -> str:
        total = int(self.timestamp)
        h, m, s = total // 3600, (total % 3600) // 60, total % 60
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class YouTubeContent(BaseModel):
    titles: list[str] = Field(default_factory=list, description="3 title options")
    description: str = ""
    chapters: list[Chapter] = Field(default_factory=list)
    seo_keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("titles", mode="before")
    @classmethod
    def _titles(cls, v: object) -> list[str]:
        return [t[:YOUTUBE_TITLE_MAX] for t in _clean_list(v, 3)]

    @field_validator("description", mode="before")
    @classmethod
    def _description(cls, v: object) -> str:
        return _clean_text(v, YOUTUBE_DESCRIPTION_MAX)

    @field_validator("seo_keywords", "tags", mode="before")
    @classmethod
    def _keywords(cls, v: object) -> list[str]:
        return _clean_list(v, 15)

    @model_validator(mode="after")
    def _validate_chapters(self) -> "YouTubeContent":
        """YouTube only renders chapters if they start at 0:00, number 3+, and
        are at least 10s apart. Anything less is dropped rather than shipped broken."""
        chapters = sorted(self.chapters, key=lambda c: c.timestamp)
        valid: list[Chapter] = []
        for chapter in chapters:
            if not chapter.label.strip():
                continue
            if valid and chapter.timestamp - valid[-1].timestamp < 10:
                continue
            valid.append(chapter)

        if len(valid) < 3 or (valid and valid[0].timestamp != 0):
            self.chapters = []
        else:
            self.chapters = valid
        return self


class InstagramContent(BaseModel):
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    cta: str = ""
    reel_cover_text: str = ""

    @field_validator("caption", mode="before")
    @classmethod
    def _caption(cls, v: object) -> str:
        return _clean_text(v, INSTAGRAM_CAPTION_MAX)

    @field_validator("cta", mode="before")
    @classmethod
    def _cta(cls, v: object) -> str:
        return _clean_text(v, 200)

    @field_validator("reel_cover_text", mode="before")
    @classmethod
    def _cover(cls, v: object) -> str:
        # Cover text sits on the video; long strings become unreadable.
        return _clean_text(v, 60)

    @field_validator("hashtags", mode="before")
    @classmethod
    def _hashtags(cls, v: object) -> list[str]:
        return _clean_hashtags(v, 30)


class TikTokContent(BaseModel):
    hook: str = ""
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    cta: str = ""

    @field_validator("hook", mode="before")
    @classmethod
    def _hook(cls, v: object) -> str:
        return _clean_text(v, 150)

    @field_validator("caption", mode="before")
    @classmethod
    def _caption(cls, v: object) -> str:
        return _clean_text(v, TIKTOK_CAPTION_MAX)

    @field_validator("cta", mode="before")
    @classmethod
    def _cta(cls, v: object) -> str:
        return _clean_text(v, 150)

    @field_validator("hashtags", mode="before")
    @classmethod
    def _hashtags(cls, v: object) -> list[str]:
        return _clean_hashtags(v, 8)


class FacebookContent(BaseModel):
    caption: str = ""
    cta: str = ""
    hashtags: list[str] = Field(default_factory=list)

    @field_validator("caption", mode="before")
    @classmethod
    def _caption(cls, v: object) -> str:
        return _clean_text(v, FACEBOOK_CAPTION_MAX)

    @field_validator("cta", mode="before")
    @classmethod
    def _cta(cls, v: object) -> str:
        return _clean_text(v, 200)

    @field_validator("hashtags", mode="before")
    @classmethod
    def _hashtags(cls, v: object) -> list[str]:
        return _clean_hashtags(v, 5)


class LinkedInContent(BaseModel):
    post: str = ""
    cta: str = ""
    hashtags: list[str] = Field(default_factory=list)

    @field_validator("post", mode="before")
    @classmethod
    def _post(cls, v: object) -> str:
        return _clean_text(v, LINKEDIN_POST_MAX)

    @field_validator("cta", mode="before")
    @classmethod
    def _cta(cls, v: object) -> str:
        return _clean_text(v, 250)

    @field_validator("hashtags", mode="before")
    @classmethod
    def _hashtags(cls, v: object) -> list[str]:
        return _clean_hashtags(v, 5)


class XContent(BaseModel):
    post: str = ""
    thread: list[str] = Field(default_factory=list)

    @field_validator("post", mode="before")
    @classmethod
    def _post(cls, v: object) -> str:
        return _clean_text(v, X_POST_MAX)

    @field_validator("thread", mode="before")
    @classmethod
    def _thread(cls, v: object) -> list[str]:
        # Every tweet in a thread must independently fit the limit.
        return [t[:X_POST_MAX] for t in _clean_list(v, 8)]


class Campaign(BaseModel):
    youtube: YouTubeContent | None = None
    instagram: InstagramContent | None = None
    tiktok: TikTokContent | None = None
    facebook: FacebookContent | None = None
    linkedin: LinkedInContent | None = None
    x: XContent | None = None

    @property
    def generated_platforms(self) -> list[str]:
        return [p for p in PLATFORM_NAMES if getattr(self, p) is not None]


class CampaignResponse(BaseModel):
    project_id: str
    campaign: Campaign
    campaign_score: float | None = None
