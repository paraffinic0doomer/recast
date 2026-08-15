import json

from app.services import pipeline_service
from app.services.analysis_service import AnalysisError
from tests.test_campaign_endpoint import (
    DNA_PAYLOAD,
    StubAnalysis,
    StubTranscription,
    _analyzed_project,
)
from tests.test_thumbnail_service import _entry


class StubWithThumbnails(StubAnalysis):
    """Adds thumbnail concepts to the campaign/moment stub."""

    def __init__(self, thumbnail_payload=None, thumbnails_fail=False, **kw):
        super().__init__(**kw)
        self.thumbnails_fail = thumbnails_fail
        self.thumbnail_payload = thumbnail_payload or {
            "concepts": [
                _entry(0, "Stop Wasting Hours"),
                _entry(1, "The Real Mistake"),
                _entry(0, "One Video Full Campaign"),
            ]
        }

    def complete_json(self, prompt, system=None):
        if "AVAILABLE FRAMES" in prompt:
            if self.thumbnails_fail:
                raise AnalysisError("thumbnail backend unavailable")
            return self.thumbnail_payload
        return super().complete_json(prompt, system)


def test_thumbnails_requires_content_dna(client):
    project = client.post("/api/projects", json={"title": "Bare"}).json()
    res = client.post(f"/api/projects/{project['id']}/thumbnails")
    assert res.status_code == 400


def test_thumbnails_unknown_project(client):
    assert client.post("/api/projects/nope/thumbnails").status_code == 404
    assert client.get("/api/projects/nope/thumbnails").status_code == 404


def test_thumbnails_empty_before_generation(client, long_sample_video, monkeypatch):
    """Absent thumbnails are not an error -- they are an optional add-on."""
    project_id = _analyzed_project(
        client, long_sample_video, monkeypatch, StubWithThumbnails()
    )
    res = client.get(f"/api/projects/{project_id}/thumbnails")
    assert res.status_code == 200
    assert res.json()["concepts"] == []
    assert res.json()["image_generation_available"] is False


def test_generate_three_concepts(client, long_sample_video, monkeypatch, storage_dirs):
    project_id = _analyzed_project(
        client, long_sample_video, monkeypatch, StubWithThumbnails()
    )
    assert client.post(f"/api/projects/{project_id}/thumbnails").status_code == 200

    body = client.get(f"/api/projects/{project_id}/thumbnails").json()
    concepts = body["concepts"]
    assert len(concepts) == 3

    for concept in concepts:
        assert concept["headline"]
        assert concept["visual_concept"]
        assert concept["subject_placement"]
        assert concept["emotional_angle"]
        assert concept["why_it_works"]
        assert concept["recommended_use_case"]
        assert concept["timestamp"] is not None
        # Preview is a real extracted frame, not a placeholder.
        assert concept["frame_url"].startswith("/media/thumbnails/")
        path = storage_dirs["thumbnails"] / concept["frame_url"].rsplit("/", 1)[-1]
        assert path.exists() and path.stat().st_size > 1000


def test_thumbnails_exposed_on_project_detail(client, long_sample_video, monkeypatch):
    project_id = _analyzed_project(
        client, long_sample_video, monkeypatch, StubWithThumbnails()
    )
    client.post(f"/api/projects/{project_id}/thumbnails")

    detail = client.get(f"/api/projects/{project_id}").json()
    assert len(detail["thumbnail_concepts"]) == 3


def test_thumbnail_failure_does_not_break_the_project(
    client, long_sample_video, monkeypatch
):
    """The whole point of 'do not let this phase break the rest of the app'."""
    stub = StubWithThumbnails(thumbnails_fail=True)
    project_id = _analyzed_project(client, long_sample_video, monkeypatch, stub)
    client.post(f"/api/projects/{project_id}/campaign")

    before = client.get(f"/api/projects/{project_id}").json()
    assert before["status"] == "completed"

    # Thumbnails blow up...
    assert client.post(f"/api/projects/{project_id}/thumbnails").status_code == 200

    after = client.get(f"/api/projects/{project_id}").json()
    # ...and the project is untouched: still completed, campaign intact.
    assert after["status"] == "completed"
    assert after["error_message"] is None
    assert after["platform_content"] is not None
    assert after["campaign_score"] == before["campaign_score"]
    assert after["thumbnail_concepts"] is None

    assert client.get(f"/api/projects/{project_id}/thumbnails").json()["concepts"] == []


def test_thumbnails_persisted_to_sqlite(
    client, long_sample_video, monkeypatch, db_sessionmaker
):
    from app.models.project import Project

    project_id = _analyzed_project(
        client, long_sample_video, monkeypatch, StubWithThumbnails()
    )
    client.post(f"/api/projects/{project_id}/thumbnails")

    db = db_sessionmaker()
    try:
        stored = json.loads(db.get(Project, project_id).thumbnail_concepts_json)
        assert len(stored) == 3
        assert stored[0]["recommended_use_case"]
    finally:
        db.close()


def test_regenerating_replaces_concepts(client, long_sample_video, monkeypatch):
    stub = StubWithThumbnails()
    project_id = _analyzed_project(client, long_sample_video, monkeypatch, stub)
    client.post(f"/api/projects/{project_id}/thumbnails")

    stub.thumbnail_payload = {"concepts": [_entry(0, "Brand New Angle")]}
    client.post(f"/api/projects/{project_id}/thumbnails")

    concepts = client.get(f"/api/projects/{project_id}/thumbnails").json()["concepts"]
    assert len(concepts) == 1
    assert concepts[0]["headline"] == "Brand New Angle"
