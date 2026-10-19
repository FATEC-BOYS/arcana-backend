# Executores de avaliação

A validação determinística está em `app/ai/evaluation.py` e é usada por
`scripts/evaluate.py --live`. Os testes de contrato estão em
`tests/unit/test_agent_evaluation.py` e rodam offline no CI.

Para métricas agregadas de execuções do worker:
`python -m scripts.observability --days 7`.

Não registrar prompts, respostas, fontes textuais, segredos ou identificadores
de usuários nos registros de observabilidade.
