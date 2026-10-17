from fastapi import APIRouter, HTTPException

from app.api.schemas import CardOut
from app.modules.cards.catalog import CARD_BY_ID, CARDS

router = APIRouter()


@router.get("", response_model=list[CardOut])
def list_cards():
    return CARDS


@router.get("/{card_id}", response_model=CardOut)
def card(card_id: str):
    if card_id not in CARD_BY_ID:
        raise HTTPException(404, "Card not found")
    return CARD_BY_ID[card_id]
