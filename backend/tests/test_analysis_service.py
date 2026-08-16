import pytest

from app.schemas.content_dna import ContentDNA
from app.services.analysis_service import (
    AnalysisError,
    AnalysisNotConfiguredError,
    OllamaAnalysisService,
    OpenAIAnalysisService,
    build_prompt,
    extract_json,
    get_analysis_service,
    to_content_dna,
)

VALID_PAYLOAD = {
    "primary_topic": "Repurposing video content",
    "secondary_topics": ["Social media", "Automation"],
    "audience": "Content creators",
    "tone": "Educational",
    "content_type": "Product explainer",
    "core_message": "One video can become a whole campaign.",
    "key_points": ["Creators waste hours repurposing manually"],
    "important_concepts": ["Content repurposing"],
    "entities": ["RECAST"],
    "keywords": ["repurposing", "social media"],
    "hooks": ["Stop rewriting captions by hand"],
    "cta": "Subscribe for more",
    "key_moments": [{"timestamp": 8.0, "title": "The problem", "description": "Manual work"}],
}


# --- JSON extraction ---------------------------------------------------------


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_from_code_fence():
    raw = 'Here you go:\n```json\n{"a": 2}\n```\nHope that helps!'
    assert extract_json(raw) == {"a": 2}


def test_extract_json_with_surrounding_prose():
    raw = 'Sure! {"a": 3} — let me know if you need more.'
    assert extract_json(raw) == {"a": 3}


def test_extract_json_empty_response():
    with pytest.raises(AnalysisError, match="empty response"):
        extract_json("   ")


def test_extract_json_no_object():
    with pytest.raises(AnalysisError, match="did not return valid JSON"):
        extract_json("I cannot help with that.")


def test_extract_json_rejects_non_object():
    with pytest.raises(AnalysisError, match="not an object"):
        extract_json("[1, 2, 3]")


# --- Validation --------------------------------------------------------------


def test_to_content_dna_valid():
    dna = to_content_dna(VALID_PAYLOAD)
    assert dna.primary_topic == "Repurposing video content"
    assert dna.cta == "Subscribe for more"
    assert dna.key_moments[0].timestamp == 8.0


def test_out_of_range_timestamps_are_dropped():
    """Small models sometimes invent timestamps past the end of the video."""
    payload = dict(VALID_PAYLOAD)
    payload["key_moments"] = [
        {"timestamp": 5.0, "title": "ok", "description": ""},
        {"timestamp": 9999.0, "title": "hallucinated", "description": ""},
    ]
    dna = to_content_dna(payload, max_timestamp=42.0)
    assert dna.key_moments[0].timestamp == 5.0
    assert dna.key_moments[1].timestamp is None  # dropped, moment itself preserved


def test_cta_absent_variants_normalise_to_none():
    for value in [None, "", "none", "N/A", "not present"]:
        dna = ContentDNA.model_validate({**VALID_PAYLOAD, "cta": value})
        assert dna.cta is None, value


def test_list_fields_dedupe_and_strip():
    dna = ContentDNA.model_validate(
        {**VALID_PAYLOAD, "keywords": ["  seo ", "SEO", "video", "", "video"]}
    )
    assert dna.keywords == ["seo", "video"]


def test_scalar_field_accepts_list_from_sloppy_model():
    dna = ContentDNA.model_validate({**VALID_PAYLOAD, "tone": ["Energetic", "Friendly"]})
    assert dna.tone == "Energetic, Friendly"


def test_missing_fields_default_rather_than_crash():
    dna = ContentDNA.model_validate({"primary_topic": "X"})
    assert dna.primary_topic == "X"
    assert dna.keywords == []
    assert dna.cta is None


def test_negative_timestamp_clamped():
    dna = ContentDNA.model_validate(
        {**VALID_PAYLOAD, "key_moments": [{"timestamp": -4.0, "title": "t"}]}
    )
    assert dna.key_moments[0].timestamp == 0.0


# --- Prompt ------------------------------------------------------------------


def test_prompt_includes_transcript_and_timestamps():
    prompt = build_prompt("hello world", [{"start": 3.5, "text": "hello world"}])
    assert "hello world" in prompt
    assert "[3.5s]" in prompt


def test_prompt_truncates_very_long_transcripts():
    prompt = build_prompt("x" * 50_000)
    assert "[transcript truncated]" in prompt
    assert len(prompt) < 20_000


# --- Backend selection -------------------------------------------------------


