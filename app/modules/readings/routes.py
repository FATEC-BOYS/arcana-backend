import asyncio
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ReadingOut
from app.core.config import get_settings
from app.core.security import digest, require_user
from app.core.usage import reserve_usage
from app.db.models import AuthSession, Event, Job, Reading, User, now
from app.db.session import get_engine, get_session
from app.modules.readings.schemas import CreateReading
from app.modules.readings.service import create_reading, owned_reading, reading_view

router = APIRouter()


@router.post("", status_code=202, response_model=ReadingOut)
def create(
    body: CreateReading,
    idempotency_key: str = Header(min_length=8, max_length=128),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    return reading_view(create_reading(db, user, body, idempotency_key))


@router.get("", response_model=list[ReadingOut])
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


@router.get("/{reading_id}", response_model=ReadingOut)
def detail(reading_id: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    return reading_view(owned_reading(db, reading_id, user.id))


@router.post("/{reading_id}/retry", status_code=202, response_model=ReadingOut)
def retry(reading_id: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    row = owned_reading(db, reading_id, user.id, lock=True)
    if row.status != "failed":
        raise HTTPException(409, "Only failed readings may be retried")
    jobs = list(db.scalars(select(Job).where(Job.reading_id == row.id, Job.message_id.is_(None))))
    if sum(j.attempts for j in jobs) >= get_settings().max_job_attempts:
        raise HTTPException(429, "Retry limit reached")
    reserve_usage(db, user.id, "reading")
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

    # All synchronous database work finishes in a thread before yielding bytes.
    def poll(cursor):
        with Session(get_engine()) as connection:
            session_valid = connection.scalar(
                select(AuthSession.id).where(
                    AuthSession.access_hash == access_hash, AuthSession.access_expires > now()
                )
            )
            if not session_valid:
                return [], True, "session_expired"
            row = connection.scalar(
                select(Reading).where(Reading.id == reading_id, Reading.user_id == user_id)
            )
            if not row:
                return [], True, "deleted"
            entries = [
                {"id": e.id, "name": e.name, "data": e.data}
                for e in connection.scalars(
                    select(Event)
                    .where(Event.reading_id == reading_id, Event.id > cursor)
                    .order_by(Event.id)
                    .limit(500)
                )
            ]
            active = connection.scalar(
                select(Job.id)
                .where(Job.reading_id == reading_id, Job.status.in_(["pending", "processing"]))
                .limit(1)
            )
            return (
                entries,
                (row.status in ("completed", "failed") and active is None and len(entries) < 500),
                None,
            )

    async def stream():
        cursor = last_event_id
        for _ in range(120):
            if await request.is_disconnected():
                break
            entries, terminal, reason = await asyncio.to_thread(poll, cursor)
            for event in entries:
                cursor = event["id"]
                yield f"id: {cursor}\nevent: {event['name']}\ndata: {json.dumps(event['data'])}\n\n"
            if reason:
                yield f"event: stream_closed\ndata: {json.dumps({'reason': reason})}\n\n"
            if terminal:
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.delete("/{reading_id}", status_code=204)
def delete_reading(
    reading_id: str, user: User = Depends(require_user), db: Session = Depends(get_session)
):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    row = owned_reading(db, reading_id, user.id, lock=True)
    db.delete(row)
    db.commit()
    return Response(status_code=204)
