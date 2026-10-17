import hashlib
from dataclasses import asdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.usage import reserve_usage
from app.db.models import BirthChart, Event, Job, Reading, User
from app.modules.cards.catalog import CARD_BY_ID, CARDS
from app.modules.cards.service import draw_cards
from app.modules.readings.schemas import CreateReading


def owned_reading(db: Session, reading_id: str, user_id: str, *, lock=False):
    query = select(Reading).where(Reading.id == reading_id, Reading.user_id == user_id)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if not row:
        raise HTTPException(404, "Reading not found")
    return row


def reading_view(row):
    return {
        "id": row.id,
        "kind": row.kind,
        "chart_id": row.chart_id,
        "question": row.question,
        "facts": row.facts,
        "status": row.status,
        "result": row.result,
        "error_code": row.error_code,
        "created_at": row.created_at,
    }


def create_reading(db: Session, user: User, body: CreateReading, key: str):
    request_hash = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    # Serialize per-user quota/idempotency updates in PostgreSQL.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    existing = db.scalar(
        select(Reading).where(Reading.user_id == user.id, Reading.idempotency_key == key)
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key already used for a different request")
        return existing
    reserve_usage(db, user.id, "reading")
    if body.kind == "tarot":
        positions = (
            ["Reflexão do dia"]
            if body.spread == "daily"
            else ["Situação atual", "O que merece atenção", "Um caminho possível"]
        )
        draw = draw_cards(
            [c["id"] for c in CARDS], len(positions), allow_reversed=body.allow_reversed
        )
        cards = [
            {**asdict(card), "position": pos, "name": CARD_BY_ID[card.card_id]["name"]}
            for card, pos in zip(draw, positions, strict=True)
        ]
        facts = {"spread": body.spread, "cards": cards}
    else:
        chart = db.scalar(
            select(BirthChart).where(BirthChart.id == body.chart_id, BirthChart.user_id == user.id)
        )
        if not chart:
            raise HTTPException(404, "Chart not found")
        facts = {"chart_id": chart.id, "chart": {k: v for k, v in chart.data.items() if k != "svg"}}
    row = Reading(
        user_id=user.id,
        idempotency_key=key,
        request_hash=request_hash,
        kind=body.kind,
        chart_id=body.chart_id if body.kind == "astrology" else None,
        question=body.question,
        facts=facts,
    )
    db.add(row)
    try:
        db.flush()
        db.add(Job(reading_id=row.id))
        db.add(Event(reading_id=row.id, name="pending", data={"kind": row.kind}))
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.scalar(
            select(Reading).where(Reading.user_id == user.id, Reading.idempotency_key == key)
        )
        if not row or row.request_hash != request_hash:
            raise HTTPException(409, "Concurrent request conflict") from None
    return row
