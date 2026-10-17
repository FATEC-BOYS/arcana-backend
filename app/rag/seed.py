from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.modules.cards.catalog import CARDS
from app.rag.documents import get_or_create_document

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


HOUSE_THEMES = {
    1: "apresentação de si e modo de iniciar experiências",
    2: "recursos pessoais, sustento e percepção de valor",
    3: "comunicação, aprendizado cotidiano e ambiente próximo",
    4: "raízes, intimidade, moradia e sensação de pertencimento",
    5: "expressão criativa, prazer e espaço para brincar",
    6: "rotina, trabalho cotidiano e cuidado prático, sem diagnóstico de saúde",
    7: "parcerias, acordos e relações de reciprocidade",
    8: "recursos compartilhados, intimidade e transformações simbólicas",
    9: "estudos amplos, exploração e construção de sentido",
    10: "papel público, carreira e responsabilidades reconhecidas",
    11: "amizades, grupos e projetos coletivos",
    12: "recolhimento, elaboração interna e o que pede tempo para ser compreendido",
}
ASPECT_THEMES = {
    "conjunction": "aproximação e combinação de temas; pode trazer foco ou intensificação",
    "opposition": "polaridades que convidam a negociação e reconhecimento de perspectivas",
    "square": "tensão que pode revelar conflitos de necessidades e pedir ajustes",
    "trine": "fluidez entre temas, que ainda depende de escolhas e prática",
    "sextile": "possibilidade de cooperação que pode ser cultivada ativamente",
}
SEED_VERSION = "2"


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
            content=f"Na interpretação simbólica, a casa {i} se relaciona a {HOUSE_THEMES[i]}. "
            "Sem horário confiável, não afirmar precisão de casas ou ascendente.",
        )
        for i in range(1, 13)
    ]
    entries += [
        dict(
            id="aspect:" + aspect,
            topic="astrology",
            tags=["aspect-" + aspect],
            content=f"O aspecto {aspect} é interpretado simbolicamente como {theme}. "
            "Não determina acontecimentos nem substitui contexto individual.",
        )
        for aspect, theme in ASPECT_THEMES.items()
    ]
    for topic in ("tarot", "astrology"):
        grouped = sorted((x for x in entries if x["topic"] == topic), key=lambda x: x["id"])
        document, created = get_or_create_document(
            db,
            source="Arcana: acervo introdutório autoral",
            topic=topic,
            version=SEED_VERSION,
            license="AGPL-3.0-or-later",
            entries=grouped,
        )
        if created:
            for index, entry in enumerate(grouped):
                db.add(
                    Chunk(
                        id=f"seed-v{SEED_VERSION}:" + entry["id"],
                        document_id=document.id,
                        chunk_index=index,
                        tags=entry["tags"],
                        content=entry["content"],
                    )
                )
    db.commit()
