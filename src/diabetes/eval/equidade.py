"""Trilha C — auditoria de equidade, e o problema de auditar um rotulo enviesado.

`docs/10` mediu recall por raca e achou uma lacuna de 10 pontos percentuais.
Aqui a auditoria e formal, com as metricas padrao — e com a ressalva que quase
nenhum trabalho faz:

**Toda metrica de justica calculada sobre um rotulo enviesado e ela mesma
enviesada.** O rotulo aqui e *diagnostico*, e `docs/12` mostrou que o
subdiagnostico e maior justamente nos grupos de menor acesso. Entao:

  * "recall igual entre grupos" significa "acha a mesma fracao dos JA
    DIAGNOSTICADOS" — nao "acha a mesma fracao dos DOENTES";
  * um modelo que parece justo no rotulo observado pode ser injusto no
    desfecho real, e vice-versa.

Por isso reportamos as metricas **duas vezes**: sobre o rotulo observado e
sobre o rotulo corrigido pelo PU (`docs/12`). A diferenca entre as duas e a
medida de quanto o vies de verificacao contamina a propria auditoria.

Metricas (Barocas, Hardt & Narayanan):
  * **paridade demografica** — taxa de selecao igual entre grupos
  * **igualdade de oportunidade** — recall (TPR) igual
  * **odds equalizados** — TPR e FPR iguais
  * **calibracao por grupo** — risco previsto = risco observado, em cada grupo

Nao se pode satisfazer todas simultaneamente quando a prevalencia difere entre
grupos (Kleinberg, Mullainathan & Raghavan, 2016; Chouldechova, 2017). A
escolha de qual priorizar e normativa, nao tecnica — e esta declarada em `docs/16`.

Uso:
    python -m diabetes.eval.equidade
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier

from diabetes.features.expandido import RISCO
from diabetes.models.expandido import RACAS, particionar
from diabetes.models.pu import C_NHANES, ajustar_ps, scar
from diabetes.pipeline.estado import registrar

ENTRADA = Path("data/processed/gold/brfss_expandido.parquet")
SEED = 42

#: especificidade-alvo da operacao de rastreamento (limiar GLOBAL)
ESPECIFICIDADE = 0.90

GRUPOS = {
    "raca": ("_RACEGR3", RACAS),
    "sexo": ("SEX", {1: "masculino", 2: "feminino"}),
    "renda": ("INCOME2", {1: "<10k", 2: "10-15k", 3: "15-20k", 4: "20-25k",
                          5: "25-35k", 6: "35-50k", 7: "50-75k", 8: ">=75k"}),
    "idade": ("_AGE80", None),   # tratada em faixas
}


def _faixa_idade(v: pd.Series) -> pd.Series:
    return pd.cut(v.astype(float), [0, 45, 65, 200],
                  labels=["18-44", "45-64", "65+"])


def metricas_por_grupo(y: np.ndarray, p: np.ndarray, grupo: pd.Series,
                       limiar: float, w: np.ndarray) -> list[dict]:
    """Prevalencia, taxa de selecao, TPR, FPR, PPV e desvio de calibracao por grupo.

    O limiar e **global**, nao por grupo: e assim que um rastreamento opera na
    pratica, e e exatamente isso que faz TPR e PPV divergirem entre grupos quando
    a prevalencia difere — o resultado de impossibilidade de Chouldechova (2017).
    Grupo com menos de 400 linhas e omitido: abaixo disso o TPR oscila mais que a
    disparidade que se quer medir. Tudo ponderado por `_LLCPWT`, menos `n`, que e
    contagem de amostra e serve para julgar a precisao de cada linha.
    """
    saida = []
    for g in sorted(pd.Series(grupo).dropna().unique(), key=str):
        m = (grupo == g).to_numpy()
        if m.sum() < 400:
            continue
        yy, pp, ww = y[m], p[m], w[m]
        sel = pp >= limiar
        prev = float(np.average(yy, weights=ww))
        tpr = float(np.average(sel[yy == 1], weights=ww[yy == 1])) if (yy == 1).any() else np.nan
        fpr = float(np.average(sel[yy == 0], weights=ww[yy == 0])) if (yy == 0).any() else np.nan
        ppv = float(np.average(yy[sel], weights=ww[sel])) if sel.any() else np.nan
        saida.append({
            "grupo": str(g), "n": int(m.sum()),
            "prevalencia_%": round(prev * 100, 2),
            "taxa_selecao_%": round(float(np.average(sel, weights=ww)) * 100, 2),
            "recall_tpr": round(tpr, 4),
            "fpr": round(fpr, 4),
            "precisao_ppv": round(ppv, 4),
            "risco_medio_previsto": round(float(np.average(pp, weights=ww)), 4),
            "calibracao_desvio_pp": round(
                (float(np.average(pp, weights=ww)) - prev) * 100, 2),
        })
    return saida


def resumo_disparidade(linhas: list[dict]) -> dict:
    """Reduz a tabela por grupo a amplitudes e razoes — o resumo da auditoria.

    Espalhamento, nao teste: sem IC e sem hipotese nula, entao "amplitude 0,05" nao
    autoriza dizer que ha disparidade significativa. As quatro familias reportadas
    (paridade demografica, igualdade de oportunidade, odds equalizados, calibracao)
    nao podem zerar ao mesmo tempo com prevalencias diferentes entre grupos
    (Kleinberg, Mullainathan & Raghavan, 2016); qual priorizar esta declarado em
    `docs/16`.
    """
    def amp(k: str) -> float:
        """Amplitude do indicador entre grupos: max - min, ignorando ausente."""
        v = [x[k] for x in linhas if not pd.isna(x[k])]
        return round(max(v) - min(v), 4) if v else float("nan")
    def raz(k: str) -> float:
        """Razao do indicador entre grupos: min/max, com 1,0 significando paridade.

        Zero fica de fora junto com o ausente — um unico grupo com recall 0 colapsaria
        a razao em 0 e esconderia a distribuicao dos demais.
        """
        v = [x[k] for x in linhas if not pd.isna(x[k]) and x[k] > 0]
        return round(min(v) / max(v), 4) if v else float("nan")
    return {
        "amplitude_paridade_demografica_pp": amp("taxa_selecao_%"),
        "amplitude_igualdade_oportunidade": amp("recall_tpr"),
        "razao_igualdade_oportunidade": raz("recall_tpr"),
        "amplitude_fpr": amp("fpr"),
        "amplitude_calibracao_pp": amp("calibracao_desvio_pp"),
    }


def main() -> None:
    """Audita equidade no rotulo observado e no corrigido pelo PU; grava `gold/_trilhaC_equidade.json`."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, default=ENTRADA)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_trilhaC_equidade.json"))
    args = ap.parse_args()

    df = pd.read_parquet(args.entrada)
    te = particionar(df)
    y = df["diabetes"].to_numpy()
    w = df["_LLCPWT"].to_numpy(float)
    registrar("equidade", "inicio", n=len(df))

    print("  ajustando o modelo de referencia (60 variaveis de risco)…")
    X = df[RISCO].astype("float32").to_numpy()
    m = CalibratedClassifierCV(
        HistGradientBoostingClassifier(
            max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
            min_samples_leaf=50, l2_regularization=1.0, early_stopping=True,
            validation_fraction=0.12, random_state=SEED),
        method="isotonic", cv=3)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X[~te], y[~te])
    p = m.predict_proba(X)[:, 1]

    limiar = float(np.quantile(p[te & (y == 0)], ESPECIFICIDADE))
    print(f"  limiar global (especificidade {ESPECIFICIDADE:.0%}): {limiar:.4f}")

    # --- rotulo corrigido pelo PU -----------------------------------------
    print("  construindo o rotulo corrigido pelo subdiagnostico (PU)…")
    p_s = ajustar_ps(df, RISCO, te)
    p_y = scar(p_s, C_NHANES)
    # rotulo esperado: 1 se diagnosticado; caso contrario, a probabilidade de
    # ser um positivo oculto. Usado como peso, nao como rotulo duro.
    oculto = np.clip((p_y - p_s) / np.clip(1 - p_s, 1e-9, None), 0, 1)

    saida = {"limiar_global": round(limiar, 5),
             "especificidade_alvo": ESPECIFICIDADE,
             "premissa_pu": {"c": C_NHANES, "fonte": "NHANES via docs/12"},
             "observado": {}, "corrigido_pu": {}}

    for nome, (col, rot) in GRUPOS.items():
        g = _faixa_idade(df[col]) if nome == "idade" else df[col].map(rot)
        g_te = g[te]

        obs = metricas_por_grupo(y[te], p[te], g_te, limiar, w[te])
        saida["observado"][nome] = {"por_grupo": obs, "disparidade": resumo_disparidade(obs)}

        # versao corrigida: o "positivo" passa a incluir a massa de ocultos.
        # Implementado por reponderacao — cada nao rotulado conta como positivo
        # com peso `oculto` e como negativo com peso `1 - oculto`.
        y_dup = np.concatenate([y[te], np.ones(te.sum(), dtype=int)])
        p_dup = np.concatenate([p[te], p[te]])
        w_dup = np.concatenate([w[te] * (1 - oculto[te] * (y[te] == 0)),
                                w[te] * oculto[te] * (y[te] == 0)])
        g_dup = pd.concat([g_te, g_te], ignore_index=True)
        mant = w_dup > 0
        cor = metricas_por_grupo(y_dup[mant], p_dup[mant],
                                 g_dup[mant].reset_index(drop=True),
                                 limiar, w_dup[mant])
        saida["corrigido_pu"][nome] = {"por_grupo": cor,
                                       "disparidade": resumo_disparidade(cor)}

        print(f"\n  === {nome.upper()} — rotulo OBSERVADO ===")
        print(pd.DataFrame(obs)[["grupo", "n", "prevalencia_%", "taxa_selecao_%",
                                 "recall_tpr", "precisao_ppv",
                                 "calibracao_desvio_pp"]].to_string(index=False))
        d_o = saida["observado"][nome]["disparidade"]
        d_c = saida["corrigido_pu"][nome]["disparidade"]
        print(f"    amplitude de recall: observado {d_o['amplitude_igualdade_oportunidade']:.4f}"
              f"   corrigido pelo PU {d_c['amplitude_igualdade_oportunidade']:.4f}")

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("equidade", "fim")


if __name__ == "__main__":
    main()
