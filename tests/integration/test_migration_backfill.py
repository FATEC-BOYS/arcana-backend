"""Exercise the data migration against an actual disposable PostgreSQL database in CI."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import BirthChart, Chunk, KnowledgeDocument, Reading, UsageBucket
from app.db.session import get_engine


def test_upgrade_and_downgrade_preserve_legacy_data(client):
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        pytest.skip("Legacy migration runs against PostgreSQL in CI")
    Base.metadata.drop_all(engine)
    config = Config("alembic.ini")
    command.stamp(config, "base")
    command.upgrade(config, "0002_domain")
    metadata = MetaData()
    users = Table("users", metadata, autoload_with=engine)
    charts = Table("birth_charts", metadata, autoload_with=engine)
    readings = Table("readings", metadata, autoload_with=engine)
    chunks = Table("knowledge_chunks", metadata, autoload_with=engine)
    with engine.begin() as connection:
        connection.execute(
            users.insert().values(
                id="legacy-user",
                email="old@example.com",
                name="Old",
                password_hash="x",
                created_at=1,
            )
        )
        connection.execute(
            charts.insert().values(
                id="legacy-chart",
                user_id="legacy-user",
                birth_input={},
                data={"sun": "Can"},
                created_at=1,
            )
        )
        connection.execute(
            readings.insert().values(
                id="legacy-reading",
                user_id="legacy-user",
                kind="astrology",
                question="Question",
                facts={"chart_id": "legacy-chart", "chart": {"sun": "Can"}},
                idempotency_key="legacy-key",
                request_hash="a" * 64,
                status="completed",
                result={"summary": "Saved reading"},
                created_at=1,
            )
        )
        connection.execute(
            chunks.insert(),
            [
                dict(
                    id=f"old-{v}",
                    source="Old source",
                    version=v,
                    license="CC0",
                    topic="tarot",
                    tags=["major-00"],
                    content=f"Version {v}",
                    embedding=[1.0] + [0.0] * 1535,
                )
                for v in ("1", "2")
            ],
        )
    command.upgrade(config, "head")
    with Session(engine) as db:
        reading = db.get(Reading, "legacy-reading")
        assert reading.chart_id == "legacy-chart"
        assert reading.facts["chart"]["sun"] == "Can"
        assert reading.result["summary"] == "Saved reading"
        assert db.get(BirthChart, "legacy-chart")
        assert len(list(db.scalars(select(KnowledgeDocument)))) == 2
        assert db.get(Chunk, "old-2").document.version == "2"
        assert db.get(Chunk, "old-2").document.active
        assert not db.get(Chunk, "old-1").document.active
        assert db.get(Chunk, "old-1").embedding[0] == 1.0
        assert db.get(Chunk, "old-1").embedding_model is None
        assert db.get(UsageBucket, ("legacy-user", 0, "reading")).count == 1
        assert db.get(UsageBucket, ("legacy-user", 0, "chart")).count == 1
    command.downgrade(config, "0002_domain")
    legacy_chunks = Table("knowledge_chunks", MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        row = (
            connection.execute(select(legacy_chunks).where(legacy_chunks.c.id == "old-1"))
            .mappings()
            .one()
        )
        assert row["source"] == "Old source"
        assert row["version"] == "1"
        assert row["embedding"][0] == 1.0
    command.upgrade(config, "head")
