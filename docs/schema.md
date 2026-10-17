# Modelo de dados — Arcana

14 entidades. Esquema definido em app/db/models.py, aplicado pelas migrações Alembic.

```mermaid
erDiagram
    USER ||--o{ BIRTH_CHART : possui
    USER ||--o{ READING : consulta
    BIRTH_CHART o|--o{ READING : fundamenta
    READING ||--o{ MESSAGE : conversa
    READING ||--o| JOURNAL_ENTRY : registra
    READING ||--o{ JOB : processa
    READING ||--o{ EVENT : publica
    READING ||--o{ GENERATION_RUN : acompanha
    KNOWLEDGE_DOCUMENT ||--o{ CHUNK : contem
```

Reading.chart_id/user_id referencia BirthChart.id/user_id: não admite mapa de outro usuário.
Snapshots ficam em Reading.facts. Chart_id pode ser nulo em tarot ou em registros legados
cujo mapa já não exista; novos pedidos astrológicos exigem mapa válido.

KnowledgeDocument identifica uma versão de fonte/tópico, com licença e hash do conteúdo.
Chunk tem documento obrigatório e posição única. Versões antigas mantêm seus trechos e
vetores; apenas a versão ativa participa da busca. A ingestão rejeita mudanças na mesma
versão. Citações históricas continuam armazenadas com seu texto na interpretação.

AuthSession, ResetToken, Mail e RateBucket completam as 14 entidades de infraestrutura.
Cartas permanecem no catálogo em código e são copiadas no snapshot da tiragem.
