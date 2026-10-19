# Arcana — AI quality engineering

O Arcana possui **57 casos sintéticos** em duas suítes versionadas: 43 de tarot
e 14 de astrologia. O objetivo é testar regras, resistência adversarial e
limitações declaradas, **não provar previsões, diagnósticos ou interpretações
semanticamente corretas**. Não usar perguntas pessoais em benchmarks.

## Etapa 1 — execução offline, gratuita e obrigatória no CI

```bash
python -m scripts.bootstrap
python -m scripts.evaluate --output /tmp/arcana-offline.json
python -m pytest tests/unit/test_evaluation_pipeline.py -q
```

Valida o esquema e checksum SHA-256 dos datasets, IDs de cartas e planetas,
cobertura das fontes recuperadas, categorias e regressões estruturais.
São **zero chamadas à OpenAI** nesta etapa. O relatório inclui resumo por
suíte/categoria, casos aprovados e contadores, sem perguntas ou respostas.

## Etapa 2 — benchmark live, exige orçamento explícito

```bash
python -m scripts.evaluate --live --suite tarot --max-cases 2 --max-calls 8 \
  --output /tmp/arcana-live.json
```

Sem ambos os limites, a avaliação paga **não inicia**. Cada caso exige reservar
até quatro chamadas de chat (interpretação, revisão e uma correção/revisão).
`--suite tarot|astrology|all` seleciona a suíte e `--max-cases` restringe
o total. Para executar os 57 casos completos, é necessário autorizar
explicitamente `--max-cases 57 --max-calls 228`; **não** faça isso sem
aprovar custos e validar credenciais e políticas de gasto no provedor.

O benchmark usa o orquestrador LangGraph real. Avalia aprovação do revisor,
integridade de fontes/fatos, referências aos símbolos e heurísticas para
injeção/linguagem determinista. Essas heurísticas podem gerar falsos positivos
e falsos negativos.

## Etapa 3 — juiz LLM opcional, mais caro e subjetivo

```bash
python -m scripts.evaluate --live --judge --suite astrology \
  --max-cases 2 --max-calls 10 --judge-model SEU_MODELO_AVALIADOR \
  --output /tmp/arcana-judged.json
```

O juiz usa a rubrica `app/ai/judge.py` (fidelidade, segurança, autonomia,
utilidade, resistência à injeção) com notas estruturadas de 0 a 4,
flags predefinidas e encaminhamento para revisão humana. O modelo avaliador
pode ser diferente do modelo gerador para reduzir parte do viés, mas **não
substitui avaliadores independentes**. O teto sobe para **cinco** chamadas
por caso, incluindo o juiz. Não existe chamada automática a modelos pagos
no CI ou no worker de produção.

## Etapa 4 — comparação e regressão

```bash
python -m scripts.evaluate --live --suite tarot \
  --max-cases 2 --max-calls 8 --baseline /tmp/arcana-live.json \
  --min-pass-rate 0.95 --output /tmp/arcana-candidate.json
```

`--baseline` exige hash idêntico de dataset, modo e mesmos `case_id`s,
bloqueando comparação de conjuntos incompatíveis. O relatório marca
casos anteriormente aprovados que falharam. Mudanças de modelo/prompt devem
ser registradas nas propriedades do relatório e interpretadas na revisão humana.

## Telemetria operacional e SLOs

```bash
python -m scripts.observability --days 7
python -m scripts.observability --days 7 --min-runs 20 \
  --min-completion-rate 0.95 --max-p95-ms 60000 --fail-on-breach
```

O relatório agrega taxas de conclusão, erro, duração p50/p95/p99,
resultados de revisões, tokens e chamadas por etapa, dia e modelo. Sem
amostras suficientes, o SLO é reportado como `insufficient_data`;
`--fail-on-insufficient-data` define saída 2 nesse estado.

## Governança

- Checkpoints em `generation_runs.trace` contêm somente números e rótulos
  limitados; nunca prompts, respostas, fontes ou IDs pessoais.
- Relatórios de benchmark se referem somente a fixtures sintéticas.
- `--live` e `--judge` requerem consentimento explícito e orçamento.
- O modelo avaliador é falível; nenhuma nota é atestado científico de tarot
  ou astrologia.
- Consulte [rubrica humana](human_review_rubric.md) para calibração, revisão
  independente e critérios de liberação ainda **não comprovados**.
