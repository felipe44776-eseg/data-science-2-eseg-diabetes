# ADR 0004 — Cost-sensitive learning em vez de SMOTE

**Status:** aceito · **Data:** 2026-08-21

## Contexto
Distribuição do alvo: 84,24% / **1,83%** / 13,93%. A classe pré-diabetes tem 4.631 casos.

## Decisão
Padrão do projeto: **pesos de classe** (`class_weight`, `scale_pos_weight`) + **ajuste de
limiar sobre probabilidade calibrada**. Oversampling sintético entra apenas como ablação
documentada, não como método adotado.

## Justificativa
1. **SMOTE gera registros impossíveis.** 19 das 21 features são binárias ou ordinais de
   baixa cardinalidade. Interpolação em espaço contínuo produz `fumante = 0,63`,
   `escolaridade = 4,2`. O vizinho sintético não existe no espaço amostral real.
2. **Oversampling destrói a calibração.** A probabilidade prevista deixa de corresponder à
   prevalência, o que inviabiliza a análise de decisão (Trilha C), o NNS e o net benefit.
   Se você precisa de probabilidade confiável, não pode reamostrar.
3. **Peso de classe resolve o mesmo problema sem tocar no dado**, e o limiar mantém a
   decisão operacional separada do modelo — que é onde ela deve estar.

## Consequências
- Reportamos a ablação com SMOTE/ADASYN para sustentar a escolha com número, não com opinião.
- Nenhuma reamostragem pode ocorrer antes da partição — teste em CI cobre isso.
