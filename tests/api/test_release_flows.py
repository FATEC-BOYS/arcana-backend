import json
import xml.etree.ElementTree as ET

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.providers.openai_provider import ProviderFailure
from app.core.config import get_settings
from app.db.models import GenerationRun, Job
from app.db.session import get_engine
from app.jobs.worker import process_one
from scripts.doctor import inspect_system
from scripts.evaluate import evaluate
from tests.support import FakeProvider, create_reading


def test_delete_does_not_reset_usage(client, auth, monkeypatch):
    monkeypatch.setenv("DAILY_READING_LIMIT", "1")
    get_settings.cache_clear()
    reading = create_reading(client, auth)
    assert client.delete("/api/v1/readings/" + reading["id"], headers=auth).status_code == 204
    response = client.post(
        "/api/v1/readings",
        headers={**auth, "Idempotency-Key": "release-reading-2"},
        json={"question": "Outra pergunta sobre trabalho?"},
    )
    assert response.status_code == 429
    assert client.get("/api/v1/me/usage", headers=auth).json()["quotas"]["reading"]["used"] == 1
    assert client.get("/api/v1/readings/" + reading["id"], headers=auth).status_code == 404


def test_duplicate_request_uses_single_quota(client, auth):
    first = create_reading(client, auth)
    second = create_reading(client, auth)
    assert first["id"] == second["id"]
    assert client.get("/api/v1/me/usage", headers=auth).json()["quotas"]["reading"]["used"] == 1


def test_failed_message_retry_and_audit(client, auth):
    reading = create_reading(client, auth)
    process_one(FakeProvider)
    path = "/api/v1/readings/" + reading["id"] + "/messages"
    result = client.post(
        path,
        headers={**auth, "Idempotency-Key": "release-message-1"},
        json={"question": "Pode explicar melhor?"},
    )
    assert result.status_code == 202, result.text
    message = result.json()
    assert message["sequence"] == 1
    process_one()
    assert (
        client.get(path + "/" + message["id"], headers=auth).json()["error_code"]
        == "llm_not_configured"
    )
    assert client.post(path + "/" + message["id"] + "/retry", headers=auth).status_code == 202
    process_one(FakeProvider)
    assert client.get(path + "/" + message["id"], headers=auth).json()["status"] == "completed"
    with Session(get_engine()) as db:
        runs = list(
            db.scalars(select(GenerationRun).where(GenerationRun.message_id == message["id"]))
        )
        assert len(runs) == 2
        assert {x.status for x in runs} == {"failed", "completed"}
    assert (
        client.post(
            path,
            headers={**auth, "Idempotency-Key": "release-message-2"},
            json={"question": "    x    "},
        ).status_code
        == 422
    )


def test_transient_failure_is_scheduled_without_new_draw(client, auth):
    class Unavailable(FakeProvider):
        def structured(self, **kwargs):
            self.calls += 1
            raise ProviderFailure("provider_temporarily_unavailable", retryable=True)

    reading = create_reading(client, auth)
    assert process_one(Unavailable)
    result = client.get("/api/v1/readings/" + reading["id"], headers=auth).json()
    assert result["status"] == "pending"
    assert result["facts"] == reading["facts"]
    assert not process_one(FakeProvider)  # Backoff has not expired.
    with Session(get_engine()) as db:
        job = db.scalar(select(Job).where(Job.reading_id == reading["id"]))
        job.available_at = 0
        db.commit()
    assert process_one(FakeProvider)
    assert (
        client.get("/api/v1/readings/" + reading["id"], headers=auth).json()["status"]
        == "completed"
    )
    assert client.get("/api/v1/me/usage", headers=auth).json()["quotas"]["reading"]["used"] == 1


def test_transient_retry_budget_is_bounded(client, auth):
    class Unavailable(FakeProvider):
        def structured(self, **kwargs):
            raise ProviderFailure("provider_rate_limited", retryable=True)

    reading = create_reading(client, auth)
    for _ in range(3):
        with Session(get_engine()) as db:
            job = db.scalar(select(Job).where(Job.reading_id == reading["id"]))
            job.available_at = 0
            db.commit()
        assert process_one(Unavailable)
    assert not process_one(Unavailable)
    assert (
        client.get("/api/v1/readings/" + reading["id"], headers=auth).json()["status"] == "failed"
    )


