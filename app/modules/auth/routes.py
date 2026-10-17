import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas import TokenOut
from app.core.config import get_settings
from app.core.security import (
    DUMMY_HASH,
    auth_rate_limit,
    digest,
    issue_session,
    passwords,
    require_user,
)
from app.db.models import AuthSession, Mail, ResetToken, User, now
from app.db.session import get_session

router = APIRouter(dependencies=[Depends(auth_rate_limit)])


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class Register(Login):
    name: str = Field(min_length=1, max_length=80)


class Refresh(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=256)


class Forgot(BaseModel):
    email: EmailStr


class Reset(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    password: str = Field(min_length=10, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    name: str


@router.post("/register", status_code=201, response_model=TokenOut)
def register(body: Register, db: Session = Depends(get_session)):
    user = User(
        email=str(body.email).lower(),
        name=body.name.strip() or "Arcana",
        password_hash=passwords.hash(body.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Unable to register this email") from None
    return issue_session(db, user.id)


@router.post("/login", response_model=TokenOut)
def login(body: Login, db: Session = Depends(get_session)):
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if not passwords.verify(body.password, user.password_hash if user else DUMMY_HASH) or not user:
        raise HTTPException(401, "Invalid credentials")
    return issue_session(db, user.id)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: Refresh, db: Session = Depends(get_session)):
    row = db.scalar(
        select(AuthSession)
        .where(
            AuthSession.refresh_hash == digest(body.refresh_token),
            AuthSession.refresh_expires > now(),
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(401, "Invalid refresh token")
    return issue_session(db, row.user_id, row)


@router.post("/logout", status_code=204)
def logout(user: User = Depends(require_user), db: Session = Depends(get_session)):
    # Revoke all sessions: explicit and immediate across devices.
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.commit()
    return Response(status_code=204)


@router.post("/forgot-password", status_code=202)
def forgot(body: Forgot, db: Session = Depends(get_session)):
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        raise HTTPException(503, "Password recovery email is not configured")
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user:
        token = secrets.token_urlsafe(48)
        db.execute(delete(Mail).where(Mail.user_id == user.id))
        db.execute(delete(ResetToken).where(ResetToken.user_id == user.id))
        db.add(ResetToken(user_id=user.id, token_hash=digest(token), expires=now() + 1800))
        # Fragment keeps the token out of server access logs. The frontend must consume it.
        link = settings.public_frontend_url.rstrip("/") + "/redefinir-senha#token=" + token
        db.add(
            Mail(
                user_id=user.id,
                recipient=user.email,
                body="Redefina sua senha Arcana (válido por 30 minutos): " + link,
            )
        )
        db.commit()
    return {"detail": "If the account exists, recovery instructions will be sent"}


@router.post("/reset-password", status_code=204)
def reset(body: Reset, db: Session = Depends(get_session)):
    row = db.scalar(
        select(ResetToken)
        .where(ResetToken.token_hash == digest(body.token), ResetToken.expires > now())
        .with_for_update()
    )
    if not row:
        raise HTTPException(400, "Invalid or expired token")
    user = db.get(User, row.user_id)
    user.password_hash = passwords.hash(body.password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(delete(ResetToken).where(ResetToken.user_id == user.id))
    db.execute(delete(Mail).where(Mail.user_id == user.id))
    db.commit()
    return Response(status_code=204)
