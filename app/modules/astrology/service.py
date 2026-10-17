import os
import threading
from datetime import UTC, datetime, time
from importlib.metadata import version
from zoneinfo import ZoneInfo

from app.modules.astrology.schemas import BirthInput

# Explicit Swiss backend uses bundled analytical fallback; no runtime ephemeris downloads.
os.environ["KERYKEION_BACKEND"] = "swisseph"
_LOCK = threading.Lock()
PLANETS = [
    "sun",
    "moon",
    "mercury",
    "venus",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
    "pluto",
]
HOUSES = [
    "first_house",
    "second_house",
    "third_house",
    "fourth_house",
    "fifth_house",
    "sixth_house",
    "seventh_house",
    "eighth_house",
    "ninth_house",
    "tenth_house",
    "eleventh_house",
    "twelfth_house",
]


def calculate_natal(body: BirthInput) -> dict:
    from kerykeion import AstrologicalSubjectFactory, ChartDataFactory, ChartDrawer

    local = datetime.combine(body.birth_date, body.birth_time or time(12, 0)).replace(
        tzinfo=ZoneInfo(body.timezone), fold=body.fold or 0
    )
    utc = local.astimezone(UTC)
    # Swiss Ephemeris has process-global state; serialize local use.
    with _LOCK:
        subject = AstrologicalSubjectFactory.from_birth_data(
            name="Arcana",
            year=utc.year,
            month=utc.month,
            day=utc.day,
            hour=utc.hour,
            minute=utc.minute,
            lng=body.longitude,
            lat=body.latitude,
            tz_str="UTC",
            online=False,
            zodiac_type="Tropical",
            houses_system_identifier="P",
            active_points=[p.title() for p in PLANETS],
        )
        chart = ChartDataFactory.create_natal_chart_data(subject)
        planets = {name: getattr(subject, name).model_dump(mode="json") for name in PLANETS}
        houses = {name: getattr(subject, name).model_dump(mode="json") for name in HOUSES}
        data = chart.model_dump(mode="json")
        known_time = body.birth_time is not None
        svg = ChartDrawer(chart, theme="dark").generate_svg_string() if known_time else None
        if not known_time:
            houses = {}
            for planet in planets.values():
                planet["house"] = None
                planet["approximate"] = True
    return {
        "engine": "kerykeion",
        "engine_version": version("kerykeion"),
        "backend": "swisseph",
        "zodiac": "Tropical",
        "house_system": "Placidus" if known_time else None,
        "ephemeris_precision": "Moshier analytical fallback; no external ephemeris files bundled",
        "utc": utc.isoformat(),
        "birth_time_known": known_time,
        "svg": svg,
        "planets": planets,
        "houses": houses,
        "ascendant": houses.get("first_house"),
        "aspects": data.get("aspects", []) if known_time else [],
        "calculation_metadata": subject.model_dump(mode="json").get("calculation_metadata"),
        "limitations": [
            "Interpretação simbólica para entretenimento e reflexão.",
            "Não utilizamos retificação de horário ou geocodificação automática.",
            *(
                []
                if known_time
                else [
                    "Horário desconhecido: posições aproximadas calculadas ao meio-dia local. "
                    "A Lua e planetas próximos a limites de signo podem variar ao longo do dia. "
                    "Casas, ascendente, aspectos e SVG não são apresentados."
                ]
            ),
        ],
    }
