# Contrato HTTP

Disponíveis: GET /api/v1/health, GET /api/v1/health/ready, GET /api/v1/spreads.
OpenAPI publicado em /openapi.json e /docs.

Planejados (não registrados):
- /api/v1/auth: cadastro, login, refresh e logout
- /api/v1/me: perfil e exclusão
- /api/v1/cards: catálogo
- /api/v1/readings: criação idempotente e histórico autenticado
- /api/v1/readings/{id}: resultado autorizado
- /api/v1/readings/{id}/messages: conversa sobre cartas imutáveis
- /api/v1/readings/{id}/events: SSE autorizado e retomável
- /api/v1/journal: notas e favoritos

Especificar schemas e erros ao implementar cada endpoint. Não expor rotas simuladas como funcionais.
