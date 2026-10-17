from typing import TypedDict

from pydantic import BaseModel, Field


class Interpretation(BaseModel):
    summary: str = Field(min_length=10, max_length=6000)
    reflections: list[str] = Field(min_length=1, max_length=5)
    source_ids: list[str] = Field(min_length=1, max_length=12)
    fact_ids: list[str] = Field(min_length=1, max_length=30)


class Review(BaseModel):
    approved: bool
    feedback: str = Field(max_length=1500)


class ReadingState(TypedDict, total=False):
    payload: dict
    answer: dict
    review: dict
    corrections: int
