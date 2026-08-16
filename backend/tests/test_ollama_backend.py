"""Covers the real OllamaAnalysisService HTTP path without requiring Ollama installed."""

import json

import httpx
import pytest

from app.services.analysis_service import AnalysisError, OllamaAnalysisService

GOOD_DNA = {
    "primary_topic": "Repurposing video",
    "secondary_topics": ["Automation"],
    "audience": "Creators",
    "tone": "Educational",
    "content_type": "Explainer",
    "core_message": "One video, one campaign.",
    "key_points": ["Manual work is slow"],
    "important_concepts": ["Repurposing"],
    "entities": ["RECAST"],
    "keywords": ["repurposing"],
    "hooks": ["Stop rewriting captions"],
    "cta": "Subscribe",
    "key_moments": [{"timestamp": 3.0, "title": "Problem", "description": "d"}],
}


def _service():
    return OllamaAnalysisService("http://localhost:11434", "llama3.2:3b", 30.0)


def _ok_response(content: dict | str) -> httpx.Response:
    body = content if isinstance(content, str) else json.dumps(content)
    return httpx.Response(
        200,
        json={"message": {"content": body}},
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )


def test_sends_expected_request_shape(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        captured["timeout"] = kwargs.get("timeout")
        return _ok_response(GOOD_DNA)

    monkeypatch.setattr(httpx, "post", fake_post)

    dna = _service().analyze("some transcript", [{"start": 3.0, "text": "hi"}])

    assert captured["url"] == "http://localhost:11434/api/chat"
    payload = captured["json"]
    assert payload["model"] == "llama3.2:3b"
    assert payload["format"] == "json"  # forces structured output
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0.2
    assert payload["messages"][0]["role"] == "system"
    assert "some transcript" in payload["messages"][1]["content"]
    assert captured["timeout"] == 30.0
    assert dna.primary_topic == "Repurposing video"


def test_model_not_found_gives_pull_instructions(monkeypatch):
    def fake_post(url, **kwargs):
        raise httpx.HTTPStatusError(
            "not found",
            request=httpx.Request("POST", url),
            response=httpx.Response(404, text="model not found", request=httpx.Request("POST", url)),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(AnalysisError, match="ollama pull llama3.2:3b"):
        _service().analyze("t")


def test_server_error_surfaces_status(monkeypatch):
    def fake_post(url, **kwargs):
        raise httpx.HTTPStatusError(
            "boom",
            request=httpx.Request("POST", url),
            response=httpx.Response(500, text="internal", request=httpx.Request("POST", url)),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(AnalysisError, match="500"):
        _service().analyze("t")


def test_timeout_suggests_smaller_model(monkeypatch):
    def fake_post(url, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(AnalysisError, match="llama3.2:1b"):
        _service().analyze("t")


def test_connection_refused_is_actionable(monkeypatch):
    def fake_post(url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(AnalysisError, match="Could not reach Ollama"):
        _service().analyze("t")


def test_handles_model_wrapping_json_in_prose(monkeypatch):
    """Small models often ignore instructions and add commentary around the JSON."""
    wrapped = f"Sure, here is the analysis:\n```json\n{json.dumps(GOOD_DNA)}\n```"
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _ok_response(wrapped))

    dna = _service().analyze("t")
    assert dna.core_message == "One video, one campaign."


def test_rejects_unusable_model_output(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: _ok_response("I'm sorry, I can't do that.")
    )

    with pytest.raises(AnalysisError, match="did not return valid JSON"):
        _service().analyze("t")


def test_hallucinated_timestamp_dropped_via_service(monkeypatch):
    payload = dict(GOOD_DNA)
    payload["key_moments"] = [{"timestamp": 5000.0, "title": "way past the end"}]
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _ok_response(payload))

    dna = _service().analyze("t", max_timestamp=42.0)
    assert dna.key_moments[0].timestamp is None
    assert dna.key_moments[0].title == "way past the end"
