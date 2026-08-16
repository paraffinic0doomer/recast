"""Content analysis service — turns a transcript into structured Content DNA.

The pipeline depends only on `AnalysisService` / `get_analysis_service()`, so
backends can be swapped via environment variables.

Backends (selected by ANALYSIS_BACKEND):
  - "groq"   : Groq chat completions (OpenAI-compatible). Requires GROQ_API_KEY.
  - "local"  : Ollama running on this machine. Free, offline, no API key.
  - "openai" : OpenAI chat completions. Requires OPENAI_API_KEY.
  - "auto"   : (default) prefer Groq, then Ollama, then OpenAI.

No backend ever fabricates analysis: if none is available the call raises and the
project is marked failed with an actionable message.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path

import httpx
from openai import OpenAI
from pydantic import ValidationError

from app.core.config import groq_key_pool, settings
from app.core.key_pool import call_with_rotation
from app.schemas.content_dna import ContentDNA

logger = logging.getLogger(__name__)

MAX_TRANSCRIPT_CHARS = 12_000
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class AnalysisError(RuntimeError):
    """Raised when an analysis attempt fails."""


class AnalysisNotConfiguredError(AnalysisError):
    """Raised when no analysis backend is available."""


SYSTEM_PROMPT = (
    "You are a senior social-media content strategist. You analyse a video "
    "transcript and return a single structured JSON object describing the "
    "content. Base every field strictly on the transcript. Never invent facts, "
    "products, or claims that are not present. Respond with JSON only."
)

JSON_SHAPE = """{
  "primary_topic": "one short phrase",
  "secondary_topics": ["..."],
  "audience": "who this content is for",
  "tone": "e.g. educational, energetic, conversational",
  "content_type": "e.g. tutorial, vlog, interview, product demo",
  "core_message": "the single most important takeaway, one sentence",
  "key_points": ["important claims actually made"],
  "important_concepts": ["core ideas or terms explained"],
  "entities": ["people, products, brands, tools, places mentioned"],
  "keywords": ["SEO-relevant keywords"],
  "hooks": ["scroll-stopping opening lines usable on social"],
  "cta": "the call to action if one exists, otherwise null",
  "key_moments": [
    {"timestamp": 12.5, "title": "short label", "description": "why it matters"}
  ]
}"""


def build_prompt(transcript_text: str, segments: list[dict] | None = None) -> str:
    """Build the analysis prompt. Segments give the model real timestamps to anchor to."""
    transcript_text = (transcript_text or "").strip()
    if len(transcript_text) > MAX_TRANSCRIPT_CHARS:
        transcript_text = transcript_text[:MAX_TRANSCRIPT_CHARS] + "\n[transcript truncated]"

    timeline = ""
    if segments:
        lines = [
            f"[{float(s.get('start', 0)):.1f}s] {str(s.get('text', '')).strip()}"
            for s in segments[:120]
        ]
        timeline = "\nTIMESTAMPED SEGMENTS:\n" + "\n".join(lines)

    return (
        f"Analyse this video transcript and return JSON matching exactly this shape:\n"
        f"{JSON_SHAPE}\n\n"
        f"Rules:\n"
        f"- Provide up to 10 key_moments, each covering a DISTINCT moment.\n"
        f"- Never emit two key_moments with the same timestamp, and order them "
        f"chronologically. Fewer strong moments beat padding with duplicates.\n"
        f"- key_moments timestamps must come from the timestamped segments below.\n"
        f"- entities must be real named people, products, brands, tools or places. "
        f"Omit generic references like 'the channel' or 'the video'.\n"
        f"- If there is no explicit call to action, set cta to null.\n"
        f"- key_points should capture the substantive claims actually argued, not "
        f"restate the topic.\n"
        f"- Keep every string concise and specific to this transcript.\n\n"
        f"TRANSCRIPT:\n{transcript_text}\n{timeline}"
    )


def extract_json(raw: str) -> dict:
    """Pull a JSON object out of a model response, tolerating prose or code fences."""
    if not raw or not raw.strip():
        raise AnalysisError("Model returned an empty response")

    text = raw.strip()

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AnalysisError(
                f"Model did not return valid JSON. Received: {raw[:200]}"
            ) from None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"Model returned malformed JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise AnalysisError("Model returned JSON that is not an object")
    return parsed


def to_content_dna(payload: dict, max_timestamp: float | None = None) -> ContentDNA:
    """Validate a raw model payload into ContentDNA, dropping impossible timestamps."""
    try:
        dna = ContentDNA.model_validate(payload)
    except ValidationError as exc:
        raise AnalysisError(f"Model output failed validation: {exc}") from exc

    if max_timestamp is not None:
        for moment in dna.key_moments:
            # Small models sometimes invent timestamps past the end of the video.
            if moment.timestamp is not None and moment.timestamp > max_timestamp:
                logger.warning(
                    "Dropping out-of-range key moment timestamp %.1fs (video is %.1fs)",
                    moment.timestamp,
                    max_timestamp,
                )
                moment.timestamp = None
    return dna


class AnalysisService(ABC):
    @abstractmethod
    def complete_json(self, prompt: str, system: str | None = None) -> dict:
        """Run a prompt and return parsed JSON. Shared by all LLM-backed features."""

    def analyze(
        self,
        transcript_text: str,
        segments: list[dict] | None = None,
        max_timestamp: float | None = None,
    ) -> ContentDNA:
        payload = self.complete_json(build_prompt(transcript_text, segments))
        return to_content_dna(payload, max_timestamp)


class OllamaAnalysisService(AnalysisService):
    """Runs a local LLM through Ollama. No API key, no network beyond localhost."""

    def __init__(self, host: str, model: str, timeout: float) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = timeout

    def complete_json(self, prompt: str, system: str | None = None) -> dict:
        logger.info("Querying Ollama model %s", self._model)

        try:
            response = httpx.post(
                f"{self._host}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system or SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:200]
            if exc.response.status_code == 404:
                raise AnalysisError(
                    f"Ollama model '{self._model}' not found. Run: ollama pull {self._model}"
                ) from exc
            raise AnalysisError(f"Ollama request failed ({exc.response.status_code}): {detail}") from exc
        except httpx.TimeoutException as exc:
            raise AnalysisError(
                f"Ollama timed out after {self._timeout:.0f}s. Try a smaller model "
                f"(e.g. llama3.2:1b) or raise OLLAMA_TIMEOUT."
            ) from exc
        except httpx.HTTPError as exc:
            raise AnalysisError(f"Could not reach Ollama at {self._host}: {exc}") from exc

        content = (response.json().get("message") or {}).get("content", "")
        return extract_json(content)


class OpenAIAnalysisService(AnalysisService):
    """Works with any OpenAI-compatible chat completions API (OpenAI, Groq, ...).

    When `key_pool` is supplied, a rate-limited key is swapped for the next one
    automatically instead of failing the request.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        key_pool=None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._key_pool = key_pool
        self._client = self._build_client(api_key)

    def _build_client(self, api_key: str) -> OpenAI:
        return (
            OpenAI(api_key=api_key, base_url=self._base_url)
            if self._base_url
            else OpenAI(api_key=api_key)
        )

    def _request(self, api_key: str, prompt: str, system: str | None):
        client = self._client if api_key == self._api_key else self._build_client(api_key)
        return client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system or SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

    def complete_json(self, prompt: str, system: str | None = None) -> dict:
        logger.info("Querying model %s", self._model)

        try:
            if self._key_pool is not None and self._key_pool.configured:
                response = call_with_rotation(
                    self._key_pool,
                    lambda key: self._request(key, prompt, system),
                    what="analysis request",
                )
            else:
                response = self._request(self._api_key, prompt, system)
        except Exception as exc:
            raise AnalysisError(f"Analysis request failed: {exc}") from exc

        return extract_json(response.choices[0].message.content or "")


