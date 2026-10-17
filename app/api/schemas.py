from typing import Any, Literal

from pydantic import BaseModel


class ReadingOut(BaseModel):
    id: str
    kind: Literal["tarot", "astrology"]
    chart_id: str | None
    question: str
    facts: dict[str, Any]
    status: Literal["pending", "processing", "completed", "failed"]
    result: dict[str, Any] | None
    error_code: str | None
    created_at: int


class MessageOut(BaseModel):
    id: str
    sequence: int
    question: str
    result: dict[str, Any] | None
    status: Literal["pending", "processing", "completed", "failed"]
    error_code: str | None
    created_at: int


class JournalOut(BaseModel):
    id: str
    reading_id: str
    note: str
    favorite: bool
    updated_at: int


class CardOut(BaseModel):
    id: str
    name: str
    arcana: Literal["major", "minor"]
    suit: str | None
    meaning: str


class SpreadOut(BaseModel):
    id: str
    positions: list[str]


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"]
    expires_in: int
