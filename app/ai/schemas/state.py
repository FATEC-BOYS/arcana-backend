from typing import TypedDict


class ReadingState(TypedDict):
    reading_id: str
    question: str
    card_ids: list[str]
    source_ids: list[str]
    interpretation: str
    review_attempts: int
