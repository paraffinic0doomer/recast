import pytest

from app.schemas.campaign import (
    Campaign,
    FacebookContent,
    InstagramContent,
    LinkedInContent,
    TikTokContent,
    X_POST_MAX,
    XContent,
    YOUTUBE_TITLE_MAX,
    YouTubeContent,
)
from app.schemas.content_dna import ContentDNA
from app.schemas.moment import BestMoment, MomentScores
from app.services.analysis_service import AnalysisError
from app.services.platform_service import (
    PLATFORM_SPECS,
    build_chapters,
    build_platform_prompt,
    generate_campaign,
    generate_platform,
    score_campaign,
)

DNA = ContentDNA.model_validate(
    {
        "primary_topic": "Repurposing video content",
        "secondary_topics": ["Automation"],
        "audience": "Content creators",
        "tone": "Educational",
        "content_type": "Tutorial",
        "core_message": "One video can become a whole campaign.",
        "key_points": ["Manual repurposing wastes hours", "Wrong moments get clipped"],
        "important_concepts": ["Repurposing"],
        "entities": ["RECAST"],
        "keywords": ["repurposing", "shorts", "automation"],
        "hooks": ["Nobody wants to watch you say hello"],
        "cta": "Subscribe for more",
        "key_moments": [
            {"timestamp": 0.0, "title": "Intro"},
            {"timestamp": 20.0, "title": "The problem"},
            {"timestamp": 45.0, "title": "The fix"},
            {"timestamp": 70.0, "title": "The tool"},
        ],
    }
)

MOMENTS = [
    BestMoment(
        id="m1", start=45.0, end=70.0, title="The fix", hook="So what is the fix?",
        scores=MomentScores(hook_strength=90, information_value=90,
                            standalone_quality=90, emotional_interest=90),
    )
]


# --- platform specs ----------------------------------------------------------


def test_all_six_platforms_supported():
    assert set(PLATFORM_SPECS) == {
        "youtube", "instagram", "tiktok", "facebook", "linkedin", "x"
    }


def test_each_platform_has_distinct_strategy():
    """The differentiation must live in the specs, not be left to the model."""
    for attr in ("tone", "length", "structure", "hook_strategy", "cta_strategy"):
        values = [getattr(spec, attr) for spec in PLATFORM_SPECS.values()]
        assert len(set(values)) == len(values), f"duplicate {attr} across platforms"


def test_prompts_differ_per_platform():
    prompts = {
        key: build_platform_prompt(spec, DNA, MOMENTS)
        for key, spec in PLATFORM_SPECS.items()
    }
    assert len(set(prompts.values())) == len(prompts)
    assert "under 280 characters" in prompts["x"]
    assert "Professional" in prompts["linkedin"]
    assert "scroll-stopper" in prompts["instagram"]


def test_prompt_carries_content_dna_and_moments():
    prompt = build_platform_prompt(PLATFORM_SPECS["tiktok"], DNA, MOMENTS)
    assert "One video can become a whole campaign." in prompt
    assert "Content creators" in prompt
    assert "So what is the fix?" in prompt


# --- validation / limits -----------------------------------------------------


def test_x_post_truncated_to_limit():
    content = XContent.model_validate({"post": "x" * 400, "thread": ["y" * 400]})
    assert len(content.post) <= X_POST_MAX
    assert all(len(t) <= X_POST_MAX for t in content.thread)


def test_youtube_title_limit_and_count():
    content = YouTubeContent.model_validate(
        {"titles": ["a" * 200, "b", "c", "d", "e"], "description": "d"}
    )
    assert len(content.titles) == 3
    assert all(len(t) <= YOUTUBE_TITLE_MAX for t in content.titles)


def test_hashtags_normalised_and_deduped():
    content = InstagramContent.model_validate(
        {"hashtags": ["#Repurposing", "repurposing", " shorts ", "", "#a-b!c"]}
    )
    assert content.hashtags == ["#Repurposing", "#shorts", "#abc"]


def test_hashtag_caps_differ_by_platform():
    many = [f"tag{i}" for i in range(40)]
    assert len(InstagramContent.model_validate({"hashtags": many}).hashtags) == 30
    assert len(TikTokContent.model_validate({"hashtags": many}).hashtags) == 8
    assert len(FacebookContent.model_validate({"hashtags": many}).hashtags) == 5
    assert len(LinkedInContent.model_validate({"hashtags": many}).hashtags) == 5


def test_reel_cover_text_kept_short():
    content = InstagramContent.model_validate({"reel_cover_text": "w" * 300})
    assert len(content.reel_cover_text) <= 60


def test_list_valued_caption_is_joined():
    content = FacebookContent.model_validate({"caption": ["Line one", "Line two"]})
    assert "Line one" in content.caption and "Line two" in content.caption


# --- chapters ----------------------------------------------------------------


def test_chapters_built_from_real_timestamps():
    chapters = build_chapters(MOMENTS, DNA)
    assert [c.timestamp for c in chapters] == [0.0, 20.0, 45.0, 70.0]
    assert chapters[0].formatted == "0:00"
    assert chapters[2].formatted == "0:45"


def test_chapters_require_zero_start():
    dna = DNA.model_copy(deep=True)
    for m, ts in zip(dna.key_moments, [12.0, 30.0, 60.0, 90.0]):
        m.timestamp = ts
    chapters = build_chapters([], dna)
    assert chapters[0].timestamp == 0.0  # synthetic intro prepended


def test_chapters_dropped_when_too_few():
    dna = DNA.model_copy(deep=True)
    dna.key_moments = dna.key_moments[:1]
    assert build_chapters([], dna) == []