def test_auto_prefers_groq_when_key_present(monkeypatch):
    """Hosted Groq beats a small local model, and needs no multi-GB download."""
    import app.services.analysis_service as a

    monkeypatch.setattr(a.settings, "analysis_backend", "auto")
    monkeypatch.setattr(a.settings, "groq_api_key", "gsk-test")
    monkeypatch.setattr(a, "ollama_available", lambda: True)
    service = get_analysis_service()
    assert isinstance(service, OpenAIAnalysisService)
    assert service._model == a.settings.groq_analysis_model


def test_auto_prefers_ollama_when_no_groq_key(monkeypatch):
    import app.services.analysis_service as a

    monkeypatch.setattr(a.settings, "analysis_backend", "auto")
    monkeypatch.setattr(a.settings, "groq_api_key", "")
    monkeypatch.setattr(a, "ollama_available", lambda: True)
    monkeypatch.setattr(a.settings, "openai_api_key", "sk-real-looking-key")
    assert isinstance(get_analysis_service(), OllamaAnalysisService)


def test_auto_falls_back_to_openai(monkeypatch):
    import app.services.analysis_service as a

    monkeypatch.setattr(a.settings, "analysis_backend", "auto")
    monkeypatch.setattr(a.settings, "groq_api_key", "")
    monkeypatch.setattr(a, "ollama_available", lambda: False)
    monkeypatch.setattr(a.settings, "openai_api_key", "sk-real-looking-key")
    assert isinstance(get_analysis_service(), OpenAIAnalysisService)


def test_auto_raises_when_nothing_available(monkeypatch):
    import app.services.analysis_service as a

    monkeypatch.setattr(a.settings, "analysis_backend", "auto")
    monkeypatch.setattr(a.settings, "groq_api_key", "")
    monkeypatch.setattr(a, "ollama_available", lambda: False)
    monkeypatch.setattr(a.settings, "openai_api_key", "")
    with pytest.raises(AnalysisNotConfiguredError, match="GROQ_API_KEY"):
        get_analysis_service()


def test_explicit_groq_requires_key(monkeypatch):
    import app.services.analysis_service as a

    monkeypatch.setattr(a.settings, "analysis_backend", "groq")
    monkeypatch.setattr(a.settings, "groq_api_key", "")
    with pytest.raises(AnalysisNotConfiguredError, match="GROQ_API_KEY"):
        get_analysis_service()


def test_groq_uses_groq_base_url(monkeypatch):
    """The Groq backend must point at Groq, not api.openai.com."""
    import app.services.analysis_service as a

    monkeypatch.setattr(a.settings, "analysis_backend", "groq")
    monkeypatch.setattr(a.settings, "groq_api_key", "gsk-test")
    service = get_analysis_service()
    assert "groq.com" in str(service._client.base_url)


def test_explicit_local_requires_server(monkeypatch):
    import app.services.analysis_service as a

    monkeypatch.setattr(a.settings, "analysis_backend", "local")
    monkeypatch.setattr(a.settings, "groq_api_key", "")
    monkeypatch.setattr(a, "ollama_available", lambda: False)
    with pytest.raises(AnalysisNotConfiguredError, match="no Ollama server"):
        get_analysis_service()


def test_unknown_backend_rejected(monkeypatch):
    import app.services.analysis_service as a

    monkeypatch.setattr(a.settings, "analysis_backend", "mango")
    with pytest.raises(AnalysisNotConfiguredError, match="Unknown ANALYSIS_BACKEND"):
        get_analysis_service()


def test_duplicate_key_moments_collapsed():
    """Models pad toward the requested count by repeating the same timestamp."""
    dna = ContentDNA.model_validate(
        {
            **VALID_PAYLOAD,
            "key_moments": [
                {"timestamp": 19.0, "title": "The Solution", "description": "a"},
                {"timestamp": 8.0, "title": "The Problem", "description": "b"},
                {"timestamp": 19.0, "title": "Problem Statement", "description": "c"},
                {"timestamp": 19.0, "title": "Alternative Solution", "description": "d"},
                {"timestamp": 0.0, "title": "Intro", "description": "e"},
            ],
        }
    )
    times = [m.timestamp for m in dna.key_moments]
    assert times == [0.0, 8.0, 19.0]  # deduped and chronological
    assert len(times) == len(set(times))


def test_duplicate_titles_collapsed():
    dna = ContentDNA.model_validate(
        {
            **VALID_PAYLOAD,
            "key_moments": [
                {"timestamp": 1.0, "title": "Intro", "description": "a"},
                {"timestamp": 2.0, "title": "intro", "description": "b"},
            ],
        }
    )
    assert len(dna.key_moments) == 1


def test_key_moments_capped_at_ten():
    dna = ContentDNA.model_validate(
        {
            **VALID_PAYLOAD,
            "key_moments": [
                {"timestamp": float(i), "title": f"m{i}"} for i in range(25)
            ],
        }
    )
    assert len(dna.key_moments) == 10
