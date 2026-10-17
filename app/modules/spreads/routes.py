from fastapi import APIRouter

from app.api.schemas import SpreadOut

router = APIRouter()


@router.get("", response_model=list[SpreadOut])
def list_spreads() -> list[dict]:
    return [
        {"id": "daily", "positions": ["Reflexão do dia"]},
        {
            "id": "three_cards",
            "positions": ["Situação atual", "O que merece atenção", "Um caminho possível"],
        },
    ]
