"""Trilha C — escore de pontos inteiros, aplicavel em papel.

Motivo da decisao
-----------------
`docs/08` §4 mediu que **cinco variaveis entregam 89,2%** do modelo de 21, e
`docs/13` que o EBM de 12 variaveis entrega 94,4% do boosting de 60. Se o ganho
de um modelo complexo e de poucos pontos percentuais, o entregavel correto e o
que roda numa unidade basica de saude **sem computador**.

E o formato consagrado: FINDRISC (Lindstrom & Tuomilehto, 2003) e o ADA Diabetes
Risk Test sao escores de pontos inteiros preenchidos a mao.

Como os pontos sao construidos
------------------------------
1. logistica ponderada nas variaveis do escore, com faixas (nao termos lineares)
   — as faixas vem dos limiares clinicos e da funcao de forma do EBM;
2. cada coeficiente e dividido pelo menor coeficiente positivo e arredondado,
   o que produz pontos inteiros preservando a razao entre efeitos;
3. a soma de pontos e mapeada de volta para risco **observado** por faixa, o que
   recalibra o arredondamento — o escore nao herda o erro da discretizacao.

Duas versoes, e a diferenca e um resultado
------------------------------------------
  **A · completo** — inclui `colesterol_alto`, que exige ter feito exame
  **B · sem proxy de acesso** — so variaveis respondiveis por quem nunca viu medico

`docs/05` mostrou que o arquivo entregue e enviesado para quem tem acesso. Um
escore que exige exame previo **nao alcanca** a populacao que `docs/12` mostrou
ser a mais invisivel. Medir quanto custa retirar essa variavel e a pergunta.

Uso:
    python -m diabetes.eval.escore
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import average_precision_score, roc_auc_score

from diabetes.models.expandido import particionar
from diabetes.pipeline.estado import registrar

ENTRADA = Path("data/processed/gold/brfss_expandido.parquet")
SEED = 42


# --------------------------------------------------------------------------
# faixas — limiares clinicos, nao quantis
# --------------------------------------------------------------------------

def _faixas(df: pd.DataFrame) -> pd.DataFrame:
    """Discretiza em faixas que um formulario de papel consegue perguntar."""
    d = pd.DataFrame(index=df.index)
    idade = df["_AGE80"].astype(float)
    imc = df["_BMI5"].astype(float) / 100

    # idade: cortes de rastreamento (ADA recomenda a partir de 35/45)
    d["idade"] = pd.cut(idade, [0, 35, 45, 55, 65, 200],
                        labels=["<35", "35-44", "45-54", "55-64", "65+"], right=False)
    # IMC: faixas da OMS
    d["imc"] = pd.cut(imc, [0, 25, 30, 35, 100],
                      labels=["<25", "25-29", "30-34", "35+"], right=False)
    # saude autoavaliada: 1-5 -> 3 niveis (o formulario nao precisa de 5)
    d["saude"] = pd.cut(df["GENHLTH"].astype(float), [0, 2, 3, 5],
                        labels=["excelente/muito boa", "boa", "regular/ruim"])
    d["hipertensao"] = df["_RFHYPE5"].map({1.0: "nao", 2.0: "sim"})
    d["colesterol"] = df["TOLDHI2"].map({2.0: "nao", 1.0: "sim"})
    d["sexo"] = df["SEX"].map({1.0: "masculino", 2.0: "feminino"})
    return d


#: referencia de cada faixa = o nivel de MENOR risco, que vale 0 ponto
REFERENCIA = {"idade": "<35", "imc": "<25", "saude": "excelente/muito boa",
              "hipertensao": "nao", "colesterol": "nao", "sexo": "feminino"}

VARS_A = ["idade", "imc", "saude", "hipertensao", "colesterol", "sexo"]
VARS_B = ["idade", "imc", "saude", "hipertensao", "sexo"]   # sem proxy de acesso


def ajustar(df: pd.DataFrame, faixas: pd.DataFrame, variaveis: list[str],
            treino: np.ndarray) -> tuple[pd.Series, pd.DataFrame]:
    """Logistica ponderada em variaveis categoricas; devolve coeficientes."""
    d = faixas[variaveis].copy()
    for c in variaveis:
        d[c] = d[c].cat.reorder_categories(
            [REFERENCIA[c], *[x for x in d[c].cat.categories if x != REFERENCIA[c]]]
        ) if hasattr(d[c], "cat") else d[c]
    X = pd.get_dummies(d, drop_first=False).astype(float)
    # remove a coluna de referencia de cada variavel
    for c in variaveis:
        col = f"{c}_{REFERENCIA[c]}"
        if col in X:
            X = X.drop(columns=col)
    X = sm.add_constant(X, has_constant="add")

    y = df["diabetes"].astype(int)
    w = df["_LLCPWT"].astype(float)
    ok = X.notna().all(axis=1) & treino
    ww = w[ok].to_numpy()
    ww = ww * (len(ww) / ww.sum())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = sm.GLM(y[ok], X[ok], family=sm.families.Binomial(),
                     freq_weights=ww).fit()
    return res.params, X


def pontos_inteiros(coef: pd.Series, variaveis: list[str]) -> dict:
    """Divide pelo menor coeficiente positivo e arredonda -> pontos inteiros."""
    b = coef.drop(index="const", errors="ignore")
    positivos = b[b > 0]
    unidade = positivos.min() if len(positivos) else 1.0
    tabela: dict[str, dict[str, int]] = {}
    for v in variaveis:
        tabela[v] = {REFERENCIA[v]: 0}
        for k, val in b.items():
            if k.startswith(f"{v}_"):
                tabela[v][k[len(v) + 1:]] = int(round(val / unidade))
    return {"unidade_logit": float(unidade), "pontos": tabela}


def aplicar(faixas: pd.DataFrame, tabela: dict, variaveis: list[str]) -> pd.Series:
    total = pd.Series(0.0, index=faixas.index)
    for v in variaveis:
        mapa = tabela["pontos"][v]
        total = total.add(faixas[v].astype(str).map(mapa), fill_value=np.nan)
    return total


def calibrar(pontos: pd.Series, y: pd.Series, w: pd.Series,
             treino: np.ndarray, n_faixas: int = 8) -> dict:
    """Mapeia soma de pontos -> risco OBSERVADO, recalibrando o arredondamento."""
    ok = pontos.notna() & treino
    cortes = np.unique(np.quantile(pontos[ok], np.linspace(0, 1, n_faixas + 1)))
    cortes[0], cortes[-1] = -np.inf, np.inf
    faixa = pd.cut(pontos, cortes, labels=False, include_lowest=True)
    tab = []
    for f in sorted(faixa[ok].dropna().unique()):
        m = ok & (faixa == f)
        risco = float(np.average(y[m], weights=w[m]))
        tab.append({
            "faixa": int(f),
            "pontos_min": int(pontos[m].min()), "pontos_max": int(pontos[m].max()),
            "risco_%": round(risco * 100, 2),
            "n_treino": int(m.sum()),
        })
    return {"cortes": [float(c) for c in cortes], "faixas": tab}


def risco_do_escore(pontos: pd.Series, cal: dict) -> pd.Series:
    faixa = pd.cut(pontos, cal["cortes"], labels=False, include_lowest=True)
    mapa = {f["faixa"]: f["risco_%"] / 100 for f in cal["faixas"]}
    return faixa.map(mapa)


# --------------------------------------------------------------------------
# FINDRISC aproximado, para comparacao
# --------------------------------------------------------------------------

def findrisc(df: pd.DataFrame) -> pd.Series:
    """FINDRISC com as variaveis que o BRFSS 2015 permite.

    O original tem 8 itens; o BRFSS nao tem circunferencia abdominal, historico
    familiar nem glicemia elevada previa. Reproduzimos os 5 possiveis com a
    pontuacao publicada — e a ausencia dos outros 3 e reportada como limitacao,
    nao escondida.
    """
    idade = df["_AGE80"].astype(float)
    imc = df["_BMI5"].astype(float) / 100
    p = pd.Series(0.0, index=df.index)
    p += np.select([idade < 45, idade < 55, idade < 65], [0, 2, 3], default=4)
    p += np.select([imc < 25, imc < 30], [0, 1], default=3)
    p += (df["_TOTINDA"] == 2).astype(float) * 2            # sem atividade fisica
    p += (df["_FRTLT1"] == 0).astype(float) * 1             # sem fruta diaria
    p += (df["_RFHYPE5"] == 2).astype(float) * 2            # medicacao/pressao alta
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, default=ENTRADA)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_trilhaC_escore.json"))
    args = ap.parse_args()

    df = pd.read_parquet(args.entrada)
    te = particionar(df)
    tr = ~te
    faixas = _faixas(df)
    y, w = df["diabetes"].astype(int), df["_LLCPWT"].astype(float)
    registrar("escore", "inicio", n=len(df))
    print(f"  n={len(df):,}  treino={tr.sum():,}  holdout={te.sum():,}")

    # AMOSTRA COMUM de avaliacao: as duas versoes e o FINDRISC medidos nas MESMAS
    # linhas. Sem isto, o escore A (que exige colesterol nao-nulo) seria comparado
    # numa amostra ja filtrada por acesso -- o proprio vies que o projeto combate.
    comum = te.copy()
    for v in set(VARS_A) | set(VARS_B):
        comum &= faixas[v].notna().to_numpy()
    for c in ("_AGE80", "_BMI5", "_TOTINDA", "_FRTLT1", "_RFHYPE5"):
        comum &= df[c].notna().to_numpy()
    print(f"  amostra comum de avaliacao: {comum.sum():,} de {te.sum():,} do holdout")

    resultados = {}
    for nome, variaveis in (("A_completo", VARS_A), ("B_sem_proxy_acesso", VARS_B)):
        coef, _ = ajustar(df, faixas, variaveis, tr)
        tab = pontos_inteiros(coef, variaveis)
        pts = aplicar(faixas, tab, variaveis)
        cal = calibrar(pts, y, w, tr)
        risco = risco_do_escore(pts, cal)

        ok = risco.notna().to_numpy() & comum
        m = {
            "roc_auc": round(float(roc_auc_score(y[ok], risco[ok])), 4),
            "pr_auc": round(float(average_precision_score(y[ok], risco[ok])), 4),
            "pontos_min": int(pts.min()), "pontos_max": int(pts.max()),
            "n_variaveis": len(variaveis),
            "n_avaliacao": int(ok.sum()),
        }
        resultados[nome] = {"variaveis": variaveis, "tabela": tab,
                            "calibracao": cal, "metricas": m}
        print(f"\n  === ESCORE {nome} ({len(variaveis)} perguntas, "
              f"{m['pontos_min']}-{m['pontos_max']} pontos) ===")
        print(f"    ROC-AUC {m['roc_auc']:.4f}   PR-AUC {m['pr_auc']:.4f}")
        for v in variaveis:
            itens = ", ".join(f"{k}={p:+d}" for k, p in
                              sorted(tab["pontos"][v].items(), key=lambda x: x[1]))
            print(f"    {v:14} {itens}")

    # FINDRISC aproximado
    fr = findrisc(df)
    ok = fr.notna().to_numpy() & comum
    m_fr = {
        "roc_auc": round(float(roc_auc_score(y[ok], fr[ok])), 4),
        "pr_auc": round(float(average_precision_score(y[ok], fr[ok])), 4),
        "n_avaliacao": int(ok.sum()),
        "itens_disponiveis": 5, "itens_originais": 8,
        "ausentes": ["circunferencia abdominal", "historico familiar",
                     "glicemia elevada previa"],
    }
    print("\n  === FINDRISC aproximado (5 de 8 itens) ===")
    print(f"    ROC-AUC {m_fr['roc_auc']:.4f}   PR-AUC {m_fr['pr_auc']:.4f}")

    a, b = resultados["A_completo"]["metricas"], resultados["B_sem_proxy_acesso"]["metricas"]
    comparacao = {
        "custo_de_remover_o_proxy_de_acesso": {
            "roc_auc_A": a["roc_auc"], "roc_auc_B": b["roc_auc"],
            "perda_roc_milesimos": round((a["roc_auc"] - b["roc_auc"]) * 1000, 1),
            "perda_pr_auc_%": round((1 - b["pr_auc"] / a["pr_auc"]) * 100, 2),
        },
        "vs_findrisc": {
            "escore_B_roc": b["roc_auc"], "findrisc_roc": m_fr["roc_auc"],
            "ganho_milesimos": round((b["roc_auc"] - m_fr["roc_auc"]) * 1000, 1),
        },
    }
    print("\n  === COMPARACAO ===")
    print(json.dumps(comparacao, ensure_ascii=False, indent=2))

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(
        {"escores": resultados, "findrisc": m_fr, "comparacao": comparacao},
        ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    registrar("escore", "fim")



if __name__ == "__main__":
    main()
