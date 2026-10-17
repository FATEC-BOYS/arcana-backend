from datetime import UTC, date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator


class BirthInput(BaseModel):
    birth_date: date
    birth_time: time
    latitude: float = Field(ge=-66, le=66, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    timezone: str = Field(max_length=80)
    fold: Literal[0, 1] | None = None

    @field_validator("birth_date")
    @classmethod
    def date_range(cls, value):
        if not date(1900, 1, 1) <= value <= date.today():
            raise ValueError("Supported birth dates: 1900-01-01 through today")
        return value

    @field_validator("birth_time")
    @classmethod
    def local_time(cls, value):
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError("Use a local time with minute precision, e.g. 14:30")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use a valid IANA timezone") from None
        return value

    @model_validator(mode="after")
    def validate_wall_time(self):
        naive = datetime.combine(self.birth_date, self.birth_time)
        zone = ZoneInfo(self.timezone)
        variants = [naive.replace(tzinfo=zone, fold=i) for i in (0, 1)]
        valid = [
            v for v in variants if v.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == naive
        ]
        if not valid:
            raise ValueError("This local time did not exist due to a timezone transition")
        if len({v.utcoffset() for v in valid}) > 1 and self.fold is None:
            raise ValueError("Ambiguous local time; specify fold=0 (first) or 1 (second)")
        return self
