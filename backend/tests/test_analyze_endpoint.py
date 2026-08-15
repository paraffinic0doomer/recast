import json

from app.schemas.content_dna import ContentDNA
from app.services import pipeline_service
from app.services.analysis_service import AnalysisError
from app.services.transcription_service import TranscriptResult, TranscriptSegment

DNA = ContentDNA.model_validate(
    {
        "primary_topic": "Repurposing video content",
        "secondary_topics": ["Automation"],
        "audience": "Content creators",
        "tone": "Educational",
        "content_type": "Explainer",
        "core_message": "One video can become a whole campaign.",
        "key_points": ["Manual repurposing wastes hours"],
        "important_concepts": ["Content repurposing"],
        "entities": ["RECAST"],
        "keywords": ["repurposing"],
        "hooks": ["Stop rewriting captions by hand"],
        "cta": "Subscribe",
        "key_moments": [{"timestamp": 2.0, "title": "The problem", "description": "why"}],
    }
)


class StubTranscription:
    def transcribe(self, audio_path):
        return TranscriptResult(
            text="Some spoken words about repurposing.",
            language="en",
            duration=6.0,
            segments=[TranscriptSegment(start=0.0, end=6.0, text="Some spoken words.")],
        )


class StubAnalysis:
    def __init__(self, dna=DNA):
        self.dna = dna
        self.calls = []

    def analyze(self, transcript_text, segments=None, max_timestamp=None):
        self.calls.append({"text": transcript_text, "segments": segments, "max": max_timestamp})
        return self.dna


def _transcribed_project(client, sample_video, monkeypatch):
    monkeypatch.setattr(
        pipeline_service, "get_transcription_service", lambda: StubTranscription()
    )
    project = client.post("/api/projects", json={"title": "DNA"}).json()
    with sample_video.open("rb") as f:
        client.post(
            "/api/upload",
            data={"project_id": project["id"]},
            files={"video": ("v.mp4", f, "video/mp4")},
        )
    client.post(f"/api/projects/{project['id']}/process")
    return project["id"]


def test_analyze_requires_transcript(client):
    project = client.post("/api/projects", json={"title": "Bare"}).json()
    res = client.post(f"/api/projects/{project['id']}/analyze")
    assert res.status_code == 400
    assert "transcript" in res.json()["detail"].lower()


def test_analyze_unknown_project(client):
    assert client.post("/api/projects/nope/analyze").status_code == 404


def test_content_dna_404_before_analysis(client, sample_video, monkeypatch):
    project_id = _transcribed_project(client, sample_video, monkeypatch)
    res = client.get(f"/api/projects/{project_id}/content-dna")
    assert res.status_code == 404
    assert "not ready" in res.json()["detail"].lower()


def test_analyze_produces_and_persists_content_dna(client, sample_video, monkeypatch):
    stub = StubAnalysis()
    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: stub)

    project_id = _transcribed_project(client, sample_video, monkeypatch)
    res = client.post(f"/api/projects/{project_id}/analyze")
    assert res.status_code == 200

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["status"] == "analyzed"
    assert detail["error_message"] is None
    assert detail["content_dna"]["primary_topic"] == "Repurposing video content"

    dna_res = client.get(f"/api/projects/{project_id}/content-dna")
    assert dna_res.status_code == 200
    body = dna_res.json()
    assert body["project_id"] == project_id
    assert body["content_dna"]["core_message"] == "One video can become a whole campaign."
    assert body["content_dna"]["key_moments"][0]["timestamp"] == 2.0


def test_analysis_receives_transcript_and_duration(client, sample_video, monkeypatch):
    """Analysis must be driven by the stored transcript, not re-derived from the video."""
    stub = StubAnalysis()
    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: stub)

    project_id = _transcribed_project(client, sample_video, monkeypatch)
    client.post(f"/api/projects/{project_id}/analyze")

    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert "repurposing" in call["text"].lower()
    assert call["segments"] and call["segments"][0]["start"] == 0.0
    assert call["max"] is not None  # video duration, used to reject bad timestamps


def test_key_topics_derived_from_dna(client, sample_video, monkeypatch):
    """key_topics must come from Content DNA so there is a single source of truth."""
    stub = StubAnalysis()
    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: stub)

    project_id = _transcribed_project(client, sample_video, monkeypatch)
    client.post(f"/api/projects/{project_id}/analyze")

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["key_topics"] == ["Repurposing video content", "Automation"]


def test_analysis_failure_preserves_transcript_and_allows_retry(
    client, sample_video, monkeypatch
):
    class Failing:
        def analyze(self, *a, **k):
            raise AnalysisError("Ollama model 'llama3.2:3b' not found. Run: ollama pull llama3.2:3b")

    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: Failing())
    project_id = _transcribed_project(client, sample_video, monkeypatch)
    client.post(f"/api/projects/{project_id}/analyze")

    failed = client.get(f"/api/projects/{project_id}").json()
    assert failed["status"] == "failed"
    assert "ollama pull" in failed["error_message"]
    # Transcript survives so the user can retry analysis without re-uploading.
    assert failed["transcript"] is not None
    assert failed["content_dna"] is None

    dna_res = client.get(f"/api/projects/{project_id}/content-dna")
    assert dna_res.status_code == 409
    assert "ollama pull" in dna_res.json()["detail"]

    # Retry with a working backend.
    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: StubAnalysis())
    retry = client.post(f"/api/projects/{project_id}/analyze")
    assert retry.status_code == 200

    recovered = client.get(f"/api/projects/{project_id}").json()
    assert recovered["status"] == "analyzed"
    assert recovered["error_message"] is None
    assert recovered["content_dna"]["primary_topic"] == "Repurposing video content"


def test_stored_dna_is_valid_json_in_sqlite(client, sample_video, monkeypatch, db_sessionmaker):
    from app.models.project import Project

    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: StubAnalysis())
    project_id = _transcribed_project(client, sample_video, monkeypatch)
    client.post(f"/api/projects/{project_id}/analyze")

    db = db_sessionmaker()
    try:
        project = db.get(Project, project_id)
        raw = json.loads(project.content_dna_json)
        assert raw["audience"] == "Content creators"
        assert isinstance(raw["key_moments"], list)
    finally:
        db.close()
