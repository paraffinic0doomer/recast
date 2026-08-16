"""Per-platform campaign generation.

Each platform gets its own spec and its own LLM call. That is deliberate: a
single "write six captions" prompt produces one voice reworded six times. Here
the model is told, separately, what a good post looks like *on that platform* --
different length, tone, structure, hook strategy and CTA strategy -- and the
output is validated against that platform's real limits.

Everything stays anchored to Content DNA, which remains the source of truth.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Type

from pydantic import BaseModel, ValidationError

from app.schemas.campaign import (
    Campaign,
    Chapter,
    FacebookContent,
    InstagramContent,
    LinkedInContent,
    TikTokContent,
    XContent,
    YouTubeContent,
)
from app.schemas.content_dna import ContentDNA
from app.schemas.moment import BestMoment
from app.services.analysis_service import AnalysisError, get_analysis_service

logger = logging.getLogger(__name__)

MIN_CHAPTERS = 3
MIN_CHAPTER_GAP = 10.0


@dataclass
class PlatformSpec:
    key: str
    label: str
    model: Type[BaseModel]
    # What makes a post work *here* -- the differentiator.
    audience_mindset: str
    tone: str
    length: str
    structure: str
    hook_strategy: str
    cta_strategy: str
    json_shape: str
    extra_rules: list[str] = field(default_factory=list)


PLATFORM_SPECS: dict[str, PlatformSpec] = {
    "youtube": PlatformSpec(
        key="youtube",
        label="YouTube",
        model=YouTubeContent,
        audience_mindset="Viewers searching for a topic, deciding from a title and thumbnail whether to commit several minutes.",
        tone="Clear and informative. Confident, not clickbait. Written for search as well as humans.",
        length="Titles under 60 characters where possible (hard limit 100). Description 150-300 words.",
        structure="Description opens with a 1-2 sentence summary that works as a search snippet, then a short paragraph of detail, then a list of what the viewer learns.",
        hook_strategy="Front-load the specific outcome or number in the title. Keywords near the start.",
        cta_strategy="Soft, end of description: subscribe or watch next. Never mid-sentence.",
        json_shape='{"titles": ["...", "...", "..."], "description": "...", "seo_keywords": ["..."], "tags": ["..."]}',
        extra_rules=[
            "Provide exactly 3 distinct title options that take different angles (outcome, question, mistake).",
            "seo_keywords are search phrases; tags are single words or short phrases.",
            "Do NOT include chapter timestamps in the description; they are added separately.",
        ],
    ),
    "instagram": PlatformSpec(
        key="instagram",
        label="Instagram",
        model=InstagramContent,
        audience_mindset="Scrolling a feed, will read the first line only unless it earns the tap on 'more'.",
        tone="Warm, personal, first-person. Conversational but polished.",
        length="Caption 80-150 words, broken into short lines with blank lines between them.",
        structure="Punchy first line, line break, 2-3 short paragraphs, then the CTA on its own line. Hashtags separate from the caption.",
        hook_strategy="First line must stand alone as a scroll-stopper, because everything after it is truncated.",
        cta_strategy="Engagement-seeking: invite a comment, save or share.",
        json_shape='{"caption": "...", "hashtags": ["..."], "cta": "...", "reel_cover_text": "..."}',
        extra_rules=[
            "reel_cover_text is 3-6 words shown ON the video cover. Make it bold and readable, not a sentence.",
            "Provide 10-20 hashtags mixing broad and niche.",
            "Do not put hashtags inside the caption field.",
        ],
    ),
    "tiktok": PlatformSpec(
        key="tiktok",
        label="TikTok",
        model=TikTokContent,
        audience_mindset="Sound-on, full-screen, will swipe away within 2 seconds if nothing lands.",
        tone="Casual, fast, direct. Lowercase-friendly. No corporate phrasing.",
        length="Caption under 150 characters. Hook is one spoken sentence.",
        structure="Hook is the spoken opening line of the video. Caption is a short teaser, not a summary.",
        hook_strategy="Pattern interrupt or bold claim in the first 2 seconds. Curiosity gap over explanation.",
        cta_strategy="Native and low-friction: follow for part 2, comment a word, watch to the end.",
        json_shape='{"hook": "...", "caption": "...", "hashtags": ["..."], "cta": "..."}',
        extra_rules=[
            "The hook must be sayable out loud in under 3 seconds.",
            "Use 3-6 hashtags only. Avoid #fyp-style filler unless genuinely relevant.",
            "Never write a caption that just restates the video.",
        ],
    ),
    "facebook": PlatformSpec(
        key="facebook",
        label="Facebook",
        model=FacebookContent,
        audience_mindset="Mixed audience including people who do not know the creator. Often older, reads more text than Instagram.",
        tone="Plain-spoken and friendly. Explains context rather than assuming it.",
        length="Caption 60-120 words in 2-3 short paragraphs.",
        structure="Context sentence first (who this is for), then the insight, then the CTA.",
        hook_strategy="Relatable problem statement rather than a curiosity gap. Assume no prior context.",
        cta_strategy="Conversational: ask a direct question that is easy to answer in the comments.",
        json_shape='{"caption": "...", "cta": "...", "hashtags": ["..."]}',
        extra_rules=[
            "Use at most 3 hashtags; Facebook readers ignore hashtag walls.",
            "Do not use TikTok/Instagram slang here.",
        ],
    ),
    "linkedin": PlatformSpec(
        key="linkedin",
        label="LinkedIn",
        model=LinkedInContent,
        audience_mindset="Professionals evaluating whether this is credible and useful to their work.",
        tone="Professional and insight-led, but human. No hype, no emoji spam.",
        length="Post 150-250 words with short single-line paragraphs.",
        structure="One-line observation, blank line, the problem, the insight, a concrete takeaway list, then the CTA.",
        hook_strategy="Lead with a counter-intuitive observation or a number. The first two lines show before 'see more'.",
        cta_strategy="Discussion-oriented and peer-to-peer: invite professional experience or disagreement.",
        json_shape='{"post": "...", "cta": "...", "hashtags": ["..."]}',
        extra_rules=[
            "Frame the value in terms of time saved, output quality or process.",
            "Use 3-5 professional hashtags. No slang tags.",
        ],
    ),
    "x": PlatformSpec(
        key="x",
        label="X",
        model=XContent,
        audience_mindset="Fast timeline, rewards density and opinion. Threads are read only if the first post earns it.",
        tone="Terse and declarative. Every word carries weight.",
        length="Main post MUST be under 280 characters. Each thread item under 280.",
        structure="Standalone claim in the main post. Optional thread of 3-5 posts, each one idea, building to a payoff.",
        hook_strategy="A strong claim or specific number stated flatly. No throat-clearing, no 'in this video'.",
        cta_strategy="Minimal. Often none, or a single closing line in the last thread post.",
        json_shape='{"post": "...", "thread": ["...", "...", "..."]}',
        extra_rules=[
            "The main post must be under 280 characters. Count them.",
            "Omit the thread (empty array) unless the content genuinely needs several beats.",
            "No hashtags unless one is genuinely meaningful.",
        ],
    ),
}


SYSTEM_PROMPT = (
    "You are a social media strategist who writes natively for each platform. "
    "You never reuse the same copy across platforms: a LinkedIn post and a TikTok "
    "caption should not sound like the same sentence reworded. Stay strictly "
    "faithful to the supplied content; never invent facts, statistics, products "
    "or claims that are not in the source. Respond with JSON only."
)


def _dna_block(dna: ContentDNA) -> str:
    lines = [
        f"- Primary topic: {dna.primary_topic}",
        f"- Secondary topics: {', '.join(dna.secondary_topics) or 'n/a'}",
        f"- Audience: {dna.audience}",
        f"- Tone of source: {dna.tone}",
        f"- Content type: {dna.content_type}",
        f"- Core message: {dna.core_message}",
    ]
    if dna.key_points:
        lines.append("- Key points: " + " | ".join(dna.key_points))
    if dna.important_concepts:
        lines.append("- Concepts: " + ", ".join(dna.important_concepts))
    if dna.entities:
        lines.append("- Entities: " + ", ".join(dna.entities))
    if dna.keywords:
        lines.append("- Keywords: " + ", ".join(dna.keywords))
    if dna.hooks:
        lines.append("- Source hooks: " + " | ".join(dna.hooks))
    if dna.cta:
        lines.append(f"- Original CTA: {dna.cta}")
    return "\n".join(lines)


def _moments_block(moments: list[BestMoment]) -> str:
    if not moments:
        return ""
    lines = [
        f"- [{m.start:.0f}s-{m.end:.0f}s] {m.title} (score {m.score}) hook: \"{m.hook}\""
        for m in moments
    ]
    return "\nSELECTED CLIPS (already cut as shorts):\n" + "\n".join(lines)


def build_platform_prompt(
    spec: PlatformSpec,
    dna: ContentDNA,
    moments: list[BestMoment],
    transcript_excerpt: str = "",
) -> str:
    rules = "\n".join(f"- {r}" for r in spec.extra_rules)
    excerpt = ""
    if transcript_excerpt:
        excerpt = f"\nTRANSCRIPT EXCERPT (for voice and specifics):\n{transcript_excerpt[:2500]}\n"

    return (
        f"Write the {spec.label} content for this campaign.\n\n"
        f"PLATFORM BRIEF - {spec.label}\n"
        f"- Reader mindset: {spec.audience_mindset}\n"
        f"- Tone: {spec.tone}\n"
        f"- Length: {spec.length}\n"
        f"- Structure: {spec.structure}\n"
        f"- Hook strategy: {spec.hook_strategy}\n"
        f"- CTA strategy: {spec.cta_strategy}\n\n"
        f"CONTENT DNA (the single source of truth):\n{_dna_block(dna)}\n"
        f"{_moments_block(moments)}\n"
        f"{excerpt}\n"
        f"Return JSON of exactly this shape:\n{spec.json_shape}\n\n"
        f"Rules:\n{rules}\n"
        f"- Write natively for {spec.label}. Do not produce text that would read "
        f"identically on another platform.\n"
        f"- Stay faithful to the Content DNA above. Invent nothing.\n"
    )


def build_chapters(moments: list[BestMoment], dna: ContentDNA) -> list[Chapter]:
    """Build YouTube chapters from real timestamps only.

    Prefers Content DNA key moments (already validated against video duration),
    falling back to detected best moments. Returns [] when YouTube's rules
    cannot be met, rather than emitting chapters YouTube will silently ignore.
    """
    points: list[tuple[float, str]] = []
    for moment in dna.key_moments:
        if moment.timestamp is not None and moment.title:
            points.append((float(moment.timestamp), moment.title))
    if not points:
        points = [(m.start, m.title) for m in moments if m.title]

    if not points:
        return []

    points.sort(key=lambda p: p[0])

    chapters: list[Chapter] = []
    # YouTube requires the first chapter to be at 0:00.
    if points[0][0] > 0:
        chapters.append(Chapter(timestamp=0.0, label="Intro"))
    for timestamp, label in points:
        if chapters and timestamp - chapters[-1].timestamp < MIN_CHAPTER_GAP:
            continue
        chapters.append(Chapter(timestamp=timestamp, label=label))

    if len(chapters) < MIN_CHAPTERS:
        logger.info("Not enough spaced timestamps for YouTube chapters; omitting")
        return []
    return chapters


def generate_platform(
    platform: str,
    dna: ContentDNA,
    moments: list[BestMoment],
    transcript_excerpt: str = "",
    service=None,
) -> BaseModel:
    """Generate content for a single platform."""
    spec = PLATFORM_SPECS.get(platform)
    if spec is None:
        raise AnalysisError(
            f"Unknown platform '{platform}'. Supported: {', '.join(PLATFORM_SPECS)}"
        )

    service = service or get_analysis_service()
    prompt = build_platform_prompt(spec, dna, moments, transcript_excerpt)

    logger.info("Generating %s content", spec.label)
    payload = service.complete_json(prompt, SYSTEM_PROMPT)
    if not isinstance(payload, dict):
        raise AnalysisError(f"{spec.label}: model did not return a JSON object")

    try:
        content = spec.model.model_validate(payload)
    except ValidationError as exc:
        raise AnalysisError(f"{spec.label} output failed validation: {exc}") from exc

    if platform == "youtube":
        # Chapters come from real timestamps, never from the model.
        content.chapters = build_chapters(moments, dna)

    return content


def generate_campaign(
    dna: ContentDNA,
    moments: list[BestMoment],
    transcript_excerpt: str = "",
    platforms: list[str] | None = None,
    service=None,
    existing: Campaign | None = None,
) -> tuple[Campaign, list[str]]:
    """Generate content for each platform. Returns (campaign, failed_platforms).

    A platform that fails does not abort the rest -- partial campaigns are more
    useful than none, and the caller reports which platforms need a retry.
    """
    service = service or get_analysis_service()
    targets = platforms or list(PLATFORM_SPECS)
    campaign = existing.model_copy(deep=True) if existing else Campaign()
    failed: list[str] = []

    for platform in targets:
        try:
            setattr(
                campaign,
                platform,
                generate_platform(platform, dna, moments, transcript_excerpt, service),
            )
        except AnalysisError as exc:
            logger.warning("Campaign generation failed for %s: %s", platform, exc)
            failed.append(platform)

    return campaign, failed


def score_campaign(campaign: Campaign, dna: ContentDNA, moments: list[BestMoment]) -> float:
    """A transparent 0-100 readiness score. Deterministic, not model-generated."""
    score = 0.0

    # Coverage: how many platforms actually produced content (50 points).
    generated = campaign.generated_platforms
    score += (len(generated) / len(PLATFORM_SPECS)) * 50

    # Source richness (25 points).
    if dna.core_message:
        score += 5
    if len(dna.key_points) >= 2:
        score += 5
    if dna.hooks:
        score += 5
    if len(dna.keywords) >= 3:
        score += 5
    if dna.cta:
        score += 5

    # Clip-worthy moments (15 points).
    score += min(len(moments), 3) / 3 * 15

    # Completeness of the highest-effort assets (10 points).
    if campaign.youtube and len(campaign.youtube.titles) >= 3:
        score += 4
    if campaign.youtube and campaign.youtube.chapters:
        score += 3
    if campaign.x and campaign.x.thread:
        score += 3

    return round(min(100.0, score), 1)
