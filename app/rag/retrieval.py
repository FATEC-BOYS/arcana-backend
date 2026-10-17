from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Evidence:
    source_id: str
    document_version: str
    text: str


class Retriever(Protocol):
    def search(self, query: str, *, card_ids: list[str], limit: int = 6) -> list[Evidence]:
        ...
