"""Remove expired operational data; personal readings/diary are never aged out here."""

import argparse
import json

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import AuthSession, Event, Mail, RateBucket, ResetToken, UsageBucket, now
from app.db.session import get_engine


def cleanup(db, *, apply=False):
    criteria = [
        (AuthSession, AuthSession.refresh_expires < now()),
        (ResetToken, ResetToken.expires < now()),
        (Mail, Mail.created_at < now() - 1800),
        (RateBucket, RateBucket.expires < now() - 86400),
        (UsageBucket, UsageBucket.day < now() // 86400 - 90),
        (Event, Event.created_at < now() - 30 * 86400),
    ]
    counts = {}
    for model, condition in criteria:
        counts[model.__tablename__] = db.scalar(
            select(func.count()).select_from(model).where(condition)
        )
        if apply:
            db.execute(delete(model).where(condition))
    if apply:
        db.commit()
    return {"applied": apply, "counts": counts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply cleanup; default is a dry run")
    args = parser.parse_args()
    with Session(get_engine()) as db:
        print(json.dumps(cleanup(db, apply=args.apply)))
