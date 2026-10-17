# Arcana Backend 🔮

Fundação da API Python do Arcana, uma experiência de tarot para entretenimento e reflexão.
Frontend: https://github.com/AlePortfolio/arcana-frontend

## Estado atual

Este repositório é um **esqueleto executável**, não um produto completo.
Funcionam: API FastAPI, OpenAPI, CORS, liveness/readiness, catálogo de tipos de tiragem,
sorteio como serviço Python, validação básica de referências, configuração de banco e Alembic.
Autenticação, tabelas de domínio, catálogo das 78 cartas, persistência das tiragens, agentes,
RAG real, chat, SSE e diário **ainda não estão implementados**. Não há chamadas pagas a modelos.
As pastas reservadas documentam o escopo sem simular respostas de produção.

## Executar localmente (Python 3.12+)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

API: http://localhost:8000/docs — frontend local permitido: http://localhost:4200
Liveness: `/api/v1/health`; readiness verifica o banco: `/api/v1/health/ready`.

## Docker (desenvolvimento)

```bash
docker compose up --build -d
docker compose exec api alembic upgrade head
```

Credenciais do Compose são somente locais; configure segredos e infraestrutura próprios para produção.
A migração inicial habilita pgvector, mas não cria tabelas de negócio.

## Verificação

```bash
ruff check .
pytest
```

Consulte [arquitetura](docs/architecture.md), [roadmap](docs/roadmap.md) e
[contrato planejado](docs/api-contract.md). Dependências têm faixas de versão; lockfile e
pinagem das imagens devem ser definidos antes do deploy de produção.
