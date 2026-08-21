# ADR 0001 — Ingestão do PDF por coordenada, não por ordem de leitura

**Status:** aceito · **Data:** 2026-08-21

## Contexto
Os dados chegaram como `Diabetes-2026.csv.pdf`: 109 MB, 4.374 páginas, um CSV renderizado
como tabela. A especificação PDF **não garante** que a ordem dos tokens no fluxo de texto
corresponda à ordem visual. `pdftotext`, `get_text()` e afins podem embaralhar colunas em
qualquer página, silenciosamente.

## Decisão
Reconstruir cada linha a partir da **bounding box** de cada palavra
(`PyMuPDF get_text("words")`): agrupar por baseline `y0` (tolerância 2 pt), ordenar por `x0`.
Validar cardinalidade (22 tokens) e parseabilidade numérica em toda linha.
Linha que falhar vai para quarentena com página, linha e motivo — **nunca é descartada em silêncio**.

## Consequências
- 253.680 linhas reconstruídas, **0 em quarentena**, batendo exatamente com o enunciado.
- Manifesto com SHA-256 do PDF de entrada e do CSV de saída → reprodutibilidade verificável.
- Custo: 48,6 s de processamento. Irrelevante, roda uma vez.

## Alternativas descartadas
- **Pedir o CSV ao professor.** Correto de fazer em paralelo, mas não pode ser dependência:
  o projeto tem de rodar com o que foi entregue.
- **`tabula`/`camelot`.** Feitos para tabelas com bordas e heurística de layout; aqui a
  geometria é regular e conhecida, então a solução direta é mais robusta e mais rápida.
