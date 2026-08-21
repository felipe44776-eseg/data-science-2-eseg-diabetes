"""Frente 1 — quanto as variaveis recuperadas valem, e para quem.

Tres perguntas, nesta ordem:

  1. **Quanto ganha?** 21 originais vs. 69 curadas, mesmo protocolo, holdout
     por grupo, com calibracao.
  2. **De onde vem o ganho?** ablacao por bloco — remove um bloco de cada vez
     e mede a perda. E o unico jeito de saber se o ganho veio de comorbidade,
     de resolucao recuperada ou so de mais marcadores de deteccao.
  3. **Para quem melhora?** auditoria por raca/etnia, que so agora e possivel.
     Se o modelo melhora na media e piora num grupo, o ganho medio e enganoso.

Particao: grupo = hash das **21 originais**, nao das 69. Com idade continua e
peso em kg as duplicatas exatas praticamente desaparecem, e usar as 69 tornaria
a particao mais permissiva que a do resto do projeto. Manter a chave antiga e a
escolha conservadora e mantem a comparacao com `docs/08` valida.

Uso:
    python -m diabetes.models.expandido
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier

from diabetes.features.expandido import (
    BLOCOS,
    ORIGINAIS,
    RISCO,
    TODAS,
)
from diabetes.models.escada import avaliar
from diabetes.pipeline.estado import registrar

SEED = 42
ENTRADA = Path("data/processed/gold/brfss_expandido.parquet")

#: rotulos do `_RACEGR3` do CDC
RACAS = {1: "branco nao-hispanico", 2: "negro nao-hispanico", 3: "outro nao-hispanico",
         4: "multirracial nao-hispanico", 5: "hispanico"}


def _modelo(calibrado: bool = True):
    base = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=50,
        l2_regularization=1.0, early_stopping=True, validation_fraction=0.12,
        random_state=SEED)
    return CalibratedClassifierCV(base, method="isotonic", cv=3) if calibrado else base


def particionar(df: pd.DataFrame, frac: float = 0.2) -> np.ndarray:
    """Holdout por grupo, chave = hash das 21 originais (escolha conservadora)."""
    orig = [f"{c}__orig" for c in ORIGINAIS]
    chave = df[orig].fillna(-1).round(0).astype("int64").astype(str).agg("|".join, axis=1)
    g = chave.map(lambda s: hashlib.blake2b(s.encode(), digest_size=8).hexdigest())
    rng = np.random.default_rng(SEED)
    u = g.unique()
    hold = set(u[rng.permutation(len(u))[: int(len(u) * frac)]])
    return g.isin(hold).to_numpy()


def treinar_avaliar(df: pd.DataFrame, cols: list[str], te: np.ndarray,
                    rotulo: str, calibrado: bool = True) -> dict:
    y = df["diabetes"].to_numpy()
    X = df[cols].astype("float32").to_numpy()
    t0 = time.time()
    m = _modelo(calibrado)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X[~te], y[~te])
    p = m.predict_proba(X[te])[:, 1]
    r = avaliar(y[te], p)
    r["n_variaveis"] = len(cols)
    r["segundos"] = round(time.time() - t0, 1)
    print(f"    {rotulo:34} {len(cols):>3} vars  ROC-AUC {r['roc_auc']:.4f}  "
          f"PR-AUC {r['pr_auc']:.4f}  recall@90 {r['recall_esp90']:.3f}  ({r['segundos']}s)")
    return {"metricas": r, "p_holdout": p}


def ablacao_por_bloco(df: pd.DataFrame, te: np.ndarray, referencia: float) -> list[dict]:
    """Remove um bloco por vez e mede a perda. So blocos de risco."""
    saida = []
    for nome, variaveis in BLOCOS.items():
        if nome == "acesso_e_deteccao":
            continue
        restante = [c for c in RISCO if c not in variaveis]
        if not restante:
            continue
        r = treinar_avaliar(df, restante, te, f"sem bloco '{nome}'")["metricas"]
        saida.append({
            "bloco_removido": nome,
            "n_removidas": len(variaveis),
            "pr_auc": r["pr_auc"],
            "perda_pr_auc": round(referencia - r["pr_auc"], 4),
            "perda_%": round((referencia - r["pr_auc"]) / referencia * 100, 2),
        })
    return sorted(saida, key=lambda x: -x["perda_pr_auc"])


def auditar_raca(df: pd.DataFrame, te: np.ndarray, p_orig: np.ndarray,
                 p_novo: np.ndarray) -> list[dict]:
    """Prevalencia, recall e calibracao por grupo racial — antes e depois."""
    y = df["diabetes"].to_numpy()[te]
    raca = df["_RACEGR3"].to_numpy()[te]
    saida = []
    for cod, nome in RACAS.items():
        m = raca == cod
        if m.sum() < 500:
            continue
        linha = {"grupo": nome, "n": int(m.sum()),
                 "prevalencia_%": round(float(y[m].mean() * 100), 2)}
        for rot, p in (("orig", p_orig), ("novo", p_novo)):
            # limiar global fixo (especificidade 90% na populacao inteira):
            # e assim que um programa de rastreamento seria operado
            limiar = np.quantile(p[y == 0], 0.90)
            linha[f"recall_{rot}"] = round(float((p[m][y[m] == 1] >= limiar).mean()), 4)
            linha[f"taxa_selecao_{rot}"] = round(float((p[m] >= limiar).mean()), 4)
            linha[f"risco_medio_{rot}"] = round(float(p[m].mean()), 4)
            linha[f"calibracao_{rot}"] = round(
                float(p[m].mean() - y[m].mean()), 4)  # >0 = superestima o grupo
        linha["ganho_recall"] = round(linha["recall_novo"] - linha["recall_orig"], 4)
        saida.append(linha)
    return saida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, default=ENTRADA)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_frente1_expandido.json"))
    args = ap.parse_args()

    df = pd.read_parquet(args.entrada)
    te = particionar(df)
    registrar("frente1", "inicio", n=len(df))
    print(f"  n={len(df):,}  holdout={te.sum():,}  prevalencia={df['diabetes'].mean():.4f}")

    print("\n  [1] quanto ganha?")
    orig_cols = [f"{c}__orig" for c in ORIGINAIS]
    r_orig = treinar_avaliar(df, orig_cols, te, "21 originais")
    r_risco = treinar_avaliar(df, RISCO, te, "60 curadas (risco)")
    r_todas = treinar_avaliar(df, TODAS, te, "69 curadas (risco + deteccao)")

    print("\n  [2] de onde vem o ganho? (ablacao por bloco)")
    abl = ablacao_por_bloco(df, te, r_risco["metricas"]["pr_auc"])

    print("\n  [3] para quem melhora? (auditoria por raca/etnia)")
    aud = auditar_raca(df, te, r_orig["p_holdout"], r_risco["p_holdout"])
    print(pd.DataFrame(aud)[["grupo", "n", "prevalencia_%", "recall_orig",
                             "recall_novo", "ganho_recall", "calibracao_novo"]]
          .to_string(index=False))

    saida = {
        "protocolo": {
            "particao": "holdout 20% por grupo, chave = hash das 21 originais",
            "modelo": "HistGradientBoosting + calibracao isotonica",
            "alvo": "diabetes vs sem diabetes (classe pre-diabetes excluida)",
            "n": int(len(df)), "n_holdout": int(te.sum()),
        },
        "comparacao": {
            "21_originais": r_orig["metricas"],
            "60_risco": r_risco["metricas"],
            "69_com_deteccao": r_todas["metricas"],
            "ganho_pr_auc_%": round(
                (r_risco["metricas"]["pr_auc"] / r_orig["metricas"]["pr_auc"] - 1) * 100, 2),
            "ganho_roc_auc_milesimos": round(
                (r_risco["metricas"]["roc_auc"] - r_orig["metricas"]["roc_auc"]) * 1000, 1),
            "deteccao_acrescenta_%": round(
                (r_todas["metricas"]["pr_auc"] / r_risco["metricas"]["pr_auc"] - 1) * 100, 2),
        },
        "ablacao_por_bloco": abl,
        "auditoria_raca": aud,
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("frente1", "fim")

    print("\n=== ABLACAO (ordenada pela perda) ===")
    print(pd.DataFrame(abl).to_string(index=False))
    print("\n=== GANHO ===")
    print(json.dumps(saida["comparacao"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
