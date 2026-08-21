# ADR 0002 — Marcar duplicatas, não removê-las na limpeza

**Status:** aceito · **Data:** 2026-08-21

## Contexto
23.899 linhas (9,4%) são idênticas nas 22 colunas. 25.772 são idênticas nas 21 features,
e 1.834 combinações de features aparecem com **alvo divergente** (6.120 linhas).

Com 21 variáveis discretas de baixa cardinalidade e n = 253.680, colisão é matematicamente
esperada: **duas pessoas diferentes podem legitimamente dar as mesmas 21 respostas.**
Não é possível distinguir "registro duplicado por erro" de "dois respondentes idênticos".

## Decisão
A camada de limpeza **marca** (`flag_duplicata_exata`, `flag_alvo_conflitante`) e **não remove**.
A decisão de deduplicar pertence à modelagem, e é tomada por objetivo:

| Objetivo | Tratamento |
|---|---|
| Estimar prevalência | **manter** — remover distorce a distribuição amostral |
| Treinar/avaliar modelo | **particionar por grupo** (`StratifiedGroupKFold`, chave = hash das features) |
| Estimar teto de Bayes | **usar os conflitos** — é justamente o sinal desejado |

## Consequências
- Elimina o vazamento treino/teste que infla o AUC na maioria dos notebooks públicos deste dataset.
- Um teste em CI garante que nenhum grupo de duplicata cruze a partição.
- Reportamos o AUC com e sem vazamento, para dimensionar o efeito com número.
