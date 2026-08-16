import json

from app.services import pipeline_service
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
        "reason": "Self-contained problem statement.",
        "scores": {
            "hook_strength": score,
            "information_value": score,
            "standalone_quality": score,
            "emotional_interest": score,
        },
    }


class StubAnalysis:
    def __init__(self, payload=None):
        # ids 0 and 5 are (0-19s) and (19-40s): adjacent, non-overlapping, so both
        # survive suppression and we get two clips to work with.
        self.payload = payload or {"moments": [_entry(0), _entry(5, score=70, title="Second")]}

    def complete_json(self, prompt, system=None):
        return self.payload

    def analyze(self, transcript_text, segments=None, max_timestamp=None):
        from app.schemas.content_dna import ContentDNA

        return ContentDNA.model_validate({"primary_topic": "Repurposing"})


def _project_with_moments(client, video, monkeypatch):
    monkeypatch.setattr(pipeline_service, "get_transcription_service", lambda: StubTranscription())
    monkeypatch.setattr(pipeline_service, "get_analysis_service", lambda: StubAnalysis())
    project = client.post("/api/projects", json={"title": "Clips"}).json()
    with video.open("rb") as f:
        client.post(
            "/api/upload",
            data={"project_id": project["id"]},
            files={"video": ("v.mp4", f, "video/mp4")},
        )
    client.post(f"/api/projects/{project['id']}/process")
    client.post(f"/api/projects/{project['id']}/moments")
    return project["id"]


def test_moments_have_stable_ids(client, long_sample_video, monkeypatch):
    project_id = _project_with_moments(client, long_sample_video, monkeypatch)
    moments = client.get(f"/api/projects/{project_id}/moments").json()["moments"]
    ids = [m["id"] for m in moments]
    assert ids == [f"m{i}" for i in range(1, len(ids) + 1)]


def test_create_clip_returns_required_fields(client, long_sample_video, monkeypatch):
    project_id = _project_with_moments(client, long_sample_video, monkeypatch)

    res = client.post(f"/api/projects/{project_id}/clips", json={"moment_id": "m1"})
    assert res.status_code == 201, res.text
    body = res.json()

    # The three fields the API contract promises.
    assert body["clip_id"]
    assert body["video_url"].startswith("/media/clips/")
    assert body["thumbnail_url"].startswith("/media/thumbnails/")

    assert body["moment_id"] == "m1"
    assert body["duration"] > 0
    assert body["width"] > 0 and body["height"] > 0


def test_created_clip_files_actually_exist(client, long_sample_video, monkeypatch, storage_dirs):
    """These must be real files on disk, not placeholders."""
    project_id = _project_with_moments(client, long_sample_video, monkeypatch)
    body = client.post(
        f"/api/projects/{project_id}/clips", json={"moment_id": "m1"}
    ).json()

    video = storage_dirs["clips"] / body["video_url"].rsplit("/", 1)[-1]
    thumb = storage_dirs["thumbnails"] / body["thumbnail_url"].rsplit("/", 1)[-1]

    assert video.exists() and video.stat().st_size > 10_000
    assert thumb.exists() and thumb.stat().st_size > 1_000

    from app.services.media_service import extract_metadata

    meta = extract_metadata(video)
    assert abs(meta.duration_seconds - body["duration"]) < 1.0
    assert (meta.width, meta.height) == (body["width"], body["height"])


def test_clip_is_vertical_from_landscape_source(client, long_sample_video, monkeypatch):
    project_id = _project_with_moments(client, long_sample_video, monkeypatch)
    body = client.post(
        f"/api/projects/{project_id}/clips", json={"moment_id": "m1"}
    ).json()
    assert (body["width"], body["height"]) == (1080, 1920)
    assert body["vertical"] is True


def test_clip_carries_moment_metadata(client, long_sample_video, monkeypatch):
    project_id = _project_with_moments(client, long_sample_video, monkeypatch)
    moments = client.get(f"/api/projects/{project_id}/moments").json()["moments"]
    body = client.post(
        f"/api/projects/{project_id}/clips", json={"moment_id": "m1"}
    ).json()
    assert body["title"] == moments[0]["title"]
    assert body["hook"] == moments[0]["hook"]
    assert body["score"] == moments[0]["score"]


def test_unknown_moment_id_rejected(client, long_sample_video, monkeypatch):
    project_id = _project_with_moments(client, long_sample_video, monkeypatch)
    res = client.post(f"/api/projects/{project_id}/clips", json={"moment_id": "nope"})
    assert res.status_code == 404
    assert "m1" in res.json()["detail"]  # tells the caller what is available


def test_clips_require_detected_moments(client, long_sample_video, monkeypatch):
    monkeypatch.setattr(pipeline_service, "get_transcription_service", lambda: StubTranscription())
    project = client.post("/api/projects", json={"title": "No moments"}).json()
    with long_sample_video.open("rb") as f:
        client.post(
            "/api/upload",
            data={"project_id": project["id"]},
            files={"video": ("v.mp4", f, "video/mp4")},
        )
    res = client.post(f"/api/projects/{project['id']}/clips", json={"moment_id": "m1"})
    assert res.status_code == 400


