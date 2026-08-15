import pytest

from app.services import pipeline_service
from app.services.transcription_service import TranscriptResult, TranscriptSegment


def _upload(client, video, title="T"):
    project = client.post("/api/projects", json={"title": title}).json()
    with video.open("rb") as f:
        client.post(
            "/api/upload",
            data={"project_id": project["id"]},
            files={"video": ("v.mp4", f, "video/mp4")},
        )
    return project["id"]


def test_transcript_404_for_unknown_project(client):
    assert client.get("/api/projects/nope/transcript").status_code == 404


def test_transcript_404_when_not_yet_processed(client, sample_video):
    project_id = _upload(client, sample_video)
    res = client.get(f"/api/projects/{project_id}/transcript")
    assert res.status_code == 404
    assert "not ready" in res.json()["detail"].lower()


def test_transcript_409_after_failure_with_reason(client, sample_video, monkeypatch):
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "auto")
    monkeypatch.setattr(ts.settings, "groq_api_key", "")
    monkeypatch.setattr(ts, "local_whisper_available", lambda: False)
    monkeypatch.setattr(ts.settings, "openai_api_key", "sk-your-key-here")

    project_id = _upload(client, sample_video)
    client.post(f"/api/projects/{project_id}/process")

    res = client.get(f"/api/projects/{project_id}/transcript")
    assert res.status_code == 409
    assert "GROQ_API_KEY" in res.json()["detail"]


def test_transcript_returns_segments(client, sample_video, monkeypatch):
    class Stub:
        def transcribe(self, audio_path):
            return TranscriptResult(
                text="one two",
                language="en",
                duration=6.0,
                segments=[
                    TranscriptSegment(start=0.0, end=2.5, text="one"),
                    TranscriptSegment(start=2.5, end=6.0, text="two"),
                ],
            )

    monkeypatch.setattr(pipeline_service, "get_transcription_service", lambda: Stub())

    project_id = _upload(client, sample_video)
    client.post(f"/api/projects/{project_id}/process")

    res = client.get(f"/api/projects/{project_id}/transcript")
    assert res.status_code == 200
    body = res.json()
    assert body["project_id"] == project_id
    assert body["text"] == "one two"
    assert body["language"] == "en"
    assert len(body["segments"]) == 2
    assert body["segments"][1] == {"start": 2.5, "end": 6.0, "text": "two"}


def test_failed_project_is_preserved_and_retryable(client, sample_video, monkeypatch):
    """A failed run must keep the project + video, and a retry must be able to succeed."""
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "auto")
    monkeypatch.setattr(ts.settings, "groq_api_key", "")
    monkeypatch.setattr(ts, "local_whisper_available", lambda: False)
    monkeypatch.setattr(ts.settings, "openai_api_key", "sk-your-key-here")

    project_id = _upload(client, sample_video, title="Retry Me")
    client.post(f"/api/projects/{project_id}/process")

    failed = client.get(f"/api/projects/{project_id}").json()
    assert failed["status"] == "failed"
    assert failed["error_message"]
    # Project and its video survive the failure.
    assert failed["title"] == "Retry Me"
    assert failed["video_url"] is not None
    assert failed["duration_seconds"] is not None

    # Now a backend becomes available and the user retries.
    class Stub:
        def transcribe(self, audio_path):
            return TranscriptResult(
                text="recovered", language="en", duration=2.0,
                segments=[TranscriptSegment(start=0.0, end=2.0, text="recovered")],
            )

    monkeypatch.setattr(pipeline_service, "get_transcription_service", lambda: Stub())

    retry = client.post(f"/api/projects/{project_id}/process")
    assert retry.status_code == 200

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["status"] == "transcribed"
    assert detail["error_message"] is None
    assert detail["transcript"]["text"] == "recovered"
