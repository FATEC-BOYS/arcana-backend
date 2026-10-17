from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Event, Reading, UsageBucket, now
from app.db.session import get_engine
from scripts.maintenance import cleanup
from tests.support import create_reading


def test_cleanup_dry_run_and_retention(client, auth):
    reading_id = create_reading(client, auth)["id"]
    with Session(get_engine()) as db:
        reading = db.get(Reading, reading_id)
        db.add(UsageBucket(user_id=reading.user_id, day=0, kind="reading", count=1))
        db.add(Event(reading_id=reading_id, name="old", data={}, created_at=now() - 31 * 86400))
        db.commit()
        report = cleanup(db)
        assert report["applied"] is False
        assert report["counts"]["usage_buckets"] == 1
        assert db.scalar(select(Event).where(Event.name == "old"))
        cleanup(db, apply=True)
        assert db.scalar(select(Event).where(Event.name == "old")) is None
        assert db.get(Reading, reading_id)
        assert db.scalar(select(UsageBucket).where(UsageBucket.day == 0)) is None
