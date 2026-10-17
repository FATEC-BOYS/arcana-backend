from fastapi import APIRouter, HTTPException

from app.modules.cards.catalog import CARD_BY_ID, CARDS

router = APIRouter()


@router.get("")
def list_cards():
    return CARDS


@router.get("/{card_id}")
def card(card_id: str):
    if card_id not in CARD_BY_ID:
        raise HTTPException(404, "Card not found")
    return CARD_BY_ID[card_id]
