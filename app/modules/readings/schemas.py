from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CreateReading(BaseModel):
    kind: Literal["tarot", "astrology"] = "tarot"
    question: str = Field(min_length=5, max_length=2000)
    spread: Literal["daily", "three_cards"] = "three_cards"
    allow_reversed: bool = True
    chart_id: str | None = Field(None, max_length=36)

    @model_validator(mode="after")
    def valid(self):
        self.question = self.question.strip()
        if len(self.question) < 5:
            raise ValueError("Question must have at least 5 non-padding characters")
        if self.kind == "astrology" and not self.chart_id:
            raise ValueError("Astrology readings require a chart_id")
        if self.kind == "tarot" and self.chart_id:
            raise ValueError("Tarot readings do not take chart_id")
        return self


class MessageInput(BaseModel):
    question: str = Field(min_length=5, max_length=2000, pattern=r".*\S.*")
