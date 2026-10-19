"""Durable database queue. Run as a separate process: python -m app.jobs.worker."""

import json
import logging
import signal
import threading
import time
from dataclasses import asdict
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.observability import RunTrace
from app.ai.orchestration.graph import InvalidGeneration, build_reading_graph
from app.ai.prompts.templates import PROMPT_VERSION
from app.ai.providers.openai_provider import OpenAIProvider, ProviderFailure, ProviderUnavailable
from app.core.config import get_settings
from app.db.models import Chunk, Event, GenerationRun, Job, KnowledgeDocument, Message, Reading, now
from app.db.session import get_engine
from app.modules.astrology.service import HOUSES
from app.rag.retrieval import retrieve


def attempt_total(db, job):
    return (
        db.scalar(
            select(func.sum(Job.attempts)).where(
                Job.reading_id == job.reading_id,
                Job.message_id == job.message_id if job.message_id else Job.message_id.is_(None),
            )
        )
        or 0
    )


def claim_job():
    with Session(get_engine()) as db:
        job = db.scalar(
            select(Job)
            .join(Reading)
            .where(
                Job.available_at <= now(),
                or_(
                    Job.status == "pending",
                    (Job.status == "processing") & (Job.lease_until < now()),
                ),
            )
            .order_by(Job.created_at, Job.id)
            .with_for_update(skip_locked=True, of=Reading)
            .limit(1)
        )
        if job is None:
            return None
        job = db.scalar(select(Job).where(Job.id == job.id).with_for_update())
        job.status, job.lease_until, job.lease_token = "processing", now() + 300, str(uuid4())
        job.attempts += 1
        reading = db.get(Reading, job.reading_id)
        target = db.get(Message, job.message_id) if job.message_id else reading
        if attempt_total(db, job) > get_settings().max_job_attempts:
            job.status, target.status = "failed", "failed"
            target.error_code = job.last_error = "worker_retry_limit"
            db.add(
                Event(
                    reading_id=reading.id,
                    name="failed",
                    data={"code": "worker_retry_limit", "message_id": job.message_id},
                )
            )
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
    trace = RunTrace()
    result, error, retryable, retrieval_mode = None, None, False, "metadata"
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
                chart_data = row.facts["chart"]
                if chart_data.get("birth_time_known", True):
                    tags += [
                        f"house-{i + 1}"
                        for i, name in enumerate(HOUSES)
                        if any(p.get("house", "") == name.title() for p in planets.values())
                    ]
                    tags += ["aspect-" + a["aspect"] for a in chart_data.get("aspects", [])]
                    fact_ids += list(chart_data.get("houses", {}))
            with trace.step("retrieval", provider=provider):
                embedded = db.scalar(
                    select(Chunk.id)
                    .join(KnowledgeDocument)
                    .where(
                        KnowledgeDocument.topic == row.kind,
                        KnowledgeDocument.active.is_(True),
                        Chunk.embedding.is_not(None),
                        Chunk.embedding_model == get_settings().embedding_model,
                    )
                    .limit(1)
                )
                vector = (
                    provider.embed(question)
                    if embedded and db.bind.dialect.name == "postgresql"
                    else None
                )
                retrieval = retrieve(
                    db,
                    topic=row.kind,
                    tags=tags,
                    vector=vector,
                    embedding_model=get_settings().embedding_model,
                )
            retrieval_mode = retrieval.mode
            if not retrieval.evidence:
                raise ProviderUnavailable("knowledge_not_seeded")
            sources = [asdict(x) for x in retrieval.evidence]
            history = list(
                db.scalars(
                    select(Message)
                    .where(
                        Message.reading_id == row.id,
                        Message.status == "completed",
                        Message.sequence < message.sequence if message else True,
                    )
                    .order_by(Message.sequence.desc())
                    .limit(3)
                )
            )
            payload = {
                "question": question,
                "facts": (
                    row.facts
                    if row.kind == "tarot"
                    else {
                        "birth_time_known": row.facts["chart"].get("birth_time_known", True),
                        "limitations": row.facts["chart"].get("limitations", []),
                        "planets": row.facts["chart"]["planets"],
                        "houses": row.facts["chart"]["houses"],
                        "aspects": row.facts["chart"]["aspects"],
                    }
                ),
                "fact_ids": fact_ids,
                "sources": sources,
                "original_reading": {"summary": row.result["summary"]} if row.result else None,
                "history": [
                    {"question": x.question, "answer": x.result["summary"] if x.result else None}
                    for x in reversed(history)
                ],
            }
        while len(json.dumps(payload)) > get_settings().max_context_chars and payload["history"]:
            payload["history"].pop(0)
        state = build_reading_graph(provider, trace=trace).invoke({"payload": payload, "corrections": -1})
        result = {
            **state["answer"],
            "sources": sources,
            "prompt_version": PROMPT_VERSION,
            "retrieval_mode": retrieval_mode,
            "reviewed": True,
        }
    except Exception as exc:
        # Never expose raw provider exceptions, prompts or user data to logs/responses.
        if isinstance(exc, (InvalidGeneration, ProviderUnavailable, ProviderFailure)):
            error = str(exc)[:50]
            retryable = isinstance(exc, ProviderFailure) and exc.retryable
        else:
            error = "generation_unavailable"
    with Session(get_engine()) as db:
        reading_id = db.scalar(select(Job.reading_id).where(Job.id == job_id))
        if not reading_id:
            return True
        db.scalar(select(Reading).where(Reading.id == reading_id).with_for_update())
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job or job.lease_token != lease_token:
            return True  # Deleted account or stale worker; never overwrite a reclaimed job.
        target = (
            db.get(Message, job.message_id) if job.message_id else db.get(Reading, job.reading_id)
        )
        retrying = bool(
            error and retryable and attempt_total(db, job) < get_settings().max_job_attempts
        )
        job.status = target.status = "pending" if retrying else ("failed" if error else "completed")
        job.last_error, target.error_code = error, error
        target.result = result
        if retrying:
            job.available_at = now() + min(60, 5 * 2**job.attempts)
            job.lease_token, job.lease_until = None, 0
        db.add(
            Event(
                reading_id=job.reading_id,
                name="retry_scheduled" if retrying else target.status,
                data={
                    "message_id": job.message_id,
                    "code": error,
                    "attempt": job.attempts,
                    "available_at": job.available_at if retrying else None,
                },
            )
        )
        settings = get_settings()
        db.add(
            GenerationRun(
                reading_id=job.reading_id,
                message_id=job.message_id,
                model=provider.model if provider else settings.llm_model,
                prompt_version=PROMPT_VERSION,
                source_ids=[s["source_id"] for s in sources],
                status="failed" if error else "completed",
                error_code=error,
                input_tokens=getattr(provider, "input_tokens", 0),
                output_tokens=getattr(provider, "output_tokens", 0),
                embedding_model=getattr(provider, "embedding_model", None),
                embedding_tokens=getattr(provider, "embedding_tokens", 0),
                calls=getattr(provider, "calls", 0),
                retrieval_mode=retrieval_mode,
                duration_ms=(time.monotonic() - started) * 1000,
                trace=trace.as_dict(),
            )
        )
        db.commit()
    return True


def main():
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    while not stop.is_set():
        try:
            processed = process_one()
        except SQLAlchemyError:
            logging.warning("worker_database_unavailable")
            processed = False
        if not processed:
            stop.wait(1)


if __name__ == "__main__":
    main()
