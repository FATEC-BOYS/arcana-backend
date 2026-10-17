# Avaliações

`python -m scripts.evaluate` verifica recuperação de evidências em três casos sintéticos
(trabalho, relacionamento e instrução maliciosa na pergunta), sem chamadas de modelo.
Exige banco migrado e seed. O relatório mede cobertura das cartas e quantidade de fontes.

`python -m scripts.evaluate --live` executa intérprete/revisor no provedor configurado:
até 12 chamadas pagas de chat, com validação de schema, citações e revisão. Tokens são
reportados; o comando não calcula preço nem comprova qualidade semântica ou científica.
Não execute com conteúdo pessoal. Os testes automatizados usam doubles e HTTP mockado.

Próxima etapa: aumentar dataset, rubricar fidelidade às evidências, resistência a instruções
maliciosas, consistência de conversa e utilidade. Comparar sem RAG/com RAG e agente único/revisor
com avaliação humana. Não medir “acerto do futuro”.
