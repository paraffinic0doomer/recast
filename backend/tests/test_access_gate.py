"""The shared-secret gate that makes a publicly exposed instance safe.

Without this, anyone who learns the tunnel URL can list every project,
download the source videos and the rendered clips, and start uploads that
spend the owner's API tokens.
"""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.access import AccessKeyMiddleware

KEY = "test-secret-key"


@pytest.fixture
def gated() -> TestClient:
    app = FastAPI()
    app.add_middleware(AccessKeyMiddleware, access_key=KEY)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://example.test"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/projects")
    def projects():
        return [{"id": "secret"}]

    @app.get("/media/clips/{name}")
    def clip(name: str):
        return {"file": name}

    return TestClient(app)


# --- refusal ----------------------------------------------------------------


def test_api_rejected_without_key(gated):
    assert gated.get("/api/projects").status_code == 401


def test_media_rejected_without_key(gated):
    """Clips and source videos are the whole point of the gate."""
    assert gated.get("/media/clips/x.mp4").status_code == 401


def test_wrong_key_rejected(gated):
    assert gated.get("/api/projects", headers={"X-Access-Key": "nope"}).status_code == 401


def test_empty_key_rejected(gated):
    assert gated.get("/api/projects", headers={"X-Access-Key": ""}).status_code == 401


def test_rejection_leaks_no_data(gated):
    body = gated.get("/api/projects").json()
    assert "secret" not in str(body)


# --- acceptance -------------------------------------------------------------


def test_header_accepted(gated):
    assert gated.get("/api/projects", headers={"X-Access-Key": KEY}).status_code == 200


def test_query_param_accepted_for_media(gated):
    """A <video src> cannot send headers, so media authenticates via ?k=."""
    assert gated.get(f"/media/clips/x.mp4?k={KEY}").status_code == 200


def test_health_stays_public(gated):
    """Liveness must work unauthenticated; it exposes no user content."""
    assert gated.get("/api/health").status_code == 200


def test_cors_preflight_allowed(gated):
    """Preflight carries no custom headers, so it must pass the gate."""
    res = gated.options(
        "/api/projects",
        headers={
            "Origin": "https://example.test",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-access-key",
        },
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "https://example.test"


def test_rejection_still_carries_cors_headers(gated):
    """Otherwise the browser reports an opaque failure instead of a 401."""
    res = gated.get("/api/projects", headers={"Origin": "https://example.test"})
    assert res.status_code == 401
    assert res.headers.get("access-control-allow-origin") == "https://example.test"


# --- disabled by default ----------------------------------------------------


def test_no_gate_when_key_unset():
    """Local development must be unaffected."""
    from app.main import app as real_app

    assert not any(
        m.cls is AccessKeyMiddleware for m in real_app.user_middleware
    ), "conftest clears ACCESS_KEY, so the gate must not be installed"
