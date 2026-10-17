"""Run from repository root: python -m scripts.manage seed|embed|ingest FILE."""

import argparse
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.providers.openai_provider import OpenAIProvider
from app.db.models import Chunk, KnowledgeDocument
from app.db.session import get_engine
from app.rag.ingestion.service import DocumentInput, ingest
from app.rag.seed import seed_knowledge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["seed", "embed", "ingest"])
    parser.add_argument("file", nargs="?")
    args = parser.parse_args()
    with Session(get_engine()) as db:
        if args.action == "seed":
            seed_knowledge(db)
            print("Original introductory corpus seeded")
        elif args.action == "ingest":
            if not args.file:
                parser.error("ingest requires a JSON file")
            print(
                "Chunks:",
                ingest(db, DocumentInput.model_validate_json(Path(args.file).read_text())),
            )
        else:
            provider = OpenAIProvider()
            rows = list(
                db.scalars(
                    select(Chunk)
                    .join(KnowledgeDocument)
                    .where(KnowledgeDocument.active.is_(True), Chunk.embedding.is_(None))
                )
            )
            for row in rows:
                row.embedding = provider.embed(row.content)
                db.commit()
            print("Embedded chunks:", len(rows))


if __name__ == "__main__":
    main()
