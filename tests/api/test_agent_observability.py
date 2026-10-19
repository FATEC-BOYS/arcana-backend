import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GenerationRun
from app.db.session import get_engine
from app.jobs.worker import process_one
from scripts.observability import report
from tests.support import FakeProvider, create_reading


def test_trace_persisted_and_report_is_aggregated(client, auth):
    reading = create_reading(client, auth)
    assert process_one(FakeProvider)
    with Session(get_engine()) as db:
        run = db.scalar(select(GenerationRun).where(GenerationRun.reading_id == reading["id"]))
        assert run.status == "completed"
        assert [step["stage"] for step in run.trace["steps"]] == [
            "retrieval", "interpret", "review"
        ]
        assert run.trace["review_rejections"] == 0
        metrics = report(db, days=7)
    assert metrics["runs"] == 1
    assert metrics["completion_rate"] == 1
    assert metrics["stages"]["interpret"]["calls"] == 1
    assert metrics["stages"]["review"]["calls"] == 1
    assert "question" not in json.dumps(metrics)
    assert reading["id"] not in json.dumps(metrics)


def test_failure_is_reported_without_sensitive_text(client, auth):
    reading = create_reading(client, auth)
    assert process_one()  # No OpenAI key set by test fixture.
    with Session(get_engine()) as db:
        metrics = report(db, days=7)
        row = db.scalar(select(GenerationRun).where(GenerationRun.reading_id == reading["id"]))
        assert row.trace == {
            "steps": [], "review_outcomes": [], "interpret_attempts": 0,
            "review_rejections": 0
        }
    assert metrics["runs"] == 1
    assert metrics["statuses"] == {"failed": 1}
    assert metrics["errors"] == {"llm_not_configured": 1}
    assert metrics["completion_rate"] == 0
