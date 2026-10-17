import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AuthSession, RateBucket, User, now
from app.db.session import get_session

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("dummy-password-for-timing-only")
bearer = HTTPBearer(auto_error=False)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(db: Session, user_id: str, existing: AuthSession | None = None):
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    row = existing or AuthSession(user_id=user_id)
    row.access_hash, row.refresh_hash = digest(access), digest(refresh)
    row.access_expires, row.refresh_expires = now() + 900, now() + 30 * 86400
    db.add(row)
    db.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": 900,
    }


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    row = db.scalar(
        select(AuthSession).where(
            AuthSession.access_hash == digest(credentials.credentials),
            AuthSession.access_expires > now(),
        )
    )
    user = db.get(User, row.user_id) if row else None
    if user is None:
        raise HTTPException(401, "Session expired", headers={"WWW-Authenticate": "Bearer"})
    return user


def auth_rate_limit(request: Request, db: Session = Depends(get_session)):
    settings = get_settings()
    # Trust direct peer only; reverse proxy trust must be configured explicitly at deployment.
    peer = request.client.host if request.client else "unknown"
    key = hmac.new(
        settings.rate_limit_secret.get_secret_value().encode(), peer.encode(), hashlib.sha256
    ).hexdigest()
    row = db.scalar(select(RateBucket).where(RateBucket.key == key).with_for_update())
    if row is None:
        db.add(RateBucket(key=key, count=1, expires=now() + settings.auth_window_seconds))
    elif row.expires <= now():
        row.count, row.expires = 1, now() + settings.auth_window_seconds
    elif row.count >= settings.auth_attempt_limit:
        raise HTTPException(429, "Too many authentication attempts", headers={"Retry-After": "900"})
    else:
        row.count += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(429, "Retry authentication shortly") from None
    db.execute(delete(RateBucket).where(RateBucket.expires < now() - 86400))
    db.commit()
