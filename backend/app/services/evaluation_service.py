"""AI campaign evaluation.

Judges the *quality* of generated campaign copy across six dimensions and
returns actionable recommendations.

This is strictly an add-on: evaluation failure must never lose a generated
campaign, so callers are expected to treat EvaluationError as non-fatal.
"""

import json
import logging

from pydantic import ValidationError

from app.schemas.campaign import Campaign
from app.schemas.content_dna import ContentDNA
from app.schemas.evaluation import CampaignEvaluation
from app.services.analysis_service import AnalysisError, get_analysis_service

logger = logging.getLogger(__name__)

MAX_CAMPAIGN_CHARS = 9000


class EvaluationError(AnalysisError):
    """Raised when campaign evaluation fails."""


SYSTEM_PROMPT = (
    "You are a critical social media strategist reviewing a generated campaign. "
    "You are hard to impress: an average campaign scores in the 60s, a strong one "
    "in the 80s, and only genuinely excellent work exceeds 90. Judge what is "
    "actually written, not what was intended. Every recommendation must be "
    "specific and actionable. Respond with JSON only."
)


def _summarise_campaign(campaign: Campaign) -> str:
    """Compact, readable rendering of the campaign for the evaluator."""
    parts: list[str] = []

    if campaign.youtube:
        yt = campaign.youtube
        parts.append(
            "YOUTUBE\n"
            f"  titles: {' | '.join(yt.titles)}\n"
            f"  description: {yt.description}\n"
            f"  chapters: {len(yt.chapters)}\n"
            f"  seo_keywords: {', '.join(yt.seo_keywords)}\n"
            f"  tags: {', '.join(yt.tags)}"
        )
    if campaign.instagram:
        ig = campaign.instagram
        parts.append(
            "INSTAGRAM\n"
            f"  cover: {ig.reel_cover_text}\n"
            f"  caption: {ig.caption}\n"
            f"  cta: {ig.cta}\n"
            f"  hashtags: {' '.join(ig.hashtags)}"
        )
    if campaign.tiktok:
        tt = campaign.tiktok
        parts.append(
            "TIKTOK\n"
            f"  hook: {tt.hook}\n"
            f"  caption: {tt.caption}\n"
            f"  cta: {tt.cta}\n"
            f"  hashtags: {' '.join(tt.hashtags)}"
        )
    if campaign.facebook:
        fb = campaign.facebook
        parts.append(f"FACEBOOK\n  caption: {fb.caption}\n  cta: {fb.cta}")
    if campaign.linkedin:
        li = campaign.linkedin
        parts.append(f"LINKEDIN\n  post: {li.post}\n  cta: {li.cta}")
    if campaign.x:
        parts.append(
            "X\n"
            f"  post: {campaign.x.post}\n"
            f"  thread: {len(campaign.x.thread)} posts"
        )

    text = "\n\n".join(parts)
    if len(text) > MAX_CAMPAIGN_CHARS:
        text = text[:MAX_CAMPAIGN_CHARS] + "\n[truncated]"
    return text


def build_evaluation_prompt(campaign: Campaign, dna: ContentDNA) -> str:
    missing = [p for p in ["youtube", "instagram", "tiktok", "facebook", "linkedin", "x"]
               if getattr(campaign, p) is None]
    missing_note = (
        f"\nNOTE: no content was generated for: {', '.join(missing)}. "
        "Take that into account.\n" if missing else ""
    )

    return (
        "Evaluate this generated social media campaign.\n\n"
        f"SOURCE CONTENT DNA (the campaign must stay faithful to this):\n"
        f"- Primary topic: {dna.primary_topic}\n"
        f"- Audience: {dna.audience}\n"
        f"- Tone: {dna.tone}\n"
        f"- Core message: {dna.core_message}\n"
        f"- Key points: {' | '.join(dna.key_points) or 'n/a'}\n"
        f"- Keywords: {', '.join(dna.keywords) or 'n/a'}\n"
        f"- Original CTA: {dna.cta or 'none'}\n"
        f"{missing_note}\n"
        f"GENERATED CAMPAIGN:\n{_summarise_campaign(campaign)}\n\n"
        "Score each dimension 0-100:\n"
        "- content_quality: is the writing clear, specific and worth reading?\n"
        "- platform_adaptation: is each platform genuinely native, or the same "
        "copy reworded? Penalise heavily if posts are interchangeable.\n"
        "- hook_strength: would the opening lines actually stop a scroll?\n"
        "- source_consistency: does it stay true to the Content DNA, inventing "
        "nothing? Penalise any claim not supported by the source.\n"
        "- seo: are keywords, titles and tags genuinely useful for discovery?\n"
        "- cta: are the calls to action specific, varied and appropriate per platform?\n\n"
        'Return JSON: {"content_quality": 0-100, "platform_adaptation": 0-100, '
        '"hook_strength": 0-100, "source_consistency": 0-100, "seo": 0-100, '
        '"cta": 0-100, "summary": "one sentence verdict", '
        '"improvements": [{"area": "...", "suggestion": "...", '
        '"priority": "high|medium|low"}]}\n\n'
        "Rules:\n"
        "- Provide 3-5 improvements, each naming a concrete change "
        "(e.g. 'Rewrite the X post to lead with the 6-8 hour statistic'), not "
        "vague advice like 'improve engagement'.\n"
        "- Do not give every dimension the same score; differentiate honestly.\n"
        "- Do not output an 'overall' field; it is computed from your scores.\n"
    )


def evaluate_campaign(
    campaign: Campaign,
    dna: ContentDNA,
    service=None,
) -> CampaignEvaluation:
    """Score campaign quality and return actionable improvements."""
    if not campaign.generated_platforms:
        raise EvaluationError("No campaign content to evaluate.")

    service = service or get_analysis_service()

    try:
        payload = service.complete_json(
            build_evaluation_prompt(campaign, dna), SYSTEM_PROMPT
        )
    except AnalysisError as exc:
        raise EvaluationError(f"Evaluation request failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise EvaluationError("Evaluator did not return a JSON object")

    try:
        evaluation = CampaignEvaluation.model_validate(payload)
    except ValidationError as exc:
        raise EvaluationError(f"Evaluation output failed validation: {exc}") from exc

    if evaluation.overall == 0:
        raise EvaluationError("Evaluator returned no usable scores")

    logger.info(
        "Campaign evaluated: overall %d (weakest: %s), %d improvements",
        evaluation.overall,
        evaluation.weakest_dimension,
        len(evaluation.improvements),
    )
    return evaluation


def load_evaluation(raw: str | None) -> CampaignEvaluation | None:
    if not raw:
        return None
    try:
        return CampaignEvaluation.model_validate(json.loads(raw))
    except (ValueError, ValidationError):
        logger.warning("Stored evaluation could not be parsed; ignoring")
        return None
