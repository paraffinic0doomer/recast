import os
import subprocess
from collections.abc import Generator
from pathlib import Path

# The access-key gate is configured from the environment at import time, and a
# developer's .env may set one for a publicly exposed instance. Tests exercise
# the routes directly and must not depend on that, so clear it before anything
# imports the app. Environment variables win over .env in pydantic-settings.
os.environ["ACCESS_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app


ALLOWED_TEST_HOSTS = {
    "testserver",
    "localhost",
    "127.0.0.1",
    "::1",
    # faster-whisper revalidates its local model cache on load. Benign, and not
    # the class of call this guard exists to catch.
    "huggingface.co",
    "cdn-lfs.huggingface.co",
}


@pytest.fixture(autouse=True)
def _no_outbound_network(monkeypatch):
    """Fail loudly if a test reaches a real API.

    Services resolve their own backend via get_analysis_service(), so patching
    the wrong module silently produces a test that calls Groq/OpenAI for real:
    slow, flaky, billable, and asserting against whatever the model happened to
    say. Blocking outbound hosts turns that mistake into an obvious failure.
    """
    import httpx

    real_send = httpx.Client.send

    def guarded_send(self, request, *args, **kwargs):
        host = request.url.host
        if host and host not in ALLOWED_TEST_HOSTS:
            raise AssertionError(
                f"Test attempted a real network call to {host}{request.url.path}. "
                "Patch the service (e.g. pipeline_service.get_analysis_service) "
                "instead of letting it resolve a live LLM backend."
            )
        return real_send(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "send", guarded_send)


@pytest.fixture(autouse=True)
def _pool_follows_settings(monkeypatch):
    """Keep the Groq key pool derived from settings during tests.

    In production the pool reads backend/groq_keys.txt. Tests must not depend on
    (or consume) a developer's real keys, and existing tests simulate "no key"
    by blanking settings.groq_api_key -- so here the pool is rebuilt from
    settings on every call.
    """
    import app.core.config as config
    import app.services.analysis_service as analysis_service
    import app.services.transcription_service as transcription_service
    from app.core.key_pool import KeyPool

    def build() -> KeyPool:
        return KeyPool.from_sources(
            keys_csv=config.settings.groq_api_keys,
            single_key=config.settings.groq_api_key,
        )

    monkeypatch.setattr(config, "groq_key_pool", build)
    monkeypatch.setattr(analysis_service, "groq_key_pool", build)
    monkeypatch.setattr(transcription_service, "groq_key_pool", build)


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path, monkeypatch):
    """Keep test runs out of the real storage/ directory.

    Without this, every test upload/clip/thumbnail accumulates in the repo.
    """
    import app.services.clip_service as clip_service
    import app.services.media_service as media_service
    import app.services.subtitle_service as subtitle_service  # noqa: F401
    import app.services.thumbnail_service as thumbnail_service
    import app.services.upload_service as upload_service

    uploads = tmp_path / "uploads"
    audio = tmp_path / "audio"
    clips = tmp_path / "clips"
    thumbs = tmp_path / "thumbnails"
    subs = tmp_path / "subtitles"
    for d in (uploads, audio, clips, thumbs, subs):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(upload_service, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(media_service, "AUDIO_DIR", audio)
    monkeypatch.setattr(media_service, "CLIPS_DIR", clips)
    monkeypatch.setattr(clip_service, "CLIPS_DIR", clips)
    monkeypatch.setattr(clip_service, "THUMBNAILS_DIR", thumbs)
    monkeypatch.setattr(thumbnail_service, "THUMBNAILS_DIR", thumbs)
    monkeypatch.setattr(clip_service, "SUBTITLES_DIR", subs)
    yield {
        "uploads": uploads,
        "audio": audio,
        "clips": clips,
        "thumbnails": thumbs,
        "subtitles": subs,
    }


@pytest.fixture()
def storage_dirs(_isolated_storage):
    """The temp storage directories used for the current test."""
    return _isolated_storage


@pytest.fixture()
def db_sessionmaker(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestSessionLocal


@pytest.fixture()
def client(db_sessionmaker, monkeypatch) -> Generator[TestClient, None, None]:
    def override_get_db():
        db = db_sessionmaker()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # The pipeline runs as a background task with its own session, independent of
    # the get_db dependency — point it at the same isolated test database.
    import app.services.pipeline_service as pipeline_service

    monkeypatch.setattr(pipeline_service, "SessionLocal", db_sessionmaker)

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def speech_video() -> Path:
    """A short real video containing actual spoken words, for true transcription tests."""
    asset = Path(__file__).parent / "assets" / "speech.mp4"
    if not asset.exists():
        pytest.skip("speech test asset missing")
    return asset


@pytest.fixture(scope="session")
def long_sample_video(tmp_path_factory) -> Path:
    """A 60s clip, long enough for realistic short-form moment windows."""
    out_path = tmp_path_factory.mktemp("long_video") / "long.mp4"
    subprocess.run(
        [
            settings.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=60:size=320x240:rate=25",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(out_path),
        ],
        check=True, capture_output=True,
    )
    return out_path


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory) -> Path:
    """Generate a real 2s test clip (video + tone) with ffmpeg for genuine media tests."""
    out_dir = tmp_path_factory.mktemp("sample_video")
    out_path = out_dir / "sample.mp4"
    subprocess.run(
        [
            settings.ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=320x240:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    return out_path
