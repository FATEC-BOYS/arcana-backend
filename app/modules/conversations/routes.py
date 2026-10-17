from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import MessageOut
from app.core.config import get_settings
from app.core.security import require_user
from app.core.usage import reserve_usage
from app.db.models import Event, Job, Message, User
from app.db.session import get_session
from app.modules.readings.schemas import MessageInput
from app.modules.readings.service import owned_reading

router = APIRouter()


def message_view(row):
    return {
        "id": row.id,
        "sequence": row.sequence,
        "question": row.question,
        "result": row.result,
        "status": row.status,
        "error_code": row.error_code,
        "created_at": row.created_at,
    }


@router.get("/{reading_id}/messages", response_model=list[MessageOut])
def messages(
    reading_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
    offset: int = Query(0, ge=0),
):
    owned_reading(db, reading_id, user.id)
    rows = db.scalars(
        select(Message)
        .where(Message.reading_id == reading_id)
        .order_by(Message.sequence)
        .offset(offset)
        .limit(100)
    )
    return [message_view(x) for x in rows]


@router.post("/{reading_id}/messages", status_code=202, response_model=MessageOut)
def send(
    reading_id: str,
    body: MessageInput,
    idempotency_key: str = Header(min_length=8, max_length=128),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    row = owned_reading(db, reading_id, user.id, lock=True)
    previous = db.scalar(
        select(Message).where(
            Message.reading_id == row.id, Message.idempotency_key == idempotency_key
        )
    )
    if previous:
        if previous.question != body.question:
            raise HTTPException(409, "Idempotency key conflict")
        return message_view(previous)
    if row.status != "completed":
        raise HTTPException(409, "Wait for the reading to complete")
    if db.scalar(
        select(Job).where(Job.reading_id == row.id, Job.status.in_(["pending", "processing"]))
    ):
        raise HTTPException(409, "A response is already being generated")
    count = db.scalar(select(func.count()).select_from(Message).where(Message.reading_id == row.id))
    if count >= get_settings().max_messages_per_reading:
        raise HTTPException(429, "Conversation limit reached")
    reserve_usage(db, user.id, "message")
    message = Message(
        reading_id=row.id,
        sequence=count + 1,
        question=body.question,
        idempotency_key=idempotency_key,
    )
    db.add(message)
    db.flush()
    db.add(Job(reading_id=row.id, message_id=message.id))
    db.add(Event(reading_id=row.id, name="message_pending", data={"message_id": message.id}))
    db.commit()
    return message_view(message)


@router.get("/{reading_id}/messages/{message_id}", response_model=MessageOut)
def detail(
    reading_id: str,
    message_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    owned_reading(db, reading_id, user.id)
    message = db.scalar(
        select(Message).where(Message.id == message_id, Message.reading_id == reading_id)
    )
    if not message:
        raise HTTPException(404, "Message not found")
    return message_view(message)


@router.post(
    "/{reading_id}/messages/{message_id}/retry", status_code=202, response_model=MessageOut
)
def retry_message(
    reading_id: str,
    message_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    # Keep lock order identical to creation: user, then reading.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    row = owned_reading(db, reading_id, user.id, lock=True)
    message = db.scalar(
        select(Message).where(Message.id == message_id, Message.reading_id == row.id)
    )
    if not message:
        raise HTTPException(404, "Message not found")
    if row.status != "completed" or message.status != "failed":
        raise HTTPException(409, "Only failed messages on completed readings can be retried")
    jobs = list(db.scalars(select(Job).where(Job.reading_id == row.id)))
    if any(job.status in ("pending", "processing") for job in jobs):
        raise HTTPException(409, "A response is already being generated")
    if (
        sum(job.attempts for job in jobs if job.message_id == message.id)
        >= get_settings().max_job_attempts
    ):
        raise HTTPException(429, "Retry limit reached")
    reserve_usage(db, user.id, "message")
    message.status, message.error_code = "pending", None
    db.add(Job(reading_id=row.id, message_id=message.id))
    db.add(Event(reading_id=row.id, name="message_pending", data={"message_id": message.id}))
    db.commit()
    return message_view(message)