def _groq_service() -> "OpenAIAnalysisService":
    pool = groq_key_pool()
    return OpenAIAnalysisService(
        api_key=pool.acquire() or settings.groq_api_key,
        model=settings.groq_analysis_model,
        base_url=GROQ_BASE_URL,
        key_pool=pool,
    )


def ollama_available() -> bool:
    """True if an Ollama server is reachable on the configured host."""
    try:
        res = httpx.get(f"{settings.ollama_host.rstrip('/')}/api/tags", timeout=2.0)
        return res.status_code == 200
    except httpx.HTTPError:
        return False


def get_analysis_service() -> AnalysisService:
    """Factory for the active analysis backend, selected via environment variables."""
    backend = settings.analysis_backend.strip().lower()

    if backend == "groq":
        if not settings.groq_configured:
            raise AnalysisNotConfiguredError(
                "ANALYSIS_BACKEND=groq but GROQ_API_KEY is not set in backend/.env."
            )
        return _groq_service()

    if backend == "local":
        if not ollama_available():
            raise AnalysisNotConfiguredError(
                f"ANALYSIS_BACKEND=local but no Ollama server is reachable at "
                f"{settings.ollama_host}. Install Ollama and run: ollama pull {settings.ollama_model}"
            )
        return OllamaAnalysisService(
            settings.ollama_host, settings.ollama_model, settings.ollama_timeout
        )

    if backend == "openai":
        if not settings.openai_configured:
            raise AnalysisNotConfiguredError(
                "ANALYSIS_BACKEND=openai but OPENAI_API_KEY is not set in backend/.env."
            )
        return OpenAIAnalysisService(settings.openai_api_key, settings.openai_analysis_model)

    if backend != "auto":
        raise AnalysisNotConfiguredError(
            f"Unknown ANALYSIS_BACKEND '{backend}'. Use 'auto', 'groq', 'local', or 'openai'."
        )

    # Hosted APIs first: far stronger models than a small local one, and no
    # multi-GB download on the machine running the backend.
    if settings.groq_configured:
        return _groq_service()
    if ollama_available():
        return OllamaAnalysisService(
            settings.ollama_host, settings.ollama_model, settings.ollama_timeout
        )
    if settings.openai_configured:
        return OpenAIAnalysisService(settings.openai_api_key, settings.openai_analysis_model)

    raise AnalysisNotConfiguredError(
        "No analysis backend available. Set GROQ_API_KEY in backend/.env (fastest to "
        f"set up), or start Ollama (ollama pull {settings.ollama_model}), "
        "or set OPENAI_API_KEY."
    )
