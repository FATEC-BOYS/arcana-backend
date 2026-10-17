import pytest
from pydantic import ValidationError

from app.modules.astrology.schemas import BirthInput
from app.modules.astrology.service import calculate_natal


def test_real_calculation_and_utc_equivalence():
    rome = BirthInput(
        birth_date="1990-07-15",
        birth_time="10:30",
        latitude=41.9028,
        longitude=12.4964,
        timezone="Europe/Rome",
    )
    utc = BirthInput(
        birth_date="1990-07-15",
        birth_time="08:30",
        latitude=41.9028,
        longitude=12.4964,
        timezone="UTC",
    )
    result = calculate_natal(rome)
    assert result["planets"]["sun"]["sign"] == "Can"
    assert len(result["planets"]) == 10
    assert len(result["houses"]) == 12
    assert result["planets"] == calculate_natal(utc)["planets"]
    assert result["aspects"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timezone": "not/a/zone"},
        {"latitude": 89},
        {"birth_time": "10:30:01"},
        {"birth_date": "2024-03-10", "birth_time": "02:30", "timezone": "America/New_York"},
        {"birth_date": "2024-11-03", "birth_time": "01:30", "timezone": "America/New_York"},
    ],
)
def test_invalid_or_ambiguous_birth_data(kwargs):
    data = dict(
        birth_date="1990-07-15",
        birth_time="10:30",
        latitude=-23.5,
        longitude=-46.6,
        timezone="America/Sao_Paulo",
    )
    with pytest.raises(ValidationError):
        BirthInput(**{**data, **kwargs})


def test_fold_resolves_repeated_hour():
    body = dict(
        birth_date="2024-11-03",
        birth_time="01:30",
        latitude=40.7,
        longitude=-74,
        timezone="America/New_York",
    )
    first = calculate_natal(BirthInput(**body, fold=0))
    second = calculate_natal(BirthInput(**body, fold=1))
    assert first["utc"] != second["utc"]
