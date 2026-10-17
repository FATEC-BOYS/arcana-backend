from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_spreads() -> list[dict]:
    return [
        {"id": "daily", "positions": ["Reflexão do dia"]},
        {"id": "three_cards", "positions": [
            "Situação atual", "O que merece atenção", "Um caminho possível"
        ]},
    ]
