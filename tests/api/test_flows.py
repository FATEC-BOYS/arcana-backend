from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.schemas.state import Interpretation, Review
from app.db.models import AuthSession, Chunk, Event, Job, Mail, Reading, User
from app.db.session import get_engine
from app.jobs.worker import process_one


class FakeProvider:
    model = "test-double"
    input_tokens = output_tokens = calls = 0

    def structured(self, *, system, payload, schema):
        import json

        self.calls += 1
        data = json.loads(payload)
        if schema == Review:
            return Review(approved=True, feedback="")
        return Interpretation(
            summary="Uma leitura simbólica sustentada pelo acervo de teste.",
            reflections=["O que faz sentido para você?"],
            source_ids=[data["sources"][0]["source_id"]],
            fact_ids=[data["fact_ids"][0]],
        )


def create(client, auth, key="request-key-1", **extra):
    return client.post(
        "/api/v1/readings",
        headers={**auth, "Idempotency-Key": key},
        json={"question": "Como refletir sobre trabalho?", **extra},
    )


def test_auth_rotation_and_revocation(client, auth):
    assert client.get("/api/v1/me", headers=auth).status_code == 200
    assert client.get("/api/v1/me").status_code == 401
    login = client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": "a-long-test-password"}
    ).json()
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert refreshed.status_code == 200
    assert (
        client.get(
            "/api/v1/me", headers={"Authorization": "Bearer " + login["access_token"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
        ).status_code
        == 401
    )
    assert client.post("/api/v1/auth/logout", headers=auth).status_code == 204
    assert client.get("/api/v1/me", headers=auth).status_code == 401


def test_reading_idempotency_and_chat(client, auth):
    first = create(client, auth)
    assert first.status_code == 202, first.text
    first = first.json()
    assert len({x["card_id"] for x in first["facts"]["cards"]}) == 3
    assert create(client, auth).json()["id"] == first["id"]
    assert create(client, auth, spread="daily").status_code == 409
    assert process_one(FakeProvider)
    completed = client.get("/api/v1/readings/" + first["id"], headers=auth).json()
    assert completed["status"] == "completed"
    assert completed["facts"] == first["facts"]
    assert completed["result"]["sources"]
    path = f"/api/v1/readings/{first['id']}/messages"
    msg = client.post(
        path,
        headers={**auth, "Idempotency-Key": "message-key-1"},
        json={"question": "Pode explicar melhor?"},
    )
    assert msg.status_code == 202, msg.text
    assert process_one(FakeProvider)
    assert client.get(path, headers=auth).json()[0]["status"] == "completed"
    journal = client.put(
        "/api/v1/journal/" + first["id"],
        headers=auth,
        json={"note": "Minha reflexão", "favorite": True},
    )
    assert journal.status_code == 200
    assert len(client.get("/api/v1/journal?favorites_only=true", headers=auth).json()) == 1
    events = client.get(f"/api/v1/readings/{first['id']}/events", headers=auth)
    assert "event: completed" in events.text


def test_failure_and_retry_preserve_cards(client, auth):
    reading = create(client, auth).json()
    assert process_one()  # No API key; must fail explicitly, never fake a reading.
    failed = client.get("/api/v1/readings/" + reading["id"], headers=auth).json()
    assert failed["status"] == "failed"
    assert failed["error_code"] == "llm_not_configured"
    assert failed["facts"] == reading["facts"]
    retried = client.post(f"/api/v1/readings/{reading['id']}/retry", headers=auth)
    assert retried.status_code == 202
    assert process_one(FakeProvider)
    assert (
        client.get("/api/v1/readings/" + reading["id"], headers=auth).json()["facts"]
        == reading["facts"]
    )


def test_cross_account_and_cascade_deletion(client, auth):
    reading = create(client, auth).json()
    token = client.post(
        "/api/v1/auth/register",
        json={"email": "b@example.com", "name": "B", "password": "another-long-password"},
    ).json()["access_token"]
    other = {"Authorization": "Bearer " + token}
    for path in [
        f"/api/v1/readings/{reading['id']}",
        f"/api/v1/readings/{reading['id']}/messages",
        f"/api/v1/readings/{reading['id']}/events",
    ]:
        assert client.get(path, headers=other).status_code == 404
    assert (
        client.put(
            "/api/v1/journal/" + reading["id"], headers=other, json={"note": "no"}
        ).status_code
        == 404
    )
    assert client.delete("/api/v1/me", headers=auth).status_code == 204
    with Session(get_engine()) as db:
        assert db.get(Reading, reading["id"]) is None
        assert not list(db.scalars(select(Job)))
        assert not list(db.scalars(select(Event)))
        assert len(list(db.scalars(select(User)))) == 1
        assert len(list(db.scalars(select(AuthSession)))) == 1


def test_reviewer_rejects_invalid_citations(client, auth):
    class Bad(FakeProvider):
        def structured(self, **kwargs):
            value = super().structured(**kwargs)
            if isinstance(value, Interpretation):
                value.source_ids = ["invented"]
            return value

    reading = create(client, auth).json()
    process_one(Bad)
    result = client.get("/api/v1/readings/" + reading["id"], headers=auth).json()
    assert result["status"] == "failed"
    assert result["error_code"] == "invalid_citations"


def test_reviewer_correction_is_bounded(client, auth):
    class Reject(FakeProvider):
        def structured(self, **kwargs):
            if kwargs["schema"] == Review:
                self.calls += 1
                return Review(approved=False, feedback="Revisar a interpretação")
            return super().structured(**kwargs)

    reading = create(client, auth).json()
    provider = Reject()
    process_one(lambda: provider)
    assert provider.calls == 4  # Initial interpretation/review + one correction/review.
    result = client.get("/api/v1/readings/" + reading["id"], headers=auth).json()
    assert result["error_code"] == "review_rejected"


def test_empty_knowledge_is_not_fabricated(client, auth):
    reading = create(client, auth).json()
    with Session(get_engine()) as db:
        from sqlalchemy import delete

        db.execute(delete(Chunk))
        db.commit()
    process_one(FakeProvider)
    assert (
        client.get("/api/v1/readings/" + reading["id"], headers=auth).json()["status"] == "failed"
    )


def test_quota_and_validation(client, auth, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("DAILY_READING_LIMIT", "1")
    get_settings.cache_clear()
    assert create(client, auth).status_code == 202
    assert create(client, auth, key="request-key-2").status_code == 429
    assert create(client, auth).status_code == 202
    bad = client.post(
        "/api/v1/readings",
        headers={**auth, "Idempotency-Key": "request-key-3"},
        json={"question": "     "},
    )
    assert bad.status_code == 422
    assert "input" not in bad.json()["detail"][0]


def test_recovery_invalidates_sessions(client, auth, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from app.core.config import get_settings

    monkeypatch.setenv("SMTP_HOST", "smtp.invalid")
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.com")
    get_settings.cache_clear()
    assert (
        client.post("/api/v1/auth/forgot-password", json={"email": "a@example.com"}).status_code
        == 202
    )
    with Session(get_engine()) as db:
        mail = db.scalar(select(Mail))
        token = parse_qs(urlparse(mail.body.split()[-1]).fragment)["token"][0]
    assert (
        client.post(
            "/api/v1/auth/reset-password", json={"token": token, "password": "new-long-password"}
        ).status_code
        == 204
    )
    assert client.get("/api/v1/me", headers=auth).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/reset-password", json={"token": token, "password": "new-long-password"}
        ).status_code
        == 400
    )


def test_expired_worker_can_resume(client, auth):
    from app.jobs.worker import claim_job

    reading = create(client, auth).json()
    key, token = claim_job()
    with Session(get_engine()) as db:
        job = db.get(Job, key)
        job.lease_until = 0
        db.commit()
    assert process_one(FakeProvider)
    assert (
        client.get("/api/v1/readings/" + reading["id"], headers=auth).json()["status"]
        == "completed"
    )
