import hashlib

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import Chunk


class DocumentInput(BaseModel):
    source: str = Field(min_length=1, max_length=500)
    version: str = Field(min_length=1, max_length=30)
    license: str = Field(min_length=1, max_length=80)
    topic: str = Field(pattern="^(tarot|astrology)$")
    tags: list[str] = Field(min_length=1, max_length=30)
    text: str = Field(min_length=20, max_length=100000)


def ingest(db: Session, body: DocumentInput) -> int:
    # CLI-only ingestion: callers cannot upload instructions into another user's RAG corpus.
    identity = hashlib.sha256((body.source + body.version + body.text).encode()).hexdigest()[:24]
    chunks = [body.text[i : i + 1200] for i in range(0, len(body.text), 1000)]
    for index, text in enumerate(chunks):
        key = f"doc:{identity}:{index}"
        if db.get(Chunk, key) is None:
            db.add(
                Chunk(
                    id=key,
                    source=body.source,
                    version=body.version,
                    license=body.license,
                    topic=body.topic,
                    tags=body.tags,
                    content=text,
                )
            )
    db.commit()
    return len(chunks)
