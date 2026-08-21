"""Trilha C — analise de decisao: vale rastrear, quem primeiro, a que custo.

AUC nao responde a pergunta do gestor. Tres ferramentas que respondem:

**Curva de decisao (Vickers & Elkin, 2006)** — *net benefit* em funcao do limiar:

    NB(t) = VP/n − FP/n · t/(1−t)

O termo `t/(1−t)` e a razao de troca implicita no limiar: quem rastreia a partir
de 10% de risco esta dizendo que um caso encontrado vale 9 falsos-positivos.
Comparamos contra as duas estrategias triviais — **rastrear todos** e **rastrear
ninguem**. Se o modelo nao superar as duas em alguma faixa util de limiar, ele
nao deve ser usado, por melhor que seja o AUC.

**Numero necessario para rastrear (NNS)** por decil de risco, e o custo em reais.

**Curva de cobertura** — quantos casos se encontra testando X% da populacao.

Uso:
    python -m diabetes.eval.decisao
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

from diabetes.eval.escore import (
    VARS_B,
    _faixas,
    ajustar,
    aplicar,
    calibrar,
    findrisc,
    pontos_inteiros,
    risco_do_escore,
)
from diabetes.features.expandido import RISCO
from diabetes.models.expandido import particionar
from diabetes.pipeline.estado import registrar

ENTRADA = Path("data/processed/gold/brfss_expandido.parquet")
SEED = 42

#: custo do teste confirmatorio. HbA1c na tabela SUS/AMB fica nesta faixa; usamos
#: os tres valores para nao fingir precisao que a tabela nao tem.
CUSTO_HBA1C = [25.0, 32.0, 40.0]


def net_benefit(y: np.ndarray, p: np.ndarray, limiares: np.ndarray,
                w: np.ndarray | None = None) -> list[dict]:
    """Net benefit do modelo e das duas estrategias triviais, por limiar."""
    w = np.ones(len(y)) if w is None else w
    total = w.sum()
    prev = float(np.average(y, weights=w))
    saida = []
    for t in limiares:
        sel = p >= t
        vp = w[sel & (y == 1)].sum() / total
        fp = w[sel & (y == 0)].sum() / total
        odds = t / (1 - t)
        saida.append({
            "limiar": round(float(t), 4),
            "nb_modelo": round(float(vp - fp * odds), 6),
            "nb_rastrear_todos": round(float(prev - (1 - prev) * odds), 6),
            "nb_rastrear_ninguem": 0.0,
            "%_selecionado": round(float(w[sel].sum() / total * 100), 2),
        })
    return saida


def faixa_util(curva: list[dict]) -> dict:
    """Onde o modelo supera as DUAS estrategias triviais."""
    uteis = [c for c in curva
             if c["nb_modelo"] > max(c["nb_rastrear_todos"], 0) + 1e-9]
    if not uteis:
        return {"tem_faixa_util": False}
    return {
        "tem_faixa_util": True,
        "limiar_min": uteis[0]["limiar"], "limiar_max": uteis[-1]["limiar"],
        "n_limiares": len(uteis),
        "melhor_ganho_sobre_trivial": round(max(
            c["nb_modelo"] - max(c["nb_rastrear_todos"], 0) for c in uteis), 6),
    }


def por_decil(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> list[dict]:
    """Risco, NNS e custo por faixa de risco previsto.

    Um escore de pontos produz poucos valores distintos — o decil por quantil
    colide. Usamos as bordas unicas, o que pode devolver menos de dez faixas:
    a granularidade e a que o instrumento realmente tem, nao a que se pediu.
    """
    corte = np.unique(np.quantile(p, np.linspace(0, 1, 11)))
    corte = np.concatenate([[-np.inf], corte[1:-1], [np.inf]])
    d = pd.cut(p, corte, labels=False, include_lowest=True, duplicates="drop")
    saida = []
    for k in sorted(pd.Series(d).dropna().unique()):
        m = d == k
        if not m.any():
            continue
        risco = float(np.average(y[m], weights=w[m]))
        nns = 1 / risco if risco > 0 else np.inf
        saida.append({
            "faixa": int(k) + 1,
            "risco_%": round(risco * 100, 2),
            "nns": round(nns, 1),
            "custo_por_caso_R$": [round(nns * c, 0) for c in CUSTO_HBA1C],
            "%_dos_casos_totais": round(float(
                w[m & (y == 1)].sum() / w[y == 1].sum() * 100), 2),
        })
    return saida


def curva_de_cobertura(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> list[dict]:
    """Testando os X% de maior risco, que fracao dos casos se encontra?"""
    ordem = np.argsort(-p)
    yo, wo = y[ordem], w[ordem]
    acum_w = np.cumsum(wo) / wo.sum()
    acum_casos = np.cumsum(wo * yo) / (wo * yo).sum()
    saida = []
    for alvo in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.75, 1.0):
        i = int(np.searchsorted(acum_w, alvo))
        i = min(i, len(acum_casos) - 1)
        capt = float(acum_casos[i])
        risco_medio = float(np.average(yo[: i + 1], weights=wo[: i + 1]))
        nns = 1 / risco_medio if risco_medio > 0 else np.inf
        saida.append({
            "%_testado": round(alvo * 100, 1),
            "%_casos_encontrados": round(capt * 100, 2),
            "nns_acumulado": round(nns, 2),
            "custo_por_caso_R$": [round(nns * c, 0) for c in CUSTO_HBA1C],
        })
    return saida


def _modelo_completo(df: pd.DataFrame, te: np.ndarray) -> np.ndarray:
    y = df["diabetes"].to_numpy()
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
    return m.predict_proba(X)[:, 1]


def main() -> None:
    """Avalia modelo, escore e FINDRISC por decisao clinica e grava `gold/_trilhaC_decisao.json`."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, default=ENTRADA)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_trilhaC_decisao.json"))
    args = ap.parse_args()

    df = pd.read_parquet(args.entrada)
    te = particionar(df)
    faixas = _faixas(df)
    y_s, w_s = df["diabetes"].astype(int), df["_LLCPWT"].astype(float)
    registrar("decisao", "inicio", n=len(df))

    print("  construindo os candidatos…")
    # escore de 5 perguntas
    coef, _ = ajustar(df, faixas, VARS_B, ~te)
    tab = pontos_inteiros(coef, VARS_B)
    pts = aplicar(faixas, tab, VARS_B)
    cal = calibrar(pts, y_s, w_s, ~te)
    p_escore = risco_do_escore(pts, cal).to_numpy(float)
    # modelo completo
    p_modelo = _modelo_completo(df, te)
    # FINDRISC reescalado para probabilidade (por faixa observada no treino)
    fr = findrisc(df)
    cal_fr = calibrar(fr, y_s, w_s, ~te)
    p_findrisc = risco_do_escore(fr, cal_fr).to_numpy(float)

    comum = te & ~np.isnan(p_escore) & ~np.isnan(p_findrisc) & ~np.isnan(p_modelo)
    y = y_s.to_numpy()[comum]
    w = w_s.to_numpy()[comum]
    print(f"  amostra de avaliacao: {comum.sum():,}  prevalencia ponderada "
          f"{np.average(y, weights=w)*100:.2f}%")

    limiares = np.round(np.arange(0.02, 0.51, 0.01), 3)
    candidatos = {
        "modelo_completo_60_vars": p_modelo[comum],
        "escore_5_perguntas": p_escore[comum],
        "findrisc_aproximado": p_findrisc[comum],
    }

    saida = {"custo_hba1c_R$": CUSTO_HBA1C,
             "prevalencia_ponderada_%": round(float(np.average(y, weights=w) * 100), 3),
             "n_avaliacao": int(comum.sum()), "candidatos": {}}

    for nome, p in candidatos.items():
        curva = net_benefit(y, p, limiares, w)
        util = faixa_util(curva)
        saida["candidatos"][nome] = {
            "curva_decisao": curva,
            "faixa_util": util,
            "por_decil": por_decil(y, p, w),
            "cobertura": curva_de_cobertura(y, p, w),
        }
        print(f"\n  === {nome} ===")
        if util["tem_faixa_util"]:
            print(f"    supera as estrategias triviais entre limiar "
                  f"{util['limiar_min']:.0%} e {util['limiar_max']:.0%}")
        else:
            print("    NAO supera as estrategias triviais em nenhum limiar")
        cob = saida["candidatos"][nome]["cobertura"]
        print(pd.DataFrame(cob)[["%_testado", "%_casos_encontrados",
                                 "nns_acumulado"]].head(6).to_string(index=False))

    print("\n  === NNS E CUSTO POR DECIL — escore de 5 perguntas ===")
    dec = pd.DataFrame(saida["candidatos"]["escore_5_perguntas"]["por_decil"])
    dec["custo_medio_R$"] = dec["custo_por_caso_R$"].apply(lambda x: x[1])
    print(dec[["faixa", "risco_%", "nns", "custo_medio_R$",
               "%_dos_casos_totais"]].to_string(index=False))

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("decisao", "fim")


if __name__ == "__main__":
    main()
