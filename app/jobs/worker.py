"""Durable database queue. Run as a separate process: python -m app.jobs.worker."""

import time
from dataclasses import asdict
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.orchestration.graph import build_reading_graph
from app.ai.prompts.templates import PROMPT_VERSION
from app.ai.providers.openai_provider import OpenAIProvider
from app.db.models import Chunk, Event, GenerationRun, Job, Message, Reading, now
from app.db.session import get_engine
from app.rag.retrieval import search


def claim_job():
    with Session(get_engine()) as db:
        job = db.scalar(
            select(Job)
            .where(
                or_(
                    Job.status == "pending",
                    (Job.status == "processing") & (Job.lease_until < now()),
                )
            )
            .order_by(Job.created_at, Job.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        job.status, job.lease_until, job.lease_token = "processing", now() + 300, str(uuid4())
        job.attempts += 1
        reading = db.get(Reading, job.reading_id)
        target = db.get(Message, job.message_id) if job.message_id else reading
        if job.attempts > 3:
            job.status, target.status = "failed", "failed"
            db.add(Event(reading_id=reading.id, name="failed", data={"code": "worker_retry_limit"}))
            db.commit()
            return None
        target.status = "processing"
        db.add(Event(reading_id=reading.id, name="processing", data={"message_id": job.message_id}))
        key, token = job.id, job.lease_token
        db.commit()
        return key, token


def process_one(provider_factory=OpenAIProvider) -> bool:
    claimed = claim_job()
    if claimed is None:
        return False
    job_id, lease_token = claimed
    started, provider, sources = time.monotonic(), None, []
    result, error = None, None
    try:
        provider = provider_factory()
        with Session(get_engine()) as db:
            job = db.get(Job, job_id)
            if not job:
                return True
            row = db.get(Reading, job.reading_id)
            message = db.get(Message, job.message_id) if job.message_id else None
            question = message.question if message else row.question
            if row.kind == "tarot":
                tags = [x["card_id"] for x in row.facts["cards"]]
                fact_ids = tags
            else:
                planets = row.facts["chart"]["planets"]
                tags = list(planets) + [v["sign"] for v in planets.values()]
                fact_ids = list(planets)
            embedded = db.scalar(
                select(Chunk.id)
                .where(Chunk.topic == row.kind, Chunk.embedding.is_not(None))
                .limit(1)
            )
            vector = (
                provider.embed(question)
                if embedded and db.bind.dialect.name == "postgresql"
                else None
            )
            evidence = search(db, topic=row.kind, tags=tags, vector=vector)
            if not evidence:
                raise RuntimeError("knowledge_not_seeded")
            sources = [asdict(x) for x in evidence]
            history = list(
                db.scalars(
                    select(Message)
                    .where(Message.reading_id == row.id, Message.status == "completed")
                    .order_by(Message.created_at.desc())
                    .limit(3)
                )
            )
            payload = {
                "question": question,
                "facts": row.facts,
                "fact_ids": fact_ids,
                "sources": sources,
                "original_reading": {"summary": row.result["summary"]} if row.result else None,
                "history": [
                    {"question": x.question, "answer": x.result["summary"] if x.result else None}
                    for x in reversed(history)
                ],
            }
        state = build_reading_graph(provider).invoke({"payload": payload, "corrections": -1})
        result = {
            **state["answer"],
            "sources": sources,
            "prompt_version": PROMPT_VERSION,
            "retrieval_mode": "semantic" if vector is not None else "metadata",
            "reviewed": True,
        }
    except Exception as exc:
        # Never expose raw provider exceptions, prompts or user data to logs/responses.
        from app.ai.orchestration.graph import InvalidGeneration
        from app.ai.providers.openai_provider import ProviderUnavailable

        if isinstance(exc, (InvalidGeneration, ProviderUnavailable)):
            error = str(exc)[:50]
        else:
            error = "generation_unavailable"
    with Session(get_engine()) as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job or job.lease_token != lease_token:
            return True  # Deleted account or stale worker; never overwrite a reclaimed job.
        target = (
            db.get(Message, job.message_id) if job.message_id else db.get(Reading, job.reading_id)
        )
        job.status = target.status = "failed" if error else "completed"
        target.result = result
        if isinstance(target, Reading):
            target.error_code = error
        db.add(
            Event(
                reading_id=job.reading_id,
                name=target.status,
                data={"message_id": job.message_id, "code": error},
            )
        )
        if provider:
            db.add(
                GenerationRun(
                    reading_id=job.reading_id,
                    model=provider.model,
                    prompt_version=PROMPT_VERSION,
                    source_ids=[s["source_id"] for s in sources],
                    input_tokens=provider.input_tokens,
                    output_tokens=provider.output_tokens,
                    calls=provider.calls,
                    duration_ms=(time.monotonic() - started) * 1000,
                )
            )
        db.commit()
    return True


def main():
    while True:
        if not process_one():
            time.sleep(1)


if __name__ == "__main__":
    main()
