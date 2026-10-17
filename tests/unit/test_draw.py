import random
import pytest
from app.modules.cards.service import draw_cards
from app.rag.citations import validate_citations


def test_draw_is_unique_and_from_catalog():
    cards = [str(i) for i in range(78)]
    result = draw_cards(cards, 3, rng=random.Random(42))
    assert len({c.card_id for c in result}) == 3
    assert all(c.card_id in cards for c in result)


def test_reversed_can_be_disabled():
    assert not any(c.reversed for c in draw_cards(["a", "b"], 2, allow_reversed=False))


@pytest.mark.parametrize("cards,count", [(["a", "a"], 1), (["a"], 2), (["a"], 0)])
def test_invalid_draws_fail(cards, count):
    with pytest.raises(ValueError):
        draw_cards(cards, count)


def test_unretrieved_sources_are_rejected():
    assert not validate_citations(["invented"], {"source-1"})
    assert validate_citations(["source-1"], {"source-1"})
    assert not validate_citations([], {"source-1"})
