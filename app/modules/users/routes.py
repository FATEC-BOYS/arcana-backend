from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_user
from app.db.models import UsageBucket, User, now
from app.db.session import get_session
from app.modules.auth.routes import UserOut

router = APIRouter()


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r".*\S.*")


@router.get("", response_model=UserOut)
def profile(user: User = Depends(require_user)):
    return user


@router.patch("", response_model=UserOut)
def update(
    body: ProfileUpdate, user: User = Depends(require_user), db: Session = Depends(get_session)
):
    user.name = body.name.strip()
    db.commit()
    return user


@router.delete("", status_code=204)
def delete_account(user: User = Depends(require_user), db: Session = Depends(get_session)):
    db.delete(user)
    db.commit()
    return Response(status_code=204)


@router.get("/usage")
def usage(user: User = Depends(require_user), db: Session = Depends(get_session)):
    settings = get_settings()
    day = now() // 86400
    rows = {
        row.kind: row.count
        for row in db.scalars(
            select(UsageBucket).where(UsageBucket.user_id == user.id, UsageBucket.day == day)
        )
    }
    limits = {
        "reading": settings.daily_reading_limit,
        "chart": settings.daily_chart_limit,
        "message": settings.daily_message_limit,
    }
    return {
        "resets_at": (day + 1) * 86400,
        "timezone": "UTC",
        "quotas": {
            kind: {
                "used": rows.get(kind, 0),
                "limit": limit,
                "remaining": max(0, limit - rows.get(kind, 0)),
            }
            for kind, limit in limits.items()
        },
    }
