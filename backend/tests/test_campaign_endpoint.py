import json

from app.schemas.content_dna import ContentDNA
from app.services import pipeline_service
from app.services.transcription_service import TranscriptResult, TranscriptSegment
from tests.test_platform_service import StubService

SEGMENTS = [
    TranscriptSegment(start=0.0, end=8.0, text="Welcome back to the channel."),
    TranscriptSegment(start=8.0, end=19.0, text="Most creators waste hours repurposing."),
    TranscriptSegment(start=19.0, end=29.0, text="What if one upload did everything?"),
    TranscriptSegment(start=29.0, end=40.0, text="Our tool finds the best moments."),
]

DNA_PAYLOAD = {
    "primary_topic": "Repurposing video content",
    "audience": "Content creators",
    "tone": "Educational",
    "content_type": "Tutorial",
    "core_message": "One video can become a whole campaign.",
    "key_points": ["Manual repurposing wastes hours", "Wrong moments get clipped"],
    "keywords": ["repurposing", "shorts", "automation"],
    "hooks": ["Nobody wants to watch you say hello"],
    "cta": "Subscribe for more",
    "key_moments": [
        {"timestamp": 0.0, "title": "Intro"},
        {"timestamp": 19.0, "title": "The question"},
        {"timestamp": 29.0, "title": "The tool"},
    ],
}


class StubTranscription:
    def transcribe(self, audio_path):
        return TranscriptResult(
            text=" ".join(s.text for s in SEGMENTS), language="en",
            duration=40.0, segments=SEGMENTS,
        )


class StubAnalysis(StubService):
    """Campaign stub that also serves analyze() and moment picking."""

    def analyze(self, transcript_text, segments=None, max_timestamp=None):
        return ContentDNA.model_validate(DNA_PAYLOAD)

    def complete_json(self, prompt, system=None):
        if "CANDIDATE WINDOWS" in prompt:
            return {
                "moments": [
                    {
                        "id": 0, "title": "Opening", "hook": "h", "reason": "r",
                        "scores": {"hook_strength": 90, "information_value": 90,
                                   "standalone_quality": 90, "emotional_interest": 90},
                    }
                ]
            }
        return super().complete_json(prompt, system)


def _analyzed_project(client, video, monkeypatch, service=None):
    service = service or StubAnalysis()
    monkeypatch.setattr(pipeline_service, "get_transcription_service", lambda: StubTranscription())
    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: service)
    project = client.post("/api/projects", json={"title": "Campaign"}).json()
    with video.open("rb") as f:
        client.post(
            "/api/upload",
            data={"project_id": project["id"]},
            files={"video": ("v.mp4", f, "video/mp4")},
        )
    client.post(f"/api/projects/{project['id']}/process")
    client.post(f"/api/projects/{project['id']}/analyze")
    client.post(f"/api/projects/{project['id']}/moments")
    return project["id"]


def test_campaign_requires_content_dna(client):
    project = client.post("/api/projects", json={"title": "Bare"}).json()
    res = client.post(f"/api/projects/{project['id']}/campaign")
    assert res.status_code == 400
    assert "Content DNA" in res.json()["detail"]


def test_campaign_unknown_project(client):
    assert client.post("/api/projects/nope/campaign").status_code == 404
    assert client.get("/api/projects/nope/campaign").status_code == 404


def test_campaign_404_before_generation(client, long_sample_video, monkeypatch):
    project_id = _analyzed_project(client, long_sample_video, monkeypatch)
    res = client.get(f"/api/projects/{project_id}/campaign")
    assert res.status_code == 404
    assert "not ready" in res.json()["detail"].lower()


def test_generate_full_campaign(client, long_sample_video, monkeypatch):
    project_id = _analyzed_project(client, long_sample_video, monkeypatch)

    res = client.post(f"/api/projects/{project_id}/campaign")
    assert res.status_code == 200

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["status"] == "completed"
    assert detail["error_message"] is None
    assert detail["campaign_score"] > 0

    body = client.get(f"/api/projects/{project_id}/campaign").json()
    campaign = body["campaign"]
    for platform in ("youtube", "instagram", "tiktok", "facebook", "linkedin", "x"):
        assert campaign[platform] is not None, platform

    assert len(campaign["youtube"]["titles"]) == 3
    assert campaign["instagram"]["reel_cover_text"]
    assert campaign["tiktok"]["hook"]
    assert campaign["x"]["post"]
    assert body["campaign_score"] > 0


def test_platform_outputs_are_not_the_same_text(client, long_sample_video, monkeypatch):
    """The whole point of the phase: six platforms, six different pieces of copy."""
    project_id = _analyzed_project(client, long_sample_video, monkeypatch)
    client.post(f"/api/projects/{project_id}/campaign")
    campaign = client.get(f"/api/projects/{project_id}/campaign").json()["campaign"]

    bodies = [
        campaign["youtube"]["description"],
        campaign["instagram"]["caption"],
        campaign["tiktok"]["caption"],
        campaign["facebook"]["caption"],
        campaign["linkedin"]["post"],
        campaign["x"]["post"],
    ]
    assert len(set(bodies)) == len(bodies)

    ctas = [
        campaign["instagram"]["cta"],
        campaign["tiktok"]["cta"],
        campaign["facebook"]["cta"],
        campaign["linkedin"]["cta"],
    ]
    assert len(set(ctas)) == len(ctas)


