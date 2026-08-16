import pytest

from app.schemas.campaign import Campaign, TikTokContent, XContent, YouTubeContent
from app.schemas.content_dna import ContentDNA
from app.schemas.evaluation import DIMENSIONS, CampaignEvaluation
from app.services.evaluation_service import (
    EvaluationError,
    build_evaluation_prompt,
    evaluate_campaign,
    load_evaluation,
)

DNA = ContentDNA.model_validate(
    {
        "primary_topic": "Repurposing video content",
        "audience": "Content creators",
        "core_message": "One video can become a whole campaign.",
        "keywords": ["repurposing", "shorts"],
        "cta": "Subscribe",
    }
)

CAMPAIGN = Campaign(
    youtube=YouTubeContent.model_validate(
        {"titles": ["A", "B", "C"], "description": "desc", "seo_keywords": ["repurposing"]}
    ),
    tiktok=TikTokContent.model_validate({"hook": "hook", "caption": "cap", "cta": "follow"}),
    x=XContent.model_validate({"post": "One video. A whole campaign."}),
)

GOOD = {
    "content_quality": 84,
    "platform_adaptation": 91,
    "hook_strength": 72,
    "source_consistency": 95,
    "seo": 68,
    "cta": 77,
    "summary": "Strong adaptation, weaker SEO.",
    "improvements": [
        {"area": "SEO", "suggestion": "Add the 6-8 hour statistic to the YouTube title", "priority": "high"},
        {"area": "Hooks", "suggestion": "Lead the X post with the number", "priority": "medium"},
        {"area": "CTA", "suggestion": "Vary the Instagram CTA from the TikTok one", "priority": "low"},
    ],
}


class StubService:
    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else GOOD
        self.error = error
        self.prompts = []

    def complete_json(self, prompt, system=None):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.payload


# --- scoring -----------------------------------------------------------------


def test_overall_is_derived_from_dimensions():
    e = evaluate_campaign(CAMPAIGN, DNA, StubService())
    expected = round(sum(GOOD[d] for d in DIMENSIONS) / len(DIMENSIONS))
    assert e.overall == expected


def test_stated_overall_is_ignored():
    """Models routinely state an overall that contradicts their own scores."""
    payload = {**GOOD, "overall": 5}
    e = evaluate_campaign(CAMPAIGN, DNA, StubService(payload))
    assert e.overall > 50


def test_scores_clamped_and_coerced():
    payload = {**GOOD, "seo": 150, "cta": -20, "hook_strength": "83", "content_quality": None}
    e = evaluate_campaign(CAMPAIGN, DNA, StubService(payload))
    assert e.seo == 100
    assert e.cta == 0
    assert e.hook_strength == 83
    assert e.content_quality == 0


def test_weakest_dimension_identified():
    e = evaluate_campaign(CAMPAIGN, DNA, StubService())
    assert e.weakest_dimension == "seo"


# --- improvements ------------------------------------------------------------


def test_improvements_parsed_and_prioritised():
    e = evaluate_campaign(CAMPAIGN, DNA, StubService())
    assert len(e.improvements) == 3
    assert e.improvements[0].priority == "high"
    assert e.improvements[-1].priority == "low"


def test_plain_string_improvements_accepted():
    payload = {**GOOD, "improvements": ["Tighten the LinkedIn opener", "Add a number to the hook"]}
    e = evaluate_campaign(CAMPAIGN, DNA, StubService(payload))
    assert len(e.improvements) == 2
    assert e.improvements[0].suggestion == "Tighten the LinkedIn opener"
    assert e.improvements[0].area == "General"


def test_empty_improvements_dropped():
    payload = {**GOOD, "improvements": [{"area": "X", "suggestion": ""}, {"suggestion": "Real one"}]}
    e = evaluate_campaign(CAMPAIGN, DNA, StubService(payload))
    assert len(e.improvements) == 1


def test_improvements_capped():
    payload = {**GOOD, "improvements": [{"suggestion": f"fix {i}"} for i in range(12)]}
    e = evaluate_campaign(CAMPAIGN, DNA, StubService(payload))
    assert len(e.improvements) == 5


def test_invalid_priority_defaults_to_medium():
    payload = {**GOOD, "improvements": [{"suggestion": "s", "priority": "urgent"}]}
    e = evaluate_campaign(CAMPAIGN, DNA, StubService(payload))
    assert e.improvements[0].priority == "medium"


# --- prompt ------------------------------------------------------------------


def test_prompt_includes_campaign_and_source():
    prompt = build_evaluation_prompt(CAMPAIGN, DNA)
    assert "One video. A whole campaign." in prompt
    assert "One video can become a whole campaign." in prompt
    assert "Penalise heavily if posts are interchangeable" in prompt


def test_prompt_notes_missing_platforms():
    prompt = build_evaluation_prompt(CAMPAIGN, DNA)
    assert "no content was generated for" in prompt
    assert "linkedin" in prompt


# --- failure modes -----------------------------------------------------------


def test_empty_campaign_rejected():
    with pytest.raises(EvaluationError, match="No campaign content"):
        evaluate_campaign(Campaign(), DNA, StubService())


def test_upstream_failure_wrapped():
    from app.services.analysis_service import AnalysisError

    service = StubService(error=AnalysisError("rate limited"))
    with pytest.raises(EvaluationError, match="rate limited"):
        evaluate_campaign(CAMPAIGN, DNA, service)


def test_non_object_response_rejected():
    with pytest.raises(EvaluationError, match="JSON object"):
        evaluate_campaign(CAMPAIGN, DNA, StubService(payload=["nope"]))


def test_all_zero_scores_rejected():
    payload = {d: 0 for d in DIMENSIONS}
    with pytest.raises(EvaluationError, match="no usable scores"):
        evaluate_campaign(CAMPAIGN, DNA, StubService(payload))


# --- persistence helper ------------------------------------------------------


def test_load_evaluation_roundtrip():
    e = evaluate_campaign(CAMPAIGN, DNA, StubService())
    assert load_evaluation(e.model_dump_json()).overall == e.overall


def test_load_evaluation_handles_garbage():
    assert load_evaluation(None) is None
    assert load_evaluation("not json") is None
    assert load_evaluation('{"overall": "???"}') is None or isinstance(
        load_evaluation('{"overall": "???"}'), CampaignEvaluation
    )
