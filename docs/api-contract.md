# API v1

OpenAPI autoritativo: /openapi.json; documentação interativa: /docs.
Todos os recursos pessoais exigem Authorization: Bearer ACCESS_TOKEN.

| Rota | Operações |
|---|---|
| /health, /health/ready | GET liveness e banco |
| /cards, /cards/{id} | GET catálogo e detalhes |
| /spreads | GET tipos de tiragem |
| /auth/register, /auth/login | POST email/password (mín. 10), register também name |
| /auth/refresh | POST refresh_token |
| /auth/logout | POST revoga todas as sessões |
| /auth/forgot-password | POST email; SMTP necessário |
| /auth/reset-password | POST token/password, revoga sessões |
| /me | GET, PATCH name, DELETE conta |
| /astrology/charts | POST nascimento, GET histórico |
| /astrology/charts/{id} | GET mapa do proprietário |
| /readings | POST (202), GET histórico |
| /readings/{id} | GET snapshot/estado/resultado |
| /readings/{id}/retry | POST falha sem novo sorteio |
| /readings/{id}/messages | POST (202), GET mensagens |
| /readings/{id}/events | GET SSE com Last-Event-ID |
| /journal | GET notas; favorites_only opcional |
| /journal/{reading_id} | PUT note/favorite |

POST /readings: Idempotency-Key header obrigatório (8–128 caracteres).
Tarot: {"kind":"tarot","question":"Como refletir sobre trabalho?","spread":"three_cards",
"allow_reversed":true}. Astrology: {"kind":"astrology","question":"Como explorar meu mapa?",
"chart_id":"UUID"}. Mapas são calculados por POST /astrology/charts com birth_date,
birth_time, latitude, longitude, timezone (IANA) e fold opcional.

POST messages exige Idempotency-Key próprio e {"question":"..."}. Uma geração ativa por leitura.
GET/POST de leitura também retornam chart_id (nulo para tarot).
Estados: pending, processing, completed, failed. Resultado inclui summary, reflections,
source_ids, fact_ids, sources, prompt_version, retrieval_mode e reviewed.

401: sessão ausente/expirada; 404: inexistente ou não pertence ao usuário;
409: conflito de idempotência/estado; 422: entrada inválida; 429: limite; 503: dependência ausente.
Falha de job é consultada no recurso e eventos. Eventos não contêm o resultado integral.