def test_x_post_respects_character_limit(client, long_sample_video, monkeypatch):
    stub = StubAnalysis()
    stub.payloads["X"] = {"post": "z" * 500, "thread": []}
    project_id = _analyzed_project(client, long_sample_video, monkeypatch, stub)
    client.post(f"/api/projects/{project_id}/campaign")

    campaign = client.get(f"/api/projects/{project_id}/campaign").json()["campaign"]
    assert len(campaign["x"]["post"]) <= 280


def test_regenerate_single_platform(client, long_sample_video, monkeypatch):
    stub = StubAnalysis()
    project_id = _analyzed_project(client, long_sample_video, monkeypatch, stub)
    client.post(f"/api/projects/{project_id}/campaign")

    before = client.get(f"/api/projects/{project_id}/campaign").json()["campaign"]
    stub.payloads["TikTok"] = {
        "hook": "completely new hook", "caption": "new", "hashtags": [], "cta": "new cta",
    }

    res = client.post(f"/api/projects/{project_id}/campaign?platform=tiktok")
    assert res.status_code == 200

    after = client.get(f"/api/projects/{project_id}/campaign").json()["campaign"]
    assert after["tiktok"]["hook"] == "completely new hook"
    assert after["youtube"] == before["youtube"]
    assert after["linkedin"] == before["linkedin"]


def test_unknown_platform_rejected(client, long_sample_video, monkeypatch):
    project_id = _analyzed_project(client, long_sample_video, monkeypatch)
    res = client.post(f"/api/projects/{project_id}/campaign?platform=myspace")
    assert res.status_code == 400
    assert "myspace" in res.json()["detail"]


def test_partial_failure_keeps_successful_platforms(client, long_sample_video, monkeypatch):
    stub = StubAnalysis(fail={"LinkedIn", "Facebook"})
    project_id = _analyzed_project(client, long_sample_video, monkeypatch, stub)
    client.post(f"/api/projects/{project_id}/campaign")

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["status"] == "completed"
    # The failure is surfaced rather than silently swallowed.
    assert "linkedin" in detail["error_message"]
    assert "facebook" in detail["error_message"]

    campaign = client.get(f"/api/projects/{project_id}/campaign").json()["campaign"]
    assert campaign["linkedin"] is None
    assert campaign["youtube"] is not None


def test_total_failure_marks_project_failed(client, long_sample_video, monkeypatch):
    stub = StubAnalysis(
        fail={"YouTube", "Instagram", "TikTok", "Facebook", "LinkedIn", "X"}
    )
    project_id = _analyzed_project(client, long_sample_video, monkeypatch, stub)
    client.post(f"/api/projects/{project_id}/campaign")

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["status"] == "failed"
    assert "every platform" in detail["error_message"]
    assert client.get(f"/api/projects/{project_id}/campaign").status_code == 409


def test_campaign_persisted_to_sqlite(client, long_sample_video, monkeypatch, db_sessionmaker):
    from app.models.project import Project

    project_id = _analyzed_project(client, long_sample_video, monkeypatch)
    client.post(f"/api/projects/{project_id}/campaign")

    db = db_sessionmaker()
    try:
        project = db.get(Project, project_id)
        stored = json.loads(project.platform_content_json)
        assert stored["youtube"]["titles"]
        assert project.campaign_score > 0
    finally:
        db.close()


def test_youtube_chapters_use_real_timestamps(client, long_sample_video, monkeypatch):
    project_id = _analyzed_project(client, long_sample_video, monkeypatch)
    client.post(f"/api/projects/{project_id}/campaign")

    campaign = client.get(f"/api/projects/{project_id}/campaign").json()["campaign"]
    chapters = campaign["youtube"]["chapters"]
    assert len(chapters) >= 3
    assert chapters[0]["timestamp"] == 0.0
    assert [c["timestamp"] for c in chapters] == sorted(c["timestamp"] for c in chapters)


def test_summary_counts_populated(client, long_sample_video, monkeypatch):
    """Dashboard cards rely on these counts, so they must reflect real content."""
    project_id = _analyzed_project(client, long_sample_video, monkeypatch)

    before = client.get(f"/api/projects/{project_id}").json()
    assert before["has_content_dna"] is True
    assert before["moment_count"] >= 1
    assert before["post_count"] == 0
    assert before["clip_count"] == 0

    client.post(f"/api/projects/{project_id}/campaign")
    moments = client.get(f"/api/projects/{project_id}/moments").json()["moments"]
    client.post(f"/api/projects/{project_id}/clips", json={"moment_id": moments[0]["id"]})

    after = client.get(f"/api/projects/{project_id}").json()
    assert after["post_count"] == 6
    assert after["clip_count"] == 1

    listed = client.get("/api/projects").json()
    row = next(p for p in listed if p["id"] == project_id)
    assert row["post_count"] == 6
    assert row["clip_count"] == 1
