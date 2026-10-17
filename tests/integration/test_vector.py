import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.db.session import get_engine
from app.rag.retrieval import search


def test_postgres_semantic_retrieval(client):
    if get_engine().dialect.name != "postgresql":
        pytest.skip("PostgreSQL vector distance required")
    vector = [1.0] + [0.0] * 1535
    with Session(get_engine()) as db:
        chunk = db.scalar(select(Chunk).where(Chunk.id == "seed-v2:tarot:major-00"))
        chunk.embedding = vector
        chunk.embedding_model = "text-embedding-3-small"
        db.commit()
        evidence = search(
            db,
            topic="tarot",
            tags=["major-00"],
            vector=vector,
            embedding_model="text-embedding-3-small",
        )
        assert evidence[0].source_id == "seed-v2:tarot:major-00"