def test_unknown_time_omits_unreliable_chart_elements(client, auth):
    chart = client.post(
        "/api/v1/astrology/charts",
        headers=auth,
        json={
            "birth_date": "1990-07-15",
            "latitude": -23.5,
            "longitude": -46.6,
            "timezone": "America/Sao_Paulo",
        },
    )
    assert chart.status_code == 201, chart.text
    data = chart.json()["data"]
    assert not data["birth_time_known"]
    assert data["houses"] == {} and data["ascendant"] is None and data["aspects"] == []
    assert data["planets"]["moon"]["house"] is None
    assert data["planets"]["moon"]["approximate"]
    assert (
        client.get(
            "/api/v1/astrology/charts/" + chart.json()["id"] + "/svg", headers=auth
        ).status_code
        == 409
    )
    reading = create_reading(client, auth, kind="astrology", chart_id=chart.json()["id"])

    class Capture(FakeProvider):
        def structured(self, **kwargs):
            payload = json.loads(kwargs["payload"])
            assert payload["facts"]["birth_time_known"] is False
            assert payload["facts"]["houses"] == {}
            return super().structured(**kwargs)

    process_one(Capture)
    assert (
        client.get("/api/v1/readings/" + reading["id"], headers=auth).json()["status"]
        == "completed"
    )


def test_svg_journal_and_chart_deletion(client, auth):
    response = client.post(
        "/api/v1/astrology/charts",
        headers=auth,
        json={
            "birth_date": "1990-07-15",
            "birth_time": "10:30",
            "latitude": -23.5,
            "longitude": -46.6,
            "timezone": "America/Sao_Paulo",
        },
    )
    assert response.status_code == 201, response.text
    chart = response.json()
    base = "/api/v1/astrology/charts/" + chart["id"]
    svg = client.get(base + "/svg", headers=auth)
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
    assert ET.fromstring(svg.text).tag.endswith("svg")
    assert "sandbox" in svg.headers["content-security-policy"]
    reading = create_reading(client, auth, kind="astrology", chart_id=chart["id"])
    assert "svg" not in reading["facts"]["chart"]
    assert client.delete(base, headers=auth).status_code == 409
    journal = "/api/v1/journal/" + reading["id"]
    assert client.put(journal, headers=auth, json={"note": "Uma nota"}).status_code == 200
    assert client.get(journal, headers=auth).json()["note"] == "Uma nota"
    assert client.delete(journal, headers=auth).status_code == 204
    assert client.get(journal, headers=auth).status_code == 404
    assert client.delete("/api/v1/readings/" + reading["id"], headers=auth).status_code == 204
    assert client.delete(base, headers=auth).status_code == 204


def test_replayed_events_and_readiness(client, auth):
    reading = create_reading(client, auth)
    process_one(FakeProvider)
    path = "/api/v1/readings/" + reading["id"] + "/events"
    events = client.get(path, headers=auth).text
    cursor = max(int(line[4:]) for line in events.splitlines() if line.startswith("id: "))
    assert "event: completed" in events
    assert "id: " not in client.get(path, headers={**auth, "Last-Event-ID": str(cursor)}).text
    capabilities = client.get("/api/v1/capabilities").json()
    assert capabilities["unknown_birth_time"] and not capabilities["ai_configured"]
    report = inspect_system()
    assert report["database"] == "ready" and report["active_chunks"] >= 215
    assert not report["generation_ready"]
    with Session(get_engine()) as db:
        assert all(case["retrieval_coverage"] for case in evaluate(db)["cases"])


def test_history_deletion_is_owner_scoped(client, auth):
    reading = create_reading(client, auth)
    token = client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "name": "Other", "password": "another-long-password"},
    ).json()["access_token"]
    assert (
        client.delete(
            "/api/v1/readings/" + reading["id"], headers={"Authorization": "Bearer " + token}
        ).status_code
        == 404
    )
    assert client.get("/api/v1/readings/" + reading["id"], headers=auth).status_code == 200


def test_manual_and_automatic_retries_share_budget(client, auth):
    class Unavailable(FakeProvider):
        def structured(self, **kwargs):
            raise ProviderFailure("provider_rate_limited", retryable=True)

    reading = create_reading(client, auth)
    process_one()  # Missing configuration: first attempt fails without automatic retry.
    path = "/api/v1/readings/" + reading["id"]
    assert client.post(path + "/retry", headers=auth).status_code == 202
    for _ in range(2):
        with Session(get_engine()) as db:
            for job in db.scalars(select(Job).where(Job.reading_id == reading["id"])):
                job.available_at = 0
            db.commit()
        assert process_one(Unavailable)
    assert not process_one(Unavailable)
    assert client.get(path, headers=auth).json()["status"] == "failed"
    assert client.post(path + "/retry", headers=auth).status_code == 429
