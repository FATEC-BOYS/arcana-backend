"""Read-only readiness report. Never prints keys or performs paid model calls."""

import json

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Chunk, KnowledgeDocument
from app.db.session import get_engine


def inspect_system():
    settings = get_settings()
    report = {
        "environment": settings.environment,
        "database": "unavailable",
        "ai_configured": bool(settings.openai_api_key),
        "smtp_configured": bool(settings.smtp_host and settings.smtp_from),
    }
    try:
        with Session(get_engine()) as db:
            report["active_documents"] = db.scalar(
                select(func.count())
                .select_from(KnowledgeDocument)
                .where(KnowledgeDocument.active.is_(True))
            )
            report["active_chunks"] = db.scalar(
                select(func.count())
                .select_from(Chunk)
                .join(KnowledgeDocument)
                .where(KnowledgeDocument.active.is_(True))
            )
            report["matching_embeddings"] = db.scalar(
                select(func.count())
                .select_from(Chunk)
                .join(KnowledgeDocument)
                .where(
                    KnowledgeDocument.active.is_(True),
                    Chunk.embedding_model == settings.embedding_model,
                    Chunk.embedding.is_not(None),
                )
            )
            report["database"] = "ready"
    except SQLAlchemyError:
        report["database"] = "unavailable_or_migrations_missing"
    report["generation_ready"] = bool(
        report["database"] == "ready" and report.get("active_chunks", 0) and report["ai_configured"]
    )
    return report


if __name__ == "__main__":
    print(json.dumps(inspect_system(), ensure_ascii=False, indent=2))
