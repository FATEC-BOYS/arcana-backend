import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import BirthChart, Chunk, KnowledgeDocument, Reading, User
from app.db.session import get_engine
from app.rag.ingestion.service import DocumentInput, ingest
from app.rag.retrieval import search
from app.rag.seed import seed_knowledge


def test_versioning_is_immutable_and_retrieval_uses_active_version(client):
    original = DocumentInput(
        source="Arcana test guide",
        version="1",
        license="CC0",
        topic="tarot",
        tags=["test-card"],
        text="Texto original sobre uma carta de teste para reflexão.",
    )
    with Session(get_engine()) as db:
        ingest(db, original)
        ingest(db, original)
        first = db.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.source == original.source)
        )
        first_id = first.id
        assert len(list(db.scalars(select(Chunk).where(Chunk.document_id == first_id)))) == 1
        with pytest.raises(ValueError, match="immutable"):
            ingest(
                db,
                original.model_copy(update={"text": "Outro conteúdo que exige uma nova versão."}),
            )
        db.rollback()
        ingest(
            db,
            original.model_copy(
                update={
                    "version": "2",
                    "text": "Nova interpretação simbólica da mesma carta de teste.",
                }
            ),
        )
        results = search(db, topic="tarot", tags=["test-card"])
        assert len(results) == 1
        assert results[0].document_version == "2"
        assert results[0].license == "CC0"
        assert db.get(KnowledgeDocument, first_id).active is False
        assert db.scalar(select(Chunk).where(Chunk.document_id == first_id)) is not None
        # Re-running an older source version must not reactivate it.
        ingest(db, original)
        assert search(db, topic="tarot", tags=["test-card"])[0].document_version == "2"


def test_document_cascade_and_seed_idempotency(client):
    with Session(get_engine()) as db:
        seed_knowledge(db)
        assert len(list(db.scalars(select(KnowledgeDocument)))) == 2
        document = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.topic == "tarot"))
        document_id = document.id
        # Database cascade also works when no ORM collection is loaded.
        db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
        db.commit()
        assert not list(db.scalars(select(Chunk).where(Chunk.document_id == document_id)))


def test_database_rejects_cross_owner_chart_link(client, auth):
    with Session(get_engine()) as db:
        owner = db.scalar(select(User))
        other = User(email="other@example.com", name="Other", password_hash="not-used")
        db.add(other)
        db.flush()
        chart = BirthChart(user_id=owner.id, birth_input={}, data={})
        db.add(chart)
        db.flush()
        db.add(
            Reading(
                user_id=other.id,
                chart_id=chart.id,
                kind="astrology",
                question="Question",
                idempotency_key="db-cross-owner",
                request_hash="a" * 64,
                facts={},
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
