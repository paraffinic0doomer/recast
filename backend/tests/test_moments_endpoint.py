import json

from app.services import pipeline_service
from app.services.analysis_service import AnalysisError
from app.services.transcription_service import TranscriptResult, TranscriptSegment

SEGMENTS = [
    TranscriptSegment(start=0.0, end=8.0, text="Welcome back to the channel."),
    TranscriptSegment(start=8.0, end=19.0, text="Most creators waste hours repurposing."),
    TranscriptSegment(start=19.0, end=29.0, text="What if one upload did everything?"),
    TranscriptSegment(start=29.0, end=40.0, text="Our tool finds the best moments."),
]


class StubTranscription:
    def transcribe(self, audio_path):
        return TranscriptResult(
            text=" ".join(s.text for s in SEGMENTS),
            language="en",
            duration=40.0,
            segments=SEGMENTS,
        )


def _entry(window_id, score=90, title="A strong moment"):
    return {
        "id": window_id,
        "title": title,
        "hook": "You are wasting hours every week.",
        "reason": "Self-contained problem statement with a clear payoff.",
        "scores": {
            "hook_strength": score,
            "information_value": score,
            "standalone_quality": score,
            "emotional_interest": score,
        },
    }


class StubAnalysis:
    """Returns Content DNA for analyze(), and moment picks for complete_json()."""

    def __init__(self, moments_payload=None):
        self.moments_payload = moments_payload or {"moments": [_entry(0)]}

    def complete_json(self, prompt, system=None):
        return self.moments_payload

    def analyze(self, transcript_text, segments=None, max_timestamp=None):
        from app.schemas.content_dna import ContentDNA

        return ContentDNA.model_validate(
            {"primary_topic": "Repurposing", "audience": "Creators", "tone": "Educational"}
        )


def _transcribed(client, video, monkeypatch):
    monkeypatch.setattr(pipeline_service, "get_transcription_service", lambda: StubTranscription())
    project = client.post("/api/projects", json={"title": "Moments"}).json()
    with video.open("rb") as f:
        client.post(
            "/api/upload",
            data={"project_id": project["id"]},
            files={"video": ("v.mp4", f, "video/mp4")},
        )
    client.post(f"/api/projects/{project['id']}/process")
    return project["id"]


def test_moments_requires_transcript(client):
    project = client.post("/api/projects", json={"title": "Bare"}).json()
    res = client.post(f"/api/projects/{project['id']}/moments")
    assert res.status_code == 400


def test_moments_unknown_project(client):
    assert client.post("/api/projects/nope/moments").status_code == 404
    assert client.get("/api/projects/nope/moments").status_code == 404


def test_moments_404_before_detection(client, long_sample_video, monkeypatch):
    project_id = _transcribed(client, long_sample_video, monkeypatch)
    res = client.get(f"/api/projects/{project_id}/moments")
    assert res.status_code == 404
    assert "not ready" in res.json()["detail"].lower()


def test_detect_and_fetch_moments(client, long_sample_video, monkeypatch):
    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: StubAnalysis())
    project_id = _transcribed(client, long_sample_video, monkeypatch)

    res = client.post(f"/api/projects/{project_id}/moments")
    assert res.status_code == 200

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["status"] == "moments_ready"
    assert detail["error_message"] is None

    body = client.get(f"/api/projects/{project_id}/moments").json()
    assert body["project_id"] == project_id
    assert len(body["moments"]) >= 1

    moment = body["moments"][0]
    assert moment["score"] == 90
    assert moment["scores"]["hook_strength"] == 90
    assert moment["title"] == "A strong moment"
    assert moment["end"] > moment["start"]


def test_moment_timestamps_match_real_transcript_segments(client, long_sample_video, monkeypatch):
    """The core Phase 5 guarantee: no invented timestamps."""
    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: StubAnalysis())
    project_id = _transcribed(client, long_sample_video, monkeypatch)
    client.post(f"/api/projects/{project_id}/moments")

    transcript = client.get(f"/api/projects/{project_id}/transcript").json()
    starts = {s["start"] for s in transcript["segments"]}
    ends = {s["end"] for s in transcript["segments"]}

    for moment in client.get(f"/api/projects/{project_id}/moments").json()["moments"]:
        assert moment["start"] in starts
        assert moment["end"] in ends


def test_moment_detection_failure_preserves_project_and_retries(
    client, long_sample_video, monkeypatch
):
    class Failing:
        def complete_json(self, prompt, system=None):
            raise AnalysisError("Analysis request failed: rate limited")

    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: Failing())
    project_id = _transcribed(client, long_sample_video, monkeypatch)
    client.post(f"/api/projects/{project_id}/moments")

    failed = client.get(f"/api/projects/{project_id}").json()
    assert failed["status"] == "failed"
    assert "rate limited" in failed["error_message"]
    assert failed["transcript"] is not None  # preserved for retry

    assert client.get(f"/api/projects/{project_id}/moments").status_code == 409

    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: StubAnalysis())
    assert client.post(f"/api/projects/{project_id}/moments").status_code == 200
    assert client.get(f"/api/projects/{project_id}").json()["status"] == "moments_ready"


def test_moments_persisted_to_sqlite(client, long_sample_video, monkeypatch, db_sessionmaker):
    from app.models.project import Project

    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: StubAnalysis())
    project_id = _transcribed(client, long_sample_video, monkeypatch)
    client.post(f"/api/projects/{project_id}/moments")

    db = db_sessionmaker()
    try:
        stored = json.loads(db.get(Project, project_id).best_moments_json)
        assert isinstance(stored, list) and stored
        assert "scores" in stored[0]
    finally:
        db.close()
