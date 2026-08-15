import json

from app.services import pipeline_service
from app.services.analysis_service import AnalysisError
from tests.test_campaign_endpoint import StubAnalysis, _analyzed_project
from tests.test_evaluation_service import GOOD


class StubWithEvaluation(StubAnalysis):
    """Campaign stub that also answers the evaluation prompt."""

    def __init__(self, evaluation_payload=None, evaluation_fails=False, **kw):
        super().__init__(**kw)
        self.evaluation_payload = evaluation_payload if evaluation_payload is not None else GOOD
        self.evaluation_fails = evaluation_fails
        self.evaluation_calls = 0

    def complete_json(self, prompt, system=None):
        if "Evaluate this generated social media campaign" in prompt:
            self.evaluation_calls += 1
            if self.evaluation_fails:
                raise AnalysisError("evaluator unavailable")
            return self.evaluation_payload
        return super().complete_json(prompt, system)


def test_evaluation_runs_with_campaign_generation(client, long_sample_video, monkeypatch):
    stub = StubWithEvaluation()
    project_id = _analyzed_project(client, long_sample_video, monkeypatch, stub)
    client.post(f"/api/projects/{project_id}/campaign")

    assert stub.evaluation_calls == 1

    body = client.get(f"/api/projects/{project_id}/evaluation").json()
    ev = body["evaluation"]
    assert ev is not None
    assert 0 < ev["overall"] <= 100
    assert ev["platform_adaptation"] == 91
    assert len(ev["improvements"]) == 3
    # The deterministic completeness score is kept alongside the quality score.
    assert body["completeness_score"] > 0


def test_evaluation_exposed_on_project_detail(client, long_sample_video, monkeypatch):
    project_id = _analyzed_project(
        client, long_sample_video, monkeypatch, StubWithEvaluation()
    )
    client.post(f"/api/projects/{project_id}/campaign")

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["campaign_evaluation"]["overall"] > 0
    assert detail["campaign_evaluation"]["summary"]


def test_evaluator_failure_does_not_block_campaign(client, long_sample_video, monkeypatch):
    """The hard requirement: scoring must never prevent campaign generation."""
    stub = StubWithEvaluation(evaluation_fails=True)
    project_id = _analyzed_project(client, long_sample_video, monkeypatch, stub)

    res = client.post(f"/api/projects/{project_id}/campaign")
    assert res.status_code == 200

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["status"] == "completed"
    assert detail["error_message"] is None
    assert detail["platform_content"] is not None
    assert detail["campaign_score"] > 0        # completeness score still computed
    assert detail["campaign_evaluation"] is None  # quality score simply absent

    # And the campaign itself is fully retrievable.
    campaign = client.get(f"/api/projects/{project_id}/campaign").json()["campaign"]
    assert campaign["youtube"] is not None


def test_evaluation_absent_is_not_an_error(client, long_sample_video, monkeypatch):
    stub = StubWithEvaluation(evaluation_fails=True)
    project_id = _analyzed_project(client, long_sample_video, monkeypatch, stub)
    client.post(f"/api/projects/{project_id}/campaign")

    res = client.get(f"/api/projects/{project_id}/evaluation")
    assert res.status_code == 200
    assert res.json()["evaluation"] is None
    assert res.json()["completeness_score"] > 0


def test_reevaluate_endpoint(client, long_sample_video, monkeypatch):
    stub = StubWithEvaluation()
    project_id = _analyzed_project(client, long_sample_video, monkeypatch, stub)
    client.post(f"/api/projects/{project_id}/campaign")

    stub.evaluation_payload = {**GOOD, "seo": 99, "summary": "Re-scored."}
    res = client.post(f"/api/projects/{project_id}/evaluate")
    assert res.status_code == 200

    ev = client.get(f"/api/projects/{project_id}/evaluation").json()["evaluation"]
    assert ev["seo"] == 99
    assert ev["summary"] == "Re-scored."


def test_reevaluate_never_mutates_the_campaign(client, long_sample_video, monkeypatch):
    stub = StubWithEvaluation()
    project_id = _analyzed_project(client, long_sample_video, monkeypatch, stub)
    client.post(f"/api/projects/{project_id}/campaign")
    before = client.get(f"/api/projects/{project_id}/campaign").json()["campaign"]

    client.post(f"/api/projects/{project_id}/evaluate")
    after = client.get(f"/api/projects/{project_id}/campaign").json()["campaign"]
    assert after == before


def test_reevaluate_requires_a_campaign(client, long_sample_video, monkeypatch):
    project_id = _analyzed_project(
        client, long_sample_video, monkeypatch, StubWithEvaluation()
    )
    res = client.post(f"/api/projects/{project_id}/evaluate")
    assert res.status_code == 400
    assert "No campaign" in res.json()["detail"]


def test_evaluation_unknown_project(client):
    assert client.post("/api/projects/nope/evaluate").status_code == 404
    assert client.get("/api/projects/nope/evaluation").status_code == 404


def test_evaluation_persisted_to_sqlite(
    client, long_sample_video, monkeypatch, db_sessionmaker
):
    from app.models.project import Project

    project_id = _analyzed_project(
        client, long_sample_video, monkeypatch, StubWithEvaluation()
    )
    client.post(f"/api/projects/{project_id}/campaign")

    db = db_sessionmaker()
    try:
        stored = json.loads(db.get(Project, project_id).campaign_evaluation_json)
        assert stored["overall"] > 0
        assert stored["improvements"]
    finally:
        db.close()


def test_unexpected_evaluator_crash_does_not_lose_campaign(
    client, long_sample_video, monkeypatch
):
    """Not just EvaluationError: any exception from scoring must be contained."""

    class Exploding(StubWithEvaluation):
        def complete_json(self, prompt, system=None):
            if "Evaluate this generated social media campaign" in prompt:
                raise RuntimeError("evaluator exploded unexpectedly")
            return super().complete_json(prompt, system)

    project_id = _analyzed_project(client, long_sample_video, monkeypatch, Exploding())
    assert client.post(f"/api/projects/{project_id}/campaign").status_code == 200

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["status"] == "completed"
    assert detail["platform_content"] is not None
    assert detail["campaign_evaluation"] is None
