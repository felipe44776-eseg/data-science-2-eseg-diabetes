# CLAUDE.md — Data Science 2 · Projeto 1 (Diabetes)

Contexto de projeto. Herda de `~/CLAUDE.md` tudo que não estiver aqui.

## Tenant

**ESEG (acadêmico)** — nunca tocar em recurso de cliente a partir deste diretório.

| | |
|---|---|
| Identidade git | `felipe_44776@aluno.eseg.edu.br` |
| Conta gh | `felipe44776-eseg` |
| Repo | `felipe44776-eseg/data-science-2-eseg-diabetes` |
| gcloud config | `eseg` (não utilizada — projeto é local-first, ver ADR 0003) |

Subagente que rode `git`/`gh` aqui deve receber o tenant declarado no prompt.

## Stack

Python 3.11 · pandas · pyarrow · scikit-learn · LightGBM · statsmodels · SHAP · DoWhy.
Parquet + DuckDB. MLflow local (`file:./mlruns`). **Sem GCP** — ver ADR 0003 e o gatilho
que reabriria a decisão.

## Comandos

```powershell
.\tasks.ps1 all      # PDF -> bronze -> silver -> gold -> relatório
.\tasks.ps1 test     # ruff + pytest
```

`PYTHONPATH` aponta para `src/` (já configurado em `tasks.ps1` e `pyproject.toml`).

## Invariantes — não violar

1. **`src/diabetes/schema.py` é a única fonte de verdade** de nome, tipo, domínio e
   semântica de coluna. Nenhum literal de nome de coluna fora dele.
2. **Nenhuma linha é descartada em silêncio.** Toda remoção vai para quarentena com o motivo,
   e toda regra emite contagem no relatório de qualidade.
3. **Nunca `train_test_split` aleatório.** 23.899 duplicatas exatas → vazamento de 13,65%
   do conjunto de teste. Usar `features/split.py` (partição por hash das features). ADR 0002.
4. **Acurácia não é reportada.** PR-AUC, recall @ especificidade, Brier, calibração. ADR 0005.
5. **SMOTE não é o método adotado** — cost-sensitive + ajuste de limiar. ADR 0004.
   SMOTE entra só como ablação para sustentar a escolha com número.
6. **Dado não é versionado; manifesto com hash é.** O PDF fonte (109 MB) fica fora do git.
7. **Notebook não contém lógica** — importa de `src/` e mostra resultado.
8. **`exame_colesterol`, `acesso_saude`, `sem_consulta_por_custo` não são fatores de risco**
   — são marcadores de detecção. Bloco separado, modelo reportado com e sem eles.
9. O alvo mede **diagnóstico autorrelatado**, não a doença. ~27,6% dos diabéticos não sabem
   (NHANES). Qualquer conclusão redigida como "tem diabetes" está errada.

## Estado

Ingestão e limpeza prontas e testadas. Próximo: features → EDA → modelos.
Roteiro completo em `docs/02-proposta-de-analise.md`.