def test_chapters_drop_entries_closer_than_ten_seconds():
    dna = DNA.model_copy(deep=True)
    for m, ts in zip(dna.key_moments, [0.0, 3.0, 5.0, 40.0]):
        m.timestamp = ts
    chapters = build_chapters([], dna)
    gaps = [b.timestamp - a.timestamp for a, b in zip(chapters, chapters[1:])]
    assert all(g >= 10 for g in gaps)


def test_youtube_drops_invalid_chapter_sets():
    content = YouTubeContent.model_validate(
        {"chapters": [{"timestamp": 5.0, "label": "a"}, {"timestamp": 40.0, "label": "b"}]}
    )
    assert content.chapters == []  # fewer than 3 and does not start at 0:00


# --- generation --------------------------------------------------------------


class StubService:
    """Returns platform-appropriate payloads and records the prompts it saw."""

    def __init__(self, payloads=None, fail=()):
        self.prompts = []
        self.fail = set(fail)
        self.payloads = payloads or {
            "YouTube": {
                "titles": ["Title A", "Title B", "Title C"],
                "description": "A long-form description for search.",
                "seo_keywords": ["repurposing"],
                "tags": ["shorts"],
            },
            "Instagram": {
                "caption": "A warm personal caption.",
                "hashtags": ["repurposing"],
                "cta": "Save this",
                "reel_cover_text": "ONE VIDEO",
            },
            "TikTok": {
                "hook": "you are wasting hours",
                "caption": "short teaser",
                "hashtags": ["creators"],
                "cta": "follow for part 2",
            },
            "Facebook": {
                "caption": "A plain-spoken explanation.",
                "cta": "What do you think?",
                "hashtags": ["creators"],
            },
            "LinkedIn": {
                "post": "A professional insight post.",
                "cta": "How does your team handle this?",
                "hashtags": ["ContentStrategy"],
            },
            "X": {"post": "One video. A whole campaign.", "thread": ["Beat one", "Beat two"]},
        }

    def complete_json(self, prompt, system=None):
        self.prompts.append(prompt)
        for label, payload in self.payloads.items():
            if f"PLATFORM BRIEF - {label}" in prompt:
                if label in self.fail:
                    raise AnalysisError(f"{label} upstream failure")
                return payload
        if "Evaluate this generated social media campaign" in prompt:
            # Campaign generation now also evaluates; subclasses override this.
            raise AnalysisError("no evaluator configured in this stub")
        raise AssertionError("prompt did not identify a platform")


def test_generate_single_platform():
    content = generate_platform("tiktok", DNA, MOMENTS, service=StubService())
    assert isinstance(content, TikTokContent)
    assert content.hook == "you are wasting hours"


def test_unknown_platform_rejected():
    with pytest.raises(AnalysisError, match="Unknown platform"):
        generate_platform("myspace", DNA, MOMENTS, service=StubService())


def test_generate_campaign_covers_all_platforms():
    campaign, failed = generate_campaign(DNA, MOMENTS, service=StubService())
    assert failed == []
    assert campaign.generated_platforms == [
        "youtube", "instagram", "tiktok", "facebook", "linkedin", "x"
    ]


def test_one_llm_call_per_platform():
    """Six separate calls is what makes the outputs genuinely platform-native."""
    stub = StubService()
    generate_campaign(DNA, MOMENTS, service=stub)
    assert len(stub.prompts) == 6


def test_platform_failure_does_not_abort_the_rest():
    stub = StubService(fail={"LinkedIn"})
    campaign, failed = generate_campaign(DNA, MOMENTS, service=stub)
    assert failed == ["linkedin"]
    assert campaign.linkedin is None
    assert campaign.youtube is not None
    assert campaign.x is not None


def test_regenerating_one_platform_keeps_the_others():
    stub = StubService()
    campaign, _ = generate_campaign(DNA, MOMENTS, service=stub)
    original_youtube = campaign.youtube.titles

    stub.payloads["TikTok"] = {"hook": "brand new hook", "caption": "c", "hashtags": [], "cta": ""}
    updated, _ = generate_campaign(
        DNA, MOMENTS, platforms=["tiktok"], service=stub, existing=campaign
    )
    assert updated.tiktok.hook == "brand new hook"
    assert updated.youtube.titles == original_youtube


def test_youtube_chapters_come_from_timestamps_not_model():
    stub = StubService()
    stub.payloads["YouTube"]["chapters"] = [{"timestamp": 9999.0, "label": "fabricated"}]
    campaign, _ = generate_campaign(DNA, MOMENTS, platforms=["youtube"], service=stub)
    assert [c.timestamp for c in campaign.youtube.chapters] == [0.0, 20.0, 45.0, 70.0]
    assert all(c.label != "fabricated" for c in campaign.youtube.chapters)


# --- scoring -----------------------------------------------------------------


def test_score_rewards_full_coverage():
    campaign, _ = generate_campaign(DNA, MOMENTS, service=StubService())
    full = score_campaign(campaign, DNA, MOMENTS)
    partial, _ = generate_campaign(DNA, MOMENTS, platforms=["x"], service=StubService())
    assert full > score_campaign(partial, DNA, MOMENTS)
    assert 0 <= full <= 100


def test_score_is_capped_at_100():
    campaign, _ = generate_campaign(DNA, MOMENTS, service=StubService())
    assert score_campaign(campaign, DNA, MOMENTS * 10) <= 100


def test_empty_campaign_scores_low():
    assert score_campaign(Campaign(), ContentDNA(), []) == 0.0
