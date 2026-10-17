from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_user
from app.db.models import BirthChart, User, now
from app.db.session import get_session
from app.modules.astrology.schemas import BirthInput
from app.modules.astrology.service import calculate_natal

router = APIRouter()


@router.post("/charts", status_code=201)
def create_chart(
    body: BirthInput, user: User = Depends(require_user), db: Session = Depends(get_session)
):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    count = db.scalar(
        select(func.count())
        .select_from(BirthChart)
        .where(BirthChart.user_id == user.id, BirthChart.created_at >= now() - 86400)
    )
    if count >= 30:
        raise HTTPException(429, "Daily chart limit reached")
    try:
        data = calculate_natal(body)
    except (ValueError, ArithmeticError):
        raise HTTPException(422, "Unable to calculate chart for these birth details") from None
    row = BirthChart(user_id=user.id, birth_input=body.model_dump(mode="json"), data=data)
    db.add(row)
    db.commit()
    return {"id": row.id, "created_at": row.created_at, "data": row.data}


@router.get("/charts")
def charts(
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    rows = db.scalars(
        select(BirthChart)
        .where(BirthChart.user_id == user.id)
        .order_by(BirthChart.created_at.desc(), BirthChart.id)
        .offset(offset)
        .limit(limit)
    )
    return [{"id": x.id, "created_at": x.created_at, "birth_input": x.birth_input} for x in rows]


@router.get("/charts/{chart_id}")
def chart(chart_id: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    row = db.scalar(
        select(BirthChart).where(BirthChart.id == chart_id, BirthChart.user_id == user.id)
    )
    if not row:
        raise HTTPException(404, "Chart not found")
    return {
        "id": row.id,
        "created_at": row.created_at,
        "data": row.data,
        "birth_input": row.birth_input,
    }
