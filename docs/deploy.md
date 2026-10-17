# Publicar o backend

Requisitos: Python 3.12+, PostgreSQL com pgvector e processos persistentes para workers.
A API e os workers usam o mesmo DATABASE_URL. O worker de geração não roda como função
serverless por requisição. Docker Compose fornece uma instalação de referência.

1. Configure ARCANA_ENV=production, DATABASE_URL, RATE_LIMIT_SECRET aleatório com pelo menos
   32 caracteres, CORS_ORIGINS com o domínio real do frontend e PUBLIC_FRONTEND_URL HTTPS.
2. Configure OPENAI_API_KEY no gerenciador de segredos do host. LLM_MODEL precisa oferecer
   saída estruturada; o modelo de embeddings precisa gerar 1536 dimensões. Nunca envie chaves ao Git.
3. Execute `python -m scripts.bootstrap` uma vez por atualização, após backup do banco existente.
4. Inicie API com `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log` e worker
   com `python -m app.jobs.worker`. Configure reinício automático e encerramento gracioso.
5. Para recuperar senha, configure SMTP_HOST/PORT/USERNAME/PASSWORD/FROM e inicie o worker
   `python -m app.jobs.mail_worker` (ou perfil mail do Compose). Configure a tela de redefinição no frontend.
6. Verifique `/health/ready`, `python -m scripts.doctor`, login e uma leitura com modelo real.
   Doctor verifica configuração/banco, não autentica no provedor. Ausência de chave produz falha explícita.
7. Opcional: `python -m scripts.manage embed` para indexação paga. Reexecute ao trocar o modelo.
8. Agende `python -m scripts.maintenance --apply` diariamente, após conferir o dry run inicial.

Configure TLS no proxy, backups/restauração, orçamento no provedor e monitoramento de
falhas/latência da API e fila. Não grave tokens, perguntas, diário ou respostas em logs.
Preserve Authorization no streaming e permita conexões SSE de até 120 segundos.
Cotas usam UTC, independentemente do fuso do usuário. Retenção operacional está em architecture.md.

Este repositório entrega código e infraestrutura; não provisiona host, domínio, credenciais,
banco gerenciado ou SMTP. A validação com modelos reais e a curadoria aprofundada continuam
etapas de homologação antes de disponibilizar o serviço publicamente.
