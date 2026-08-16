"""Thumbnail concept schemas.

No image-generation API is configured (Groq offers none and no OpenAI key is
set), so RECAST produces render-ready specifications instead. The preview is not
a mockup: a real frame is extracted from the source video at the concept's
timestamp, and the frontend composes the headline over it per the spec.
"""

from pydantic import BaseModel, Field, field_validator

HEADLINE_MAX = 40  # Longer than this is unreadable at YouTube grid size.

TEXT_POSITIONS = {"left", "right", "center", "top", "bottom"}
SUBJECT_PLACEMENTS = {"left", "right", "center", "full"}


class ThumbnailConcept(BaseModel):
    id: str = ""
    headline: str = ""
    visual_concept: str = ""
    subject_placement: str = "center"
    emotional_angle: str = ""
    why_it_works: str = ""
    recommended_use_case: str = ""

    # Render hints for the frontend composer.
    text_position: str = "left"
    accent_color: str = "#FACC15"
    timestamp: float | None = None
    frame_url: str | None = None

    @field_validator("headline", mode="before")
    @classmethod
    def _headline(cls, v: object) -> str:
        text = "" if v is None else str(v).strip().strip('"')
        return text[:HEADLINE_MAX]

    @field_validator(
        "visual_concept",
        "emotional_angle",
        "why_it_works",
        "recommended_use_case",
        mode="before",
    )
    @classmethod
    def _text(cls, v: object) -> str:
        return "" if v is None else str(v).strip()

    @field_validator("subject_placement", mode="before")
    @classmethod
    def _placement(cls, v: object) -> str:
        text = str(v or "center").strip().lower()
        return text if text in SUBJECT_PLACEMENTS else "center"

    @field_validator("text_position", mode="before")
    @classmethod
    def _text_position(cls, v: object) -> str:
        text = str(v or "left").strip().lower()
        return text if text in TEXT_POSITIONS else "left"

    @field_validator("accent_color", mode="before")
    @classmethod
    def _accent(cls, v: object) -> str:
        text = str(v or "").strip()
        if text.startswith("#") and len(text) in (4, 7):
            try:
                int(text[1:], 16)
                return text.upper()
            except ValueError:
                pass
        return "#FACC15"

    @field_validator("timestamp")
    @classmethod
    def _timestamp(cls, v: float | None) -> float | None:
        return None if v is None else max(0.0, float(v))


class ThumbnailsResponse(BaseModel):
    project_id: str
    concepts: list[ThumbnailConcept] = Field(default_factory=list)
    image_generation_available: bool = False
