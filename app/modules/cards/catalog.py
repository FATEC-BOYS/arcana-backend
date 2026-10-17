"""Original short descriptions. No third-party deck artwork is distributed."""

MAJORS = [
    ("O Louco", "abertura, espontaneidade e responsabilidade diante do desconhecido"),
    ("O Mago", "iniciativa e uso consciente dos recursos disponíveis"),
    ("A Sacerdotisa", "escuta, observação e espaço para o que ainda não está claro"),
    ("A Imperatriz", "cuidado, criatividade e condições para algo crescer"),
    ("O Imperador", "estrutura, limites e responsabilidade"),
    ("O Hierofante", "tradição, aprendizado e revisão das próprias referências"),
    ("Os Enamorados", "escolhas, vínculos e alinhamento entre valores e ações"),
    ("O Carro", "direção, autonomia e coordenação de forças diferentes"),
    ("A Força", "coragem serena, paciência e manejo dos impulsos"),
    ("O Eremita", "recolhimento, discernimento e busca de orientação"),
    ("A Roda da Fortuna", "mudanças de ciclo e limites do controle pessoal"),
    ("A Justiça", "equilíbrio, consequências e revisão dos critérios de decisão"),
    ("O Enforcado", "pausa e mudança de perspectiva"),
    ("A Morte", "encerramentos simbólicos e transformação; não morte literal"),
    ("A Temperança", "integração, moderação e ajuste gradual"),
    ("O Diabo", "apegos, automatismos e recuperação da liberdade de escolha"),
    ("A Torre", "revisão de estruturas frágeis e resposta a rupturas"),
    ("A Estrela", "esperança, reconexão e cuidado com expectativas"),
    ("A Lua", "ambiguidade, imaginação e distinção entre receios e evidências"),
    ("O Sol", "clareza, expressão e reconhecimento do que sustenta a vida"),
    ("O Julgamento", "reavaliação, responsabilidade e possibilidade de recomeço"),
    ("O Mundo", "integração de aprendizados e conclusão de etapas"),
]
SUITS = {
    "wands": ("Paus", "iniciativa e ação"),
    "cups": ("Copas", "afetos e vínculos"),
    "swords": ("Espadas", "pensamento e comunicação"),
    "pentacles": ("Ouros", "recursos, trabalho e vida material"),
}
RANKS = [
    ("ace", "Ás", "início"),
    ("two", "Dois", "equilíbrio"),
    ("three", "Três", "desenvolvimento"),
    ("four", "Quatro", "estabilidade"),
    ("five", "Cinco", "tensão"),
    ("six", "Seis", "reorganização"),
    ("seven", "Sete", "discernimento"),
    ("eight", "Oito", "movimento"),
    ("nine", "Nove", "amadurecimento"),
    ("ten", "Dez", "conclusão"),
    ("page", "Pajem", "aprendizado"),
    ("knight", "Cavaleiro", "busca"),
    ("queen", "Rainha", "cultivo"),
    ("king", "Rei", "responsabilidade"),
]
CARDS = [
    dict(
        id=f"major-{i:02d}",
        name=name,
        arcana="major",
        suit=None,
        meaning=f"Símbolo de {meaning}. Leitura para reflexão, não previsão factual.",
    )
    for i, (name, meaning) in enumerate(MAJORS)
]
CARDS += [
    dict(
        id=f"{suit}-{rank}",
        name=f"{name} de {pt}",
        arcana="minor",
        suit=suit,
        meaning=f"Combina {theme} com {area}. Explore a relação com a pergunta, "
        "sem tratar o símbolo como certeza sobre pessoas ou acontecimentos.",
    )
    for suit, (pt, area) in SUITS.items()
    for rank, name, theme in RANKS
]
CARD_BY_ID = {card["id"]: card for card in CARDS}


