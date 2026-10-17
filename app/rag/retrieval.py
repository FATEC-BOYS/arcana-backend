from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk


@dataclass(frozen=True)
class Evidence:
    source_id: str
    document_version: str
    text: str
    source: str


def search(
    db: Session, *, topic: str, tags: list[str], vector: list[float] | None = None, limit: int = 12
) -> list[Evidence]:
    if vector is not None and db.bind.dialect.name == "postgresql":
        query = (
            select(Chunk)
            .where(Chunk.topic == topic, Chunk.embedding.is_not(None))
            .order_by(Chunk.embedding.cosine_distance(vector))
            .limit(limit)
        )
        rows = list(db.scalars(query))
        if rows:
            return [Evidence(x.id, x.version, x.content, x.source) for x in rows]
    # Deterministic metadata retrieval is explicit, not mislabeled semantic search.
    rows = list(db.scalars(select(Chunk).where(Chunk.topic == topic)))
    ranked = sorted(rows, key=lambda x: (-len(set(x.tags) & set(tags)), x.id))
    return [
        Evidence(x.id, x.version, x.content, x.source)
        for x in ranked[:limit]
        if set(x.tags) & set(tags)
    ]
