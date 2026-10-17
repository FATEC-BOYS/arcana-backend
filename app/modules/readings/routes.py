import asyncio
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import digest, require_user
from app.db.models import AuthSession, Event, Job, Reading, User, now
from app.db.session import get_engine, get_session
from app.modules.readings.schemas import CreateReading
from app.modules.readings.service import create_reading, owned_reading, reading_view

router = APIRouter()


@router.post("", status_code=202)
def create(
    body: CreateReading,
    idempotency_key: str = Header(min_length=8, max_length=128),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    return reading_view(create_reading(db, user, body, idempotency_key))


@router.get("")
def history(
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    rows = db.scalars(
        select(Reading)
        .where(Reading.user_id == user.id)
        .order_by(Reading.created_at.desc(), Reading.id)
        .offset(offset)
        .limit(limit)
    )
    return [reading_view(x) for x in rows]


@router.get("/{reading_id}")
def detail(reading_id: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    return reading_view(owned_reading(db, reading_id, user.id))


@router.post("/{reading_id}/retry", status_code=202)
def retry(reading_id: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    row = owned_reading(db, reading_id, user.id, lock=True)
    if row.status != "failed":
        raise HTTPException(409, "Only failed readings may be retried")
    jobs = list(db.scalars(select(Job).where(Job.reading_id == row.id, Job.message_id.is_(None))))
    if sum(j.attempts for j in jobs) >= 3:
        raise HTTPException(429, "Retry limit reached")
    row.status, row.error_code = "pending", None
    db.add(Job(reading_id=row.id))
    db.add(Event(reading_id=row.id, name="pending", data={"retry": True}))
    db.commit()
    return reading_view(row)


@router.get("/{reading_id}/events")
def events(
    reading_id: str,
    request: Request,
    last_event_id: int = Header(0, ge=0),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    owned_reading(db, reading_id, user.id)
    user_id = user.id
    access_hash = digest(request.headers.get("authorization", "").split(" ", 1)[-1])
    db.rollback()

    # Use fetch streaming with Authorization; native EventSource cannot set that header.
    async def stream():
        cursor = last_event_id
        for _ in range(120):
            if await request.is_disconnected():
                break
            with Session(get_engine()) as connection:
                session_valid = connection.scalar(
                    select(AuthSession.id).where(
                        AuthSession.access_hash == access_hash, AuthSession.access_expires > now()
                    )
                )
                if not session_valid:
                    break
                row = connection.scalar(
                    select(Reading).where(Reading.id == reading_id, Reading.user_id == user_id)
                )
                if not row:
                    break
                entries = list(
                    connection.scalars(
                        select(Event)
                        .where(Event.reading_id == reading_id, Event.id > cursor)
                        .order_by(Event.id)
                    )
                )
                active = connection.scalar(
                    select(Job.id)
                    .where(Job.reading_id == reading_id, Job.status.in_(["pending", "processing"]))
                    .limit(1)
                )
                terminal = row.status in ("completed", "failed") and active is None
                for event in entries:
                    cursor = event.id
                    yield f"id: {event.id}\nevent: {event.name}\ndata: {json.dumps(event.data)}\n\n"
                if terminal:
                    break
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
