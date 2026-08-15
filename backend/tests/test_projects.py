

def test_create_and_list_project(client):
    res = client.post("/api/projects", json={"title": "My Video"})
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "My Video"
    assert body["status"] == "pending"

    res = client.get("/api/projects")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_create_project_default_title(client):
    res = client.post("/api/projects", json={})
    assert res.status_code == 201
    assert res.json()["title"] == "Untitled Project"


def test_get_project_not_found(client):
    res = client.get("/api/projects/does-not-exist")
    assert res.status_code == 404


def test_upload_video_attaches_to_project(client, storage_dirs):
    project = client.post("/api/projects", json={"title": "Demo"}).json()

    video_path = None
    try:
        res = client.post(
            "/api/upload",
            data={"project_id": project["id"]},
            files={"video": ("demo.mp4", b"fake video bytes", "video/mp4")},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "uploaded"
        assert body["video_filename"] == "demo.mp4"
        assert body["video_url"] == f"/media/uploads/{project['id']}.mp4"

        detail = client.get(f"/api/projects/{project['id']}").json()
        assert detail["status"] == "uploaded"

        video_path = storage_dirs["uploads"] / f"{project['id']}.mp4"
        assert video_path.exists()
    finally:
        if video_path is not None:
            video_path.unlink(missing_ok=True)


def test_upload_rejects_bad_extension(client):
    project = client.post("/api/projects", json={"title": "Demo"}).json()
    res = client.post(
        "/api/upload",
        data={"project_id": project["id"]},
        files={"video": ("demo.txt", b"not a video", "text/plain")},
    )
    assert res.status_code == 400


def test_upload_unknown_project(client):
    res = client.post(
        "/api/upload",
        data={"project_id": "missing"},
        files={"video": ("demo.mp4", b"fake video bytes", "video/mp4")},
    )
    assert res.status_code == 404


def test_delete_project(client):
    project = client.post("/api/projects", json={"title": "Delete me"}).json()
    res = client.delete(f"/api/projects/{project['id']}")
    assert res.status_code == 204
    assert client.get(f"/api/projects/{project['id']}").status_code == 404