def test_clips_unknown_project(client):
    assert (
        client.post("/api/projects/nope/clips", json={"moment_id": "m1"}).status_code == 404
    )
    assert client.get("/api/projects/nope/clips").status_code == 404


def test_list_clips_and_persistence(client, long_sample_video, monkeypatch, db_sessionmaker):
    from app.models.project import Project

    project_id = _project_with_moments(client, long_sample_video, monkeypatch)
    assert client.get(f"/api/projects/{project_id}/clips").json()["clips"] == []

    client.post(f"/api/projects/{project_id}/clips", json={"moment_id": "m1"})
    client.post(f"/api/projects/{project_id}/clips", json={"moment_id": "m2"})

    listed = client.get(f"/api/projects/{project_id}/clips").json()["clips"]
    assert [c["moment_id"] for c in listed] == ["m1", "m2"]

    db = db_sessionmaker()
    try:
        stored = json.loads(db.get(Project, project_id).clips_json)
        assert len(stored) == 2
    finally:
        db.close()


def test_regenerating_same_moment_replaces_not_duplicates(
    client, long_sample_video, monkeypatch
):
    project_id = _project_with_moments(client, long_sample_video, monkeypatch)
    client.post(f"/api/projects/{project_id}/clips", json={"moment_id": "m1"})
    client.post(f"/api/projects/{project_id}/clips", json={"moment_id": "m1"})

    clips = client.get(f"/api/projects/{project_id}/clips").json()["clips"]
    assert len(clips) == 1


def test_download_serves_attachment(client, long_sample_video, monkeypatch):
    """<a download> is ignored cross-origin, so the server must force the save."""
    project_id = _project_with_moments(client, long_sample_video, monkeypatch)
    clip = client.post(
        f"/api/projects/{project_id}/clips", json={"moment_id": "m1"}
    ).json()

    res = client.get(f"/api/projects/{project_id}/clips/{clip['clip_id']}/download")
    assert res.status_code == 200
    assert res.headers["content-type"] == "video/mp4"
    disposition = res.headers["content-disposition"]
    assert disposition.startswith("attachment")
    assert ".mp4" in disposition
    assert len(res.content) > 10_000


def test_download_unknown_clip_404(client, long_sample_video, monkeypatch):
    project_id = _project_with_moments(client, long_sample_video, monkeypatch)
    assert (
        client.get(f"/api/projects/{project_id}/clips/nope/download").status_code == 404
    )


def test_download_missing_file_reports_clearly(
    client, long_sample_video, monkeypatch, storage_dirs
):
    project_id = _project_with_moments(client, long_sample_video, monkeypatch)
    clip = client.post(
        f"/api/projects/{project_id}/clips", json={"moment_id": "m1"}
    ).json()

    # Simulate the file being cleaned up while the DB record survives.
    (storage_dirs["clips"] / f"{clip['clip_id']}.mp4").unlink()

    res = client.get(f"/api/projects/{project_id}/clips/{clip['clip_id']}/download")
    assert res.status_code == 404
    assert "regenerate" in res.json()["detail"].lower()


def test_concurrent_render_does_not_overwrite_other_clips(
    client, long_sample_video, monkeypatch, db_sessionmaker
):
    """Rendering takes seconds; a clip saved during that window must survive.

    Regression: the handler merged into a project row loaded *before* the
    render, so a clip committed meanwhile was silently dropped.
    """
    import app.api.projects as projects_api
    from app.models.project import Project

    project_id = _project_with_moments(client, long_sample_video, monkeypatch)

    real_generate = projects_api.generate_clip
    state = {"injected": False}

    def slow_generate(video_path, start, end, clip_id, **kw):
        result = real_generate(video_path, start, end, clip_id, **kw)
        # Simulate another request committing a clip mid-render.
        if not state["injected"]:
            state["injected"] = True
            other = db_sessionmaker()
            try:
                row = other.get(Project, project_id)
                row.clips_json = json.dumps(
                    [
                        {
                            "clip_id": "other", "moment_id": "m2",
                            "video_url": "/media/clips/other.mp4",
                            "thumbnail_url": "/media/thumbnails/other.jpg",
                            "title": "Other", "hook": "", "score": 50,
                            "start": 0.0, "end": 5.0, "duration": 5.0,
                            "width": 1080, "height": 1920, "vertical": True,
                        }
                    ]
                )
                other.commit()
            finally:
                other.close()
        return result

    monkeypatch.setattr(projects_api, "generate_clip", slow_generate)

    client.post(f"/api/projects/{project_id}/clips", json={"moment_id": "m1"})

    clips = client.get(f"/api/projects/{project_id}/clips").json()["clips"]
    moment_ids = sorted(c["moment_id"] for c in clips)
    assert moment_ids == ["m1", "m2"], f"a clip was lost: {moment_ids}"
