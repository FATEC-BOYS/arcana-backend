# Arquitetura

Monólito modular Python: FastAPI, SQLAlchemy/Alembic, PostgreSQL/pgvector e fluxo LangGraph planejado.
Módulos contêm rotas, schemas, modelos, serviço e repositório conforme forem implementados.
O catálogo das cartas é separado do acervo interpretativo e dos vetores.

## Fluxo planejado

Validar pergunta -> persistir tiragem única -> recuperar evidências -> interpretar -> revisar
-> até uma correção -> persistir resultado. Sorteio e autorização são código determinístico
fora dos agentes. A seleção usa SystemRandom; não repetir o sorteio em retomadas.

Persistir Reading, DrawnCard, Message, JournalEntry, Document, Chunk, GenerationRun e User.
Cada leitura pertence a um usuário. Toda consulta privada deve filtrar o proprietário.
Estados: pending, processing, completed, failed. Idempotency-Key deve ter restrição única
por usuário e operação. Execuções longas exigem job durável, não somente BackgroundTasks.

## Operação e privacidade

SSE transmite eventos de progresso e resultado, sem raciocínio interno do modelo.
Guardar versões de prompt/modelo/acervo, tokens, latência e custos. Não logar perguntas,
diário nem credenciais. Implementar retenção e exclusão antes de aceitar dados reais.
Documentos recuperados são dados não confiáveis, nunca instruções para executar ferramentas.

## Limites

Autenticação, worker durável e provedor LLM ainda serão implementados.
Sem endpoints privados provisórios ou autenticação fictícia.
