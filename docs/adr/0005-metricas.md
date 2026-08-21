# ADR 0005 — Acurácia banida; PR-AUC + calibração como métricas primárias

**Status:** aceito · **Data:** 2026-08-21

## Contexto
Responder sempre "sem diabetes" produz **84,24% de acurácia**. Qualquer número próximo
disso é indistinguível de não ter modelo nenhum.

## Decisão
Acurácia **não é reportada** no relatório final. Hierarquia adotada:

| Prioridade | Métrica | Papel |
|---|---|---|
| 1 | **PR-AUC** (one-vs-rest por classe) | discriminação sob desbalanceamento severo |
| 2 | **Recall @ especificidade 90%** | leitura operacional de rastreamento |
| 3 | **Brier + curva de calibração** | a probabilidade é utilizável para decisão? |
| 4 | **Net benefit** (curva de decisão) | usar o modelo é melhor que não usar? |
| 5 | Log-loss | função de otimização |
| — | ROC-AUC | só para comparabilidade com a literatura |
| — | ~~Acurácia~~ | **não reportada** |

## Consequências
- Calibração (Platt/isotônica em fold separado) passa a ser etapa obrigatória do pipeline.
- Toda comparação de modelo usa a mesma partição congelada em `data/processed/gold/folds.parquet`.