# Original editorial readings, intentionally short and tied to each minor card.
MINOR_MEANINGS = {
    "wands": [
        "Um impulso criativo pede espaço e uma primeira ação possível.",
        "Planejamento entre o que já existe e a vontade de explorar novos caminhos.",
        "Expansão que exige acompanhar resultados e ajustar expectativas.",
        "Celebração, pertencimento e reconhecimento de uma base construída.",
        "Interesses em disputa pedem negociação e clareza sobre prioridades.",
        "Reconhecimento de uma conquista sem perder o diálogo com quem participou.",
        "Defesa de uma posição e revisão dos limites que valem ser sustentados.",
        "Movimento e comunicação rápidos pedem coordenação antes da próxima ação.",
        "Persistência depois do desgaste, com espaço para proteger a própria energia.",
        "Excesso de responsabilidades convida a distribuir tarefas e rever compromissos.",
        "Curiosidade e disposição para experimentar uma iniciativa ainda em formação.",
        "Entusiasmo para avançar, equilibrando impulso e continuidade.",
        "Confiança criativa e presença que acolhe a expressão de outras pessoas.",
        "Visão e liderança que precisam transformar inspiração em responsabilidade.",
    ],
    "cups": [
        "Abertura para sentir e reconhecer uma necessidade afetiva.",
        "Reciprocidade e encontro, com espaço para escuta e acordos.",
        "Amizade, apoio coletivo e celebração de vínculos.",
        "Recolhimento emocional e atenção ao que está sendo oferecido ou recusado.",
        "Frustração e luto simbólico, reconhecendo perdas sem apagar apoios presentes.",
        "Memórias e familiaridade podem acolher, mas também pedir atualização.",
        "Muitas possibilidades imaginadas pedem critérios e contato com a realidade.",
        "Afastamento do que perdeu sentido para procurar uma relação mais coerente.",
        "Satisfação e reconhecimento do que nutre, sem transformar desejo em garantia.",
        "Convivência e bem-estar compartilhado, atentos às necessidades individuais.",
        "Sensibilidade e curiosidade para nomear sentimentos que estão surgindo.",
        "Busca de conexão e expressão afetiva, equilibrando idealização e escuta.",
        "Acolhimento e percepção emocional, preservando os próprios limites.",
        "Maturidade para lidar com sentimentos sem controlar a experiência alheia.",
    ],
    "swords": [
        "Clareza inicial e formulação de uma questão que precisava ser nomeada.",
        "Uma decisão suspensa pede informações e reconhecimento das próprias dúvidas.",
        "Dor emocional e verdades difíceis convidam a cuidado e elaboração.",
        "Pausa mental e recuperação antes de retomar uma conversa ou decisão.",
        "Conflito em que vencer pode custar confiança; examine a forma de discordar.",
        "Transição gradual para condições mais estáveis, levando os aprendizados.",
        "Estratégia e informação incompleta pedem transparência; não afirmar que alguém mente.",
        "Sensação de restrição convida a distinguir limites reais e interpretações.",
        "Preocupações recorrentes pedem acolhimento e verificação dos fatos, sem diagnóstico.",
        "Um encerramento desgastante pode pedir descanso e reconstrução, sem previsão de tragédia.",
        "Investigação e curiosidade, com cuidado para não transformar suposições em certezas.",
        "Ação orientada por uma ideia forte pede escuta e atenção às consequências.",
        "Discernimento e limites claros, conciliando franqueza e sensibilidade.",
        "Critério e responsabilidade no uso de conhecimento, argumentos e autoridade.",
    ],
    "pentacles": [
        "Uma oportunidade material pede avaliação e cuidado para se desenvolver.",
        "Equilíbrio de recursos, tarefas e tempo em condições que podem mudar.",
        "Aprendizado e colaboração, com reconhecimento de competências diferentes.",
        "Busca de segurança pode convidar a distinguir proteção e rigidez.",
        "Dificuldades materiais ou exclusão pedem reconhecer recursos e redes de apoio.",
        "Trocas e ajuda convidam a examinar reciprocidade e assimetrias de poder.",
        "Espera por resultados e avaliação de onde continuar investindo esforço.",
        "Prática, dedicação e aperfeiçoamento gradual de uma habilidade.",
        "Autonomia e cuidado com os frutos do trabalho, sem reduzir valor pessoal à renda.",
        "Continuidade, comunidade e legado material, considerando quem participa dessa segurança.",
        "Curiosidade prática e disposição para aprender algo aplicável.",
        "Constância e compromisso com o processo, atentos ao risco de estagnação.",
        "Cuidado concreto com recursos, corpo e ambiente, preservando limites.",
        "Gestão responsável do que foi construído e atenção ao impacto das escolhas.",
    ],
}
for _card in CARDS:
    if _card["arcana"] == "minor":
        _rank = _card["id"].split("-", 1)[1]
        _index = next(i for i, entry in enumerate(RANKS) if entry[0] == _rank)
        _card["meaning"] = (
            MINOR_MEANINGS[_card["suit"]][_index] + " Leitura simbólica para reflexão."
        )
