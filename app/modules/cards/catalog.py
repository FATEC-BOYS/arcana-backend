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
