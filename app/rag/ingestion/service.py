from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.rag.documents import get_or_create_document


class DocumentInput(BaseModel):
    source: str = Field(min_length=1, max_length=500)
    version: str = Field(min_length=1, max_length=30)
    license: str = Field(min_length=1, max_length=80)
    topic: str = Field(pattern="^(tarot|astrology)$")
    tags: list[str] = Field(min_length=1, max_length=30)
    text: str = Field(min_length=20, max_length=100000)


def ingest(db: Session, body: DocumentInput) -> int:
    chunks = [body.text[i : i + 1200] for i in range(0, len(body.text), 1000)]
    entries = [{"content": text, "tags": body.tags} for text in chunks]
    document, created = get_or_create_document(
        db,
        source=body.source,
        version=body.version,
        license=body.license,
        topic=body.topic,
        entries=entries,
    )
    if created:
        for index, text in enumerate(chunks):
            db.add(
                Chunk(
                    id=f"doc:{document.id}:{index}",
                    document_id=document.id,
                    chunk_index=index,
                    tags=body.tags,
                    content=text,
                )
            )
    db.commit()
    return len(chunks)
