from collections.abc import Sequence
from dataclasses import dataclass
from random import SystemRandom


@dataclass(frozen=True)
class DrawnCard:
    card_id: str
    reversed: bool


def draw_cards(
    card_ids: Sequence[str], count: int, *, allow_reversed: bool = True, rng=None
) -> list[DrawnCard]:
    """Draw unique cards. Persist once; retrying a reading must reuse its draw."""
    if len(set(card_ids)) != len(card_ids):
        raise ValueError("Catalog contains duplicate identifiers")
    if count < 1 or count > len(card_ids):
        raise ValueError("Invalid draw size")
    generator = rng if rng is not None else SystemRandom()
    return [
        DrawnCard(card_id, bool(generator.getrandbits(1)) if allow_reversed else False)
        for card_id in generator.sample(list(card_ids), count)
    ]
