from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Chunk, KnowledgeDocument


@dataclass(frozen=True)
class Evidence:
    source_id: str
    document_version: str
    text: str
    source: str
    document_id: str
    license: str


def search(
    db: Session, *, topic: str, tags: list[str], vector: list[float] | None = None, limit: int = 12
) -> list[Evidence]:
    base = (
        select(Chunk)
        .join(KnowledgeDocument)
        .options(joinedload(Chunk.document))
        .where(KnowledgeDocument.topic == topic, KnowledgeDocument.active.is_(True))
    )

    def evidence(x):
        return Evidence(
            x.id,
            x.document.version,
            x.content,
            x.document.source,
            x.document_id,
            x.document.license,
        )

    if vector is not None and db.bind.dialect.name == "postgresql":
        query = (
            base.where(Chunk.embedding.is_not(None))
            .order_by(Chunk.embedding.cosine_distance(vector))
            .limit(limit)
        )
        rows = list(db.scalars(query))
        if rows:
            return [evidence(x) for x in rows]
    # Deterministic metadata retrieval is explicit, not mislabeled semantic search.
    rows = list(db.scalars(base))
    ranked = sorted(rows, key=lambda x: (-len(set(x.tags) & set(tags)), x.id))
    return [evidence(x) for x in ranked[:limit] if set(x.tags) & set(tags)]
