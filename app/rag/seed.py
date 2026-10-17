from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.modules.cards.catalog import CARDS

SIGNS = {
    "Ari": "iniciativa e afirmação",
    "Tau": "continuidade e recursos",
    "Gem": "curiosidade e comunicação",
    "Can": "cuidado e pertencimento",
    "Leo": "expressão e reconhecimento",
    "Vir": "organização e aperfeiçoamento",
    "Lib": "reciprocidade e negociação",
    "Sco": "profundidade e transformação",
    "Sag": "exploração e sentido",
    "Cap": "estrutura e compromisso",
    "Aqu": "coletividade e experimentação",
    "Pis": "imaginação e sensibilidade",
}
PLANET_THEMES = {
    "sun": "identidade",
    "moon": "necessidades emocionais",
    "mercury": "comunicação",
    "venus": "afetos e valores",
    "mars": "iniciativa",
    "jupiter": "expansão",
    "saturn": "limites",
    "uranus": "mudança",
    "neptune": "imaginação",
    "pluto": "transformação",
}


def seed_knowledge(db: Session):
    entries = [
        dict(
            id="tarot:" + c["id"],
            topic="tarot",
            tags=[c["id"]],
            content=c["name"]
            + ": "
            + c["meaning"]
            + " A orientação invertida pode convidar a refletir sobre bloqueio, excesso ou "
            "interiorização desse tema; não muda a carta sorteada.",
        )
        for c in CARDS
    ]
    entries += [
        dict(
            id="astro:" + p + ":" + sign,
            topic="astrology",
            tags=[p, sign],
            content=f"Na leitura simbólica, {p} se relaciona a {theme}; o signo {sign} "
            f"acrescenta temas de {meaning}. Isso não determina personalidade ou futuro.",
        )
        for p, theme in PLANET_THEMES.items()
        for sign, meaning in SIGNS.items()
    ]
    entries += [
        dict(
            id=f"house:{i}",
            topic="astrology",
            tags=[f"house-{i}"],
            content=f"A casa {i} é uma posição calculada a partir do horário e local. "
            "Sem horário confiável, não afirmar precisão de casas ou ascendente.",
        )
        for i in range(1, 13)
    ]
    for entry in entries:
        if db.get(Chunk, entry["id"]) is None:
            db.add(
                Chunk(
                    **entry,
                    source="Arcana: acervo introdutório autoral",
                    version="1",
                    license="AGPL-3.0-or-later",
                )
            )
    db.commit()
