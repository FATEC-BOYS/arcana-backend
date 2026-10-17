# Arquitetura

FastAPI + SQLAlchemy/Alembic + PostgreSQL/pgvector + Kerykeion/Swiss Ephemeris + LangGraph.
Monólito modular com API, worker de geração e worker SMTP opcional em processos separados.

## Dados e cálculos

15 tabelas: users, auth_sessions, reset_tokens, mail_outbox, rate_buckets, readings,
birth_charts, messages, journal_entries, jobs, reading_events, knowledge_documents, knowledge_chunks, generation_runs, usage_buckets.
Chaves estrangeiras em cascata removem o conteúdo pessoal ao excluir a conta.
O acervo global é independente. Cálculos natais são snapshots, identificados por versão.

Data/hora local é convertida por zoneinfo para UTC antes de chamar Kerykeion (online=False).
Sistema tropical, Placidus, latitude entre -66 e 66 graus, datas de 1900 até hoje.
Horário desconhecido usa meio-dia local apenas para posições aproximadas: sem casas, ascendente,
aspectos ou SVG. A incerteza acompanha o resultado e o contexto dos agentes. Não há retificação,
geocodificação nem inferência do fuso por coordenada.
O cliente deve fornecer coordenadas e fuso coerentes. fold resolve repetições de horário.
Swiss Ephemeris é serializado por lock no processo devido a estado global. A distribuição
não inclui arquivos externos de efemérides; backend usa fallback analítico Moshier disponível
na biblioteca. Resultados guardam proveniência disponível do Kerykeion. Sem sinastria/trânsitos.

## Agentes e recuperação

Sorteio/cálculo -> snapshot persistido -> job -> recuperação -> intérprete -> revisor.
Máximo: interpretação, revisão, uma correção e revisão final (4 chamadas de chat).
Uma rejeição final falha explicitamente, nunca publica silenciosamente uma leitura rejeitada.
Schemas validam campos; código rejeita source_ids e fact_ids não permitidos. Isso não prova
fidelidade semântica completa: precisa de avaliação humana e com modelos reais.
Metadados sustentam o RAG inicial; embeddings OpenAI + pgvector são opcionais.
Fontes recuperadas e entradas são dados não confiáveis para os agentes.

## Execuções e retomada

POST /readings usa Idempotency-Key por usuário e hash de payload. Reuso com outro payload
retorna 409. Cartas não mudam em retry. Worker usa SKIP LOCKED, lease de 300s e token de posse.
Cada chamada ao modelo tem timeout 30s e sem retry automático do SDK. Histórico limitado.
Após crash, lease expirado pode ser retomado; processamento é at-least-once e pode repetir
custo de modelo se houver crash após a chamada externa. Token de posse evita publicação velha.
Até 3 tentativas automáticas por job; retry manual de leitura limitado pelo total de tentativas.
Eventos persistidos são de estado, sem raciocínio interno. Resultado é consultado por GET.

## Segurança e operação

Tokens opacos de alta entropia, somente hashes no banco; senhas Argon2. Autorização por
proprietário em cada recurso. Rate limit de autenticação por IP com hash HMAC. Limites de
leituras, mapas e mensagens por dia UTC; mensagens também têm limite por tiragem.
Cotas persistem após exclusão de recursos e são reservadas sob lock por usuário. Configure proxy confiável explicitamente.
Cache-Control no-store e validações sem eco de valores de senha/dados privados.
Sem logs de acesso no comando Docker; não adicionar prompts/diário aos logs.
Recuperação usa outbox com conteúdo privado temporário, apagado no envio ou expiração.
É necessária retenção operacional, TLS, backups, configuração de segredos e revisão de
segurança antes de uso público. Custo monetário não é calculado automaticamente: registramos
tokens/modelo; preços variam. Configure orçamento também no provedor.

## Integridade e documentos (migração 0003)

Reading.chart_id tem FK composta com user_id para o mapa do mesmo proprietário.
Snapshots JSON são mantidos. O endpoint de exclusão de mapa rejeita mapas ainda vinculados a leituras (409).
Excluir a conta remove todos os dados pessoais em cascata.
A migração preenche chart_id apenas quando o mapa existe e tem o proprietário correto.
Snapshots legados sem mapa continuam consultáveis, com chart_id nulo.

KnowledgeDocument agrupa source, topic, version, license, content_hash e active.
Chunk referencia o documento e possui posição única nele; embeddings existentes são mantidos.
Uma versão é imutável. Nova versão desativa as anteriores na busca; não apaga trechos antigos.
O índice parcial garante uma única versão ativa por fonte/tópico. A recuperação expõe
document_id, versão e licença junto da fonte. Resultados históricos guardam texto e referências.

A migração 0003 deve executar online: agrupa trechos legados por fonte/tópico/versão,
preserva seus IDs e vetores e escolhe a maior versão por ordenação natural como ativa.
Fontes com licenças conflitantes na mesma versão exigem correção prévia: não são mescladas
silenciosamente. Imports legados que perderam ordem de documento podem exigir nova versão
ao reimportar. Downgrade restaura metadados nos chunks; o conceito de versão ativa deixa de existir.

## Operação e migração 0004

Mensagens possuem sequência única por leitura e retry individual. Jobs temporariamente
indisponíveis voltam à fila com available_at/backoff; erros de autenticação/configuração
falham explicitamente. GenerationRun relaciona leitura e mensagem, estado/erro, modelo,
versão de prompt, modo de recuperação, tokens de chat e embeddings separadamente.
A migração ordena mensagens legadas por created_at/id e preenche cotas pelo dia original.
Vetores legados não recebem modelo presumido: somente vetores do modelo configurado
participam da busca semântica; o restante continua disponível por metadados.

A limpeza operacional é manual/agendável via scripts.maintenance: sessões/reset tokens
expirados, outbox antiga, rate buckets antigos, cotas com mais de 90 dias e eventos com
mais de 30 dias. Leituras, mensagens, mapas, execuções e diário permanecem até exclusão
pelo proprietário. SSE não promete replay além da retenção; GET é a fonte do resultado.
