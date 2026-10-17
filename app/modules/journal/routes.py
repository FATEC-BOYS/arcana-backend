from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_user
from app.db.models import JournalEntry, User, now
from app.db.session import get_session
from app.modules.readings.service import owned_reading

router = APIRouter()


class JournalInput(BaseModel):
    note: str = Field(default="", max_length=10000)
    favorite: bool = False


def view(row):
    return {
        "id": row.id,
        "reading_id": row.reading_id,
        "note": row.note,
        "favorite": row.favorite,
        "updated_at": row.updated_at,
    }


@router.put("/{reading_id}")
def save(
    reading_id: str,
    body: JournalInput,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    owned_reading(db, reading_id, user.id, lock=True)
    row = db.scalar(select(JournalEntry).where(JournalEntry.reading_id == reading_id))
    if row is None:
        row = JournalEntry(reading_id=reading_id, user_id=user.id)
    row.note, row.favorite, row.updated_at = body.note, body.favorite, now()
    db.add(row)
    db.commit()
    return view(row)


@router.get("")
def entries(
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    favorites_only: bool = False,
):
    query = select(JournalEntry).where(JournalEntry.user_id == user.id)
    if favorites_only:
        query = query.where(JournalEntry.favorite.is_(True))
    return [
        view(x)
        for x in db.scalars(
            query.order_by(JournalEntry.updated_at.desc(), JournalEntry.id)
            .offset(offset)
            .limit(limit)
        )
    ]
