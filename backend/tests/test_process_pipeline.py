import pytest

from app.services import pipeline_service
from app.services.transcription_service import TranscriptResult, TranscriptSegment


def _create_and_upload(client, sample_video):
    project = client.post("/api/projects", json={"title": "Pipeline Test"}).json()
    with sample_video.open("rb") as f:
        client.post(
            "/api/upload",
            data={"project_id": project["id"]},
            files={"video": ("sample.mp4", f, "video/mp4")},
        )
    return project["id"]


def test_process_requires_video(client):
    project = client.post("/api/projects", json={"title": "No video"}).json()
    res = client.post(f"/api/projects/{project['id']}/process")
    assert res.status_code == 400


def test_process_unknown_project(client):
    res = client.post("/api/projects/does-not-exist/process")
    assert res.status_code == 404


def test_process_without_any_backend_fails_clearly(client, sample_video, monkeypatch):
    """With no transcription backend at all, the run must fail honestly -- never fake success."""
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "auto")
    monkeypatch.setattr(ts.settings, "groq_api_key", "")
    monkeypatch.setattr(ts, "local_whisper_available", lambda: False)
    monkeypatch.setattr(ts.settings, "openai_api_key", "sk-your-key-here")

    project_id = _create_and_upload(client, sample_video)

    res = client.post(f"/api/projects/{project_id}/process")
    assert res.status_code == 200

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["status"] == "failed"
    assert "GROQ_API_KEY" in detail["error_message"]
    assert detail["transcript"] is None
    # Real ffmpeg stages should still have completed before the transcription step failed.
    assert detail["duration_seconds"] is not None
    assert detail["video_width"] == 320
    assert detail["video_height"] == 240


def test_process_succeeds_with_transcription_backend(client, sample_video, monkeypatch):
    fake_result = TranscriptResult(
        text="hello world",
        language="en",
        duration=2.0,
        segments=[TranscriptSegment(start=0.0, end=2.0, text="hello world")],
    )

    class FakeTranscriptionService:
        def transcribe(self, audio_path):
            assert audio_path.exists()
            return fake_result

    monkeypatch.setattr(
        pipeline_service, "get_transcription_service", lambda: FakeTranscriptionService()
    )

    project_id = _create_and_upload(client, sample_video)
    res = client.post(f"/api/projects/{project_id}/process")
    assert res.status_code == 200

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["status"] == "transcribed"
    assert detail["error_message"] is None
    assert detail["transcript"]["text"] == "hello world"
    assert detail["duration_seconds"] is not None
    assert detail["video_fps"] > 0


def test_process_rejects_when_already_active(client, sample_video, db_sessionmaker):
    from app.models.project import Project, ProjectStatus

    project_id = _create_and_upload(client, sample_video)

    # TestClient runs background tasks synchronously to completion, so we can't
    # overlap requests here; instead verify the guard directly against an
    # already-active status written to the same test database.
    db = db_sessionmaker()
    try:
        project = db.get(Project, project_id)
        project.status = ProjectStatus.TRANSCRIBING
        db.commit()
    finally:
        db.close()

    res = client.post(f"/api/projects/{project_id}/process")
    assert res.status_code == 409


def test_process_end_to_end_with_real_local_whisper(client, speech_video, monkeypatch):
    """Full real pipeline: ffprobe -> ffmpeg audio -> local Whisper. No mocks, no network."""
    pytest.importorskip("faster_whisper")
    import app.services.transcription_service as ts

    # Pin to local: with a GROQ_API_KEY present, "auto" would use the hosted API
    # and this test would stop covering the local backend at all.
    monkeypatch.setattr(ts.settings, "transcription_backend", "local")

    project = client.post("/api/projects", json={"title": "Real Speech"}).json()
    with speech_video.open("rb") as f:
        client.post(
            "/api/upload",
            data={"project_id": project["id"]},
            files={"video": ("speech.mp4", f, "video/mp4")},
        )

    res = client.post(f"/api/projects/{project['id']}/process")
    assert res.status_code == 200

    detail = client.get(f"/api/projects/{project['id']}").json()
    assert detail["status"] == "transcribed", detail["error_message"]

    transcript = detail["transcript"]
    assert "campaign" in transcript["text"].lower()
    assert transcript["language"] == "en"
    assert len(transcript["segments"]) >= 1
    # Timestamps are what later phases use to cut clips.
    assert transcript["segments"][0]["end"] > transcript["segments"][0]["start"]


def test_trailing_speech_is_not_dropped(client, speech_video, monkeypatch):
    """Regression: Whisper's condition_on_previous_text silently truncated the end
    of the audio, losing the final sentence — where CTAs usually live."""
    pytest.importorskip("faster_whisper")
    import app.services.transcription_service as ts

    monkeypatch.setattr(ts.settings, "transcription_backend", "local")

    project = client.post("/api/projects", json={"title": "Tail"}).json()
    with speech_video.open("rb") as f:
        client.post(
            "/api/upload",
            data={"project_id": project["id"]},
            files={"video": ("speech.mp4", f, "video/mp4")},
        )
    client.post(f"/api/projects/{project['id']}/process")

    detail = client.get(f"/api/projects/{project['id']}").json()
    assert detail["status"] == "transcribed", detail["error_message"]

    transcript = detail["transcript"]
    audio_duration = transcript["duration"] or 0.0
    last_end = transcript["segments"][-1]["end"]

    # The transcript must reach near the end of the audio, not stop early.
    assert last_end >= audio_duration - 3.0, (
        f"transcription stopped at {last_end:.1f}s but audio is {audio_duration:.1f}s "
        "— trailing speech was dropped"
    )
