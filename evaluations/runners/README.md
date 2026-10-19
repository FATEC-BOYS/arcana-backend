# Runners

- `scripts/evaluate.py`: dataset SHA-256, tarot + astrologia, casos adversariais,
  benchmark pago explicitamente limitado, rubrica, relatórios e comparação.
- `app/ai/evaluation.py`: verificações determinísticas, diagnósticas.
- `app/ai/judge.py`: avaliador opcional estruturado de cinco dimensões.
- `app/ai/observability.py`: spans por etapa sem entrada/saída de usuário.
- `scripts/observability.py`: métricas agregadas e SLOs por janela.
- `tests/unit/test_evaluation_pipeline.py`: limites de gasto e regressões.
- `tests/unit/test_observability_slo.py`: comportamento com poucos dados e falhas.

O CI roda somente o modo offline com fixtures sintéticas. Análises qualitativas
precisam de avaliadores humanos independentes e auditoria de confiabilidade real.
