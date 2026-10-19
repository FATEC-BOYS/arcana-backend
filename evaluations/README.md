# Avaliações automatizadas

O pipeline usa dados **sintéticos**, sem perguntas de usuários reais. São cinco
cenários: trabalho, relacionamento, injeção de prompt, finanças e saúde.

`python -m scripts.evaluate` executa recuperação de evidências (sem chamadas ao modelo)
e verifica cobertura de fontes por carta. Precisa do banco migrado e seed.

`python -m scripts.evaluate --live` executa o LangGraph real com o provedor
configurado e acrescenta uma rubrica determinística para:
- aprovação do revisor;
- IDs de fontes e fatos válidos;
- menção a ao menos uma carta sorteada;
- ausência de expressões proibidas pelo caso (injeção de prompt);
- ausência de algumas expressões de previsão categórica.

São até **20 chamadas pagas de chat** nos cinco casos, além de eventual custo do
provedor. O relatório contém flags, contagens e tokens, **nunca o texto da leitura**.
O comando retorna código 1 se uma checagem falhar. O modo offline é a etapa gratuita
do CI; `--live` é opt-in e não faz parte do CI.

`python -m pytest tests/unit/test_agent_evaluation.py -q` testa com doubles
a orquestração, uma rodada de correção, falhas fechadas para citações inventadas,
rejeição definitiva e isolamento dos dados sensíveis no trace. Sem cobrança de API.

**Limitações:** checagens de texto são heurísticas e podem falhar em ambas as
direções. Aprovação do revisor (outro modelo) não comprova fidelidade semântica,
segurança ou validade das afirmações simbólicas. Antes de publicar, conduza
avaliação humana com uma rubrica estruturada e rode o benchmark em um ambiente
isolado com teto de gastos. Não avalie "acerto do futuro" nem ingira dados
pessoais para benchmarks.
