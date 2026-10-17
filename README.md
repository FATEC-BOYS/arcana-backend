# Arcana Backend 🔮

API Python para tarot e astrologia natal com persistência, RAG e agentes.
Frontend: https://github.com/FATEC-BOYS/arcana-frontend
Licença: AGPL-3.0-or-later; consulte LICENSE e NOTICE.md.

Versão 0.3.0 — escopo V1 implementado; homologação externa depende da configuração abaixo.

## Implementado

- Cadastro/login, tokens opacos, refresh rotativo, logout global, perfil e exclusão em cascata.
- Recuperação de senha por token de uso único + outbox SMTP (opcional).
- Catálogo autoral de 78 cartas e sorteio sem repetição com inversões opcionais.
- Tiragens persistidas e idempotentes: carta diária ou três cartas.
- Mapas natais calculados offline com Kerykeion 6.0.4 + Swiss Ephemeris.
- Validação de fuso IANA, horários inexistentes/ambíguos e coordenadas; SVG e horário desconhecido.
- Interpretação e revisão com LangGraph, até uma correção, JSON estruturado e citações verificadas.
- Fila durável em PostgreSQL com lease, retomada e bloqueio de resultados de workers antigos.
- Chat contextual, fontes, diário/favoritos, SSE retomável, limites por usuário.
- Documentos versionados e trechos de RAG com FK, licença e versão ativa única.
- Acervo introdutório original, ingestão CLI e embeddings opcionais em pgvector.
- Histórico técnico de modelo/prompt, tokens, chamadas e duração, sem conteúdo nos logs.

## Executar com Docker

```bash
cp .env.example .env
docker compose up --build -d
```

O serviço init executa migrações e seed; depois API e worker iniciam.
API: http://localhost:8000/docs. Sem OPENAI_API_KEY, cálculos e sorteios funcionam,
mas a interpretação assíncrona termina com `llm_not_configured`. Nenhuma leitura fictícia
é apresentada como real. Após configurar a chave/reiniciar worker, use o endpoint retry.

## Sem Docker (Python 3.12+)

Swiss Ephemeris pode exigir compilador C/C++ no sistema para instalar pyswisseph.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
cp .env.example .env
python -m scripts.bootstrap
uvicorn app.main:app --reload --no-access-log
```

Em outro terminal, com o mesmo ambiente: `python -m app.jobs.worker`.
PostgreSQL + extensão pgvector são necessários para o uso normal. SQLite é usado somente
nos testes rápidos; locks e busca vetorial de produção são exercitados no CI PostgreSQL.

## RAG

`python -m scripts.manage seed` adiciona acervo curto, original e introdutório.
Por padrão a recuperação usa tags das cartas/planetas, sem chamadas de embeddings.
`python -m scripts.manage embed` usa a chave OpenAI para gerar embeddings de 1536 dimensões
para o acervo; PostgreSQL passa a usar similaridade cosseno. Há custo de API.
O modelo de embeddings deve permanecer o mesmo entre ingestão e consulta.

Importação: `python -m scripts.manage ingest caminho/documento.json`.
Schema: source, version, license, topic (`tarot`/`astrology`), tags e text.
Não importe material sem direito de uso. Não há upload público para o acervo global.

## Autenticação / frontend

Bearer token no header Authorization; access expira em 15 min, refresh em 30 dias.
O refresh rotaciona ambos. Logout revoga todas as sessões. Não colocar tokens em URLs.
SSE usa fetch streaming com Authorization e Last-Event-ID, não EventSource nativo.
Cada conexão dura no máximo 120s; reconectar e buscar o recurso para obter o resultado.
Cadastrar SMTP e executar `docker compose --profile mail up -d` para recuperação de senha.
O frontend ainda precisa implementar consumo do token do fragmento /redefinir-senha#token=...

## Verificação

```bash
python -m ruff check .
python -m pytest -q
```

Testes de modelo usam doubles explícitos, sem gasto e sem testar a qualidade de um modelo real.
Os testes astrológicos calculam posições reais. CI também aplica migrações e testa PostgreSQL.
Leia docs/architecture.md, docs/api-contract.md e docs/roadmap.md antes de publicar.

## Evolução do banco

A migração 0003 liga leituras aos mapas do mesmo usuário e normaliza documentos do RAG.
A 0004 acrescenta cotas persistentes, sequência de mensagens, retomada de jobs e proveniência dos vetores.
Em instalações existentes: `python -m scripts.bootstrap` aplica migrações e seed idempotente.
Preserva snapshots, IDs de trechos e embeddings. Faça backup antes de atualizar um banco com dados.
O backfill exige conexão online; fontes com versões precisam seguir a política em docs/architecture.md.

## Operação da V1

Consulte [deploy.md](docs/deploy.md) para configurar API, worker, banco e SMTP.
`GET /capabilities` informa recursos configurados, sem expor segredos; `GET /me/usage`
informa cotas por dia UTC. Excluir uma leitura não devolve cota. Retentativas manuais
consomem cota; retentativas automáticas respeitam MAX_JOB_ATTEMPTS e usam backoff.

```bash
python -m scripts.doctor
python -m scripts.evaluate
python -m scripts.maintenance
# Aplica a limpeza, após revisar o dry run:
python -m scripts.maintenance --apply
python -m scripts.openapi
```

Doctor não chama o provedor: configuração presente não comprova credencial válida.
Evaluate padrão verifica recuperação em três casos sintéticos; `--live` faz chamadas pagas
explicitamente e ainda exige revisão humana. Contratos HTTP do SDK usam transporte mockado nos testes.
Embeddings antigos sem identificação do modelo são preservados e ignorados na similaridade;
execute `scripts.manage embed` para reindexar com o modelo configurado. O seed v2 contém
215 trechos introdutórios autorais, mantendo referências das versões anteriores.
