from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_user
from app.db.models import User
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
