from dataclasses import dataclass

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB, array
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


@dataclass(frozen=True)
class RetrievalBatch:
    evidence: list[Evidence]
    mode: str


def retrieve(
    db: Session,
    *,
    topic: str,
    tags: list[str],
    vector: list[float] | None = None,
    embedding_model: str | None = None,
    limit: int = 12,
) -> RetrievalBatch:
    base = (
        select(Chunk)
        .join(KnowledgeDocument)
        .options(joinedload(Chunk.document))
        .where(KnowledgeDocument.topic == topic, KnowledgeDocument.active.is_(True))
    )
    metadata = base
    if db.bind.dialect.name == "postgresql" and tags:
        metadata = metadata.where(cast(Chunk.tags, JSONB).has_any(array(tags)))
    rows = list(db.scalars(metadata.limit(1000)))
    exact = sorted(
        (x for x in rows if set(x.tags) & set(tags)),
        key=lambda x: (-len(set(x.tags) & set(tags)), x.id),
    )
    selected = exact[:limit]
    mode = "metadata"
    if vector is not None and embedding_model and db.bind.dialect.name == "postgresql":
        semantic = list(
            db.scalars(
                base.where(Chunk.embedding.is_not(None), Chunk.embedding_model == embedding_model)
                .order_by(Chunk.embedding.cosine_distance(vector))
                .limit(limit)
            )
        )
        if semantic:
            # Reserve context for exact card/planet evidence, then add semantic discoveries.
            selected = exact[: min(8, limit)]
            selected_ids = {x.id for x in selected}
            selected += [x for x in semantic if x.id not in selected_ids][: limit - len(selected)]
            mode = "hybrid"
    evidence = [
        Evidence(
            x.id,
            x.document.version,
            x.content,
            x.document.source,
            x.document_id,
            x.document.license,
        )
        for x in selected
    ]
    return RetrievalBatch(evidence, mode)


def search(db: Session, **kwargs) -> list[Evidence]:
    return retrieve(db, **kwargs).evidence
