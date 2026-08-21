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
- Um teste em CI garante que nenhum grupo de duplicata cruze a partição.
- Reportamos a métrica com e sem vazamento, para dimensionar o efeito com número.

## Adendo (2026-08-21) — o efeito medido é pequeno

A decisão está mantida, mas a justificativa foi corrigida por medição (`docs/08` §2.1):

| modelo | split aleatório | split por grupo | inflação |
|---|---|---|---|
| gradient boosting | 0,4498 | 0,4494 | +0,09% |
| árvore sem poda | 0,1999 | 0,1993 | +0,3% |
| kNN k=1 | 0,1914 | 0,1890 | +1,2% |

O raciocínio do "Contexto" acima já continha a explicação e não foi seguido até o fim:
como a colisão é **legítima**, a gêmea no treino carrega *um* rótulo da distribuição
conflitante, não o rótulo da linha de teste. Memorizá-la devolve a classe majoritária do
grupo — que é o que um bom modelo preveria de qualquer forma.

**A decisão continua correta**: a partição por grupo é gratuita e é a única defensável por
princípio, e nada garante que o efeito seja pequeno em outro modelo ou outro dataset.
O que muda é a **magnitude alegada**, que estava exagerada.
