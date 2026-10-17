from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import UsageBucket, User, now


def reserve_usage(db: Session, user_id: str, kind: str):
    # Called within the same transaction as resource/job creation. PostgreSQL serializes
    # reservations per user, so deletion or concurrent requests cannot reset quota.
    db.scalar(select(User).where(User.id == user_id).with_for_update())
    day = now() // 86400
    key = (user_id, day, kind)
    bucket = db.get(UsageBucket, key)
    settings = get_settings()
    limit = {
        "reading": settings.daily_reading_limit,
        "chart": settings.daily_chart_limit,
        "message": settings.daily_message_limit,
    }[kind]
    if bucket and bucket.count >= limit:
        raise HTTPException(
            429,
            f"Daily {kind} limit reached",
            headers={"Retry-After": str((day + 1) * 86400 - now())},
        )
    if bucket is None:
        bucket = UsageBucket(user_id=user_id, day=day, kind=kind, count=0)
        db.add(bucket)
    bucket.count += 1
