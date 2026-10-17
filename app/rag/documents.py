import hashlib
import json

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import KnowledgeDocument


def source_key(source: str, topic: str) -> str:
    return hashlib.sha256(json.dumps([source, topic]).encode()).hexdigest()


def content_hash(entries: list[dict]) -> str:
    content = [{"content": x["content"], "tags": sorted(x["tags"])} for x in entries]
    return hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def get_or_create_document(
    db: Session, *, source: str, topic: str, version: str, license: str, entries: list[dict]
) -> tuple[KnowledgeDocument, bool]:
    key, checksum = source_key(source, topic), content_hash(entries)
    row = db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.source_key == key, KnowledgeDocument.version == version
        )
    )
    if row:
        if row.content_hash != checksum or row.license != license:
            raise ValueError("A document version is immutable; increment version to change content")
        return row, False
    db.execute(
        update(KnowledgeDocument).where(KnowledgeDocument.source_key == key).values(active=False)
    )
    db.flush()
    row = KnowledgeDocument(
        source_key=key,
        source=source,
        version=version,
        license=license,
        topic=topic,
        content_hash=checksum,
        active=True,
    )
    db.add(row)
    db.flush()
    return row, True
