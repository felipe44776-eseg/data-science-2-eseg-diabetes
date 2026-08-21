"""Recalibracao do escore de 5 perguntas para o Brasil.

Por que esta frente existe
--------------------------
`docs/09` §2.3 mediu que o **IMC pesa 16% menos no Brasil** (OR 1,228 contra
1,454 por 5 kg/m²), e a prevalencia diagnosticada e bem menor (7,08% contra
10,50%). Um escore calibrado nos EUA aplicado aqui erra de duas formas:

  * **discriminacao** — os pesos relativos entre fatores nao sao os mesmos;
  * **calibracao** — mesmo que a ordem esteja certa, o *nivel* de risco previsto
    fica alto demais, porque a prevalencia de base difere.

A segunda e a mais perigosa num escore clinico: um instrumento que diz "seu
risco e 28%" quando o risco real e 15% gera rastreamento excessivo e ansiedade.

O que se mede aqui
------------------
1. o escore dos EUA aplicado **cru** ao Vigitel — quanto erra, e em que direcao;
2. os pontos **reajustados** no Vigitel — quais fatores mudam de peso;
3. a tabela de risco **recalibrada** para a populacao brasileira;
4. quanto se ganha recalibrando, separando **discriminacao** (ROC-AUC) de
   **calibracao** (razao previsto/observado). E a distincao que importa: o
   escore americano pode ordenar bem e mesmo assim ser inutilizavel aqui.

Mapeamento da saude autoavaliada
--------------------------------
As escalas diferem e nao dava para ignorar:

    BRFSS GENHLTH   1 excelente · 2 muito boa · 3 boa · 4 regular · 5 ruim
    Vigitel q74     1 muito bom · 2 bom · 3 regular · 4 ruim · 5 muito ruim

Colapsadas nos 3 niveis do escore:

    "excelente/muito boa"  <-  BRFSS 1-2   ·  Vigitel 1
    "boa"                  <-  BRFSS 3     ·  Vigitel 2
    "regular/ruim"         <-  BRFSS 4-5   ·  Vigitel 3-5

Uso:
    python -m diabetes.eval.escore_brasil
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

from diabetes.eval.escore import (
    VARS_B,
    _faixas,
    ajustar,
    aplicar,
    calibrar,
    pontos_inteiros,
    risco_do_escore,
)
from diabetes.external.vigitel import carregar_vigitel
from diabetes.models.expandido import particionar
from diabetes.pipeline.estado import registrar

VIGITEL = Path("data/external/vigitel/vigitel2015_bruto.parquet")
EXPANDIDO = Path("data/processed/gold/brfss_expandido.parquet")
SEED = 42


# --------------------------------------------------------------------------
# harmonizacao das faixas do escore no Vigitel
# --------------------------------------------------------------------------

def faixas_vigitel(v: pd.DataFrame) -> pd.DataFrame:
    """Mesmas faixas do escore, calculadas sobre as variaveis do Vigitel."""
    d = pd.DataFrame(index=v.index)
    idade = v["q6"].astype(float)
    imc = v["q9_i"] / (v["q11_i"] / 100) ** 2

    d["idade"] = pd.cut(idade, [0, 35, 45, 55, 65, 200],
                        labels=["<35", "35-44", "45-54", "55-64", "65+"], right=False)
    d["imc"] = pd.cut(imc.where(imc.between(12, 98)), [0, 25, 30, 35, 100],
                      labels=["<25", "25-29", "30-34", "35+"], right=False)
    # q74: 1 muito bom · 2 bom · 3 regular · 4 ruim · 5 muito ruim
    d["saude"] = pd.Categorical(
        np.select(
            [v["q74"].eq(1), v["q74"].eq(2), v["q74"].isin([3, 4, 5])],
            ["excelente/muito boa", "boa", "regular/ruim"], default=None),
        categories=["excelente/muito boa", "boa", "regular/ruim"])
    d["hipertensao"] = pd.Categorical(
        v["q75"].map({1: "sim", 2: "nao"}), categories=["nao", "sim"])
    d["sexo"] = pd.Categorical(
        v["q7"].map({1: "masculino", 2: "feminino"}),
        categories=["feminino", "masculino"])
    return d


def alvo_vigitel(v: pd.DataFrame) -> pd.Series:
    """q76: 1 sim · 2 nao · 777 nao sabe. r138=1 -> gestacional, vira 0."""
    y = v["q76"].where(v["q76"].isin([1, 2])).replace({1: 1, 2: 0})
    return y.mask((y == 1) & (v["r138"] == 1), 0)


# --------------------------------------------------------------------------
# metricas de calibracao
# --------------------------------------------------------------------------

def calibracao(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> dict:
    """Razao previsto/observado e erro medio — o que a discriminacao nao ve."""
    obs = float(np.average(y, weights=w))
    prev = float(np.average(p, weights=w))
    # inclinacao da calibracao: regressao do desfecho no logit do previsto.
    # 1,0 = perfeita; < 1 = previsoes espalhadas demais; > 1 = comprimidas
    lp = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    X = sm.add_constant(lp)
    ww = w * (len(w) / w.sum())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = sm.GLM(y, X, family=sm.families.Binomial(), freq_weights=ww).fit()
    return {
        "observado_%": round(obs * 100, 3),
        "previsto_%": round(prev * 100, 3),
        "razao_previsto_observado": round(prev / obs, 3),
        "erro_absoluto_pp": round((prev - obs) * 100, 3),
        "inclinacao_calibracao": round(float(m.params[1]), 3),
        "intercepto_calibracao": round(float(m.params[0]), 3),
    }


def por_faixa(pontos: pd.Series, y: pd.Series, w: pd.Series,
              cal_eua: dict) -> list[dict]:
    """Risco previsto pela tabela americana vs observado no Brasil, por faixa."""
    faixa = pd.cut(pontos, cal_eua["cortes"], labels=False, include_lowest=True)
    mapa = {f["faixa"]: f for f in cal_eua["faixas"]}
    saida = []
    for k in sorted(faixa.dropna().unique()):
        m = (faixa == k) & y.notna()
        if m.sum() < 200:
            continue
        obs = float(np.average(y[m], weights=w[m]))
        ref = mapa.get(int(k), {})
        saida.append({
            "faixa": int(k) + 1,
            "pontos": f"{ref.get('pontos_min', '?')}–{ref.get('pontos_max', '?')}",
            "risco_EUA_%": ref.get("risco_%"),
            "risco_BR_observado_%": round(obs * 100, 2),
            "razao": round(ref["risco_%"] / (obs * 100), 2)
            if ref.get("risco_%") and obs > 0 else None,
            "n": int(m.sum()),
        })
    return saida


# --------------------------------------------------------------------------

def main() -> None:
    """Recalibra o escore de 5 perguntas no Vigitel e grava `gold/_escore_brasil.json`."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vigitel", type=Path, default=VIGITEL)
    ap.add_argument("--expandido", type=Path, default=EXPANDIDO)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_escore_brasil.json"))
    args = ap.parse_args()

    registrar("escore_brasil", "inicio")

    # --- escore dos EUA, ajustado no BRFSS ---------------------------------
    print("  ajustando o escore nos EUA (BRFSS)…")
    us = pd.read_parquet(args.expandido)
    te_us = particionar(us)
    fx_us = _faixas(us)
    coef_us, _ = ajustar(us, fx_us, VARS_B, ~te_us)
    tab_us = pontos_inteiros(coef_us, VARS_B)
    pts_us = aplicar(fx_us, tab_us, VARS_B)
    cal_us = calibrar(pts_us, us["diabetes"].astype(int),
                      us["_LLCPWT"].astype(float), ~te_us)

    # --- Vigitel -----------------------------------------------------------
    print("  carregando Vigitel 2015…")
    vig_bruto = pd.read_parquet(args.vigitel)
    _ = carregar_vigitel(args.vigitel)          # valida a harmonizacao
    fx_br = faixas_vigitel(vig_bruto)
    y_br = alvo_vigitel(vig_bruto)
    w_br = vig_bruto["pesorake"].astype(float)

    ok = fx_br.notna().all(axis=1) & y_br.notna()
    print(f"    {ok.sum():,} de {len(vig_bruto):,} com as 5 respostas completas")

    # particao propria do Brasil, para nao avaliar no que ajustou
    rng = np.random.default_rng(SEED)
    te_br = pd.Series(rng.random(len(vig_bruto)) < 0.30, index=vig_bruto.index)

    # --- [1] escore americano aplicado CRU ao Brasil -----------------------
    print("\n  [1] escore dos EUA aplicado cru ao Brasil")
    pts_br = aplicar(fx_br, tab_us, VARS_B)
    risco_cru = risco_do_escore(pts_br, cal_us)
    m = ok & te_br
    cal_cru = calibracao(y_br[m].to_numpy(float), risco_cru[m].to_numpy(float),
                         w_br[m].to_numpy(float))
    disc_cru = {
        "roc_auc": round(float(roc_auc_score(y_br[m], risco_cru[m])), 4),
        "pr_auc": round(float(average_precision_score(y_br[m], risco_cru[m])), 4),
    }
    for k, v in {**disc_cru, **cal_cru}.items():
        print(f"    {k:28} {v}")

    # --- [2] pontos reajustados no Brasil ----------------------------------
    print("\n  [2] pontos reajustados no Vigitel")
    # `ajustar` faz astype(int) na coluna inteira antes de aplicar a mascara,
    # entao o alvo nao pode ter NaN aqui. As linhas invalidas ja estao fora do
    # treino por `ok`; preencher com 0 e seguro e nao entra no ajuste.
    d_br = pd.DataFrame({**{c: fx_br[c] for c in VARS_B},
                         "diabetes": y_br.fillna(0).astype(int),
                         "_LLCPWT": w_br})
    coef_br, _ = ajustar(d_br, fx_br, VARS_B, (~te_br & ok).to_numpy())
    tab_br = pontos_inteiros(coef_br, VARS_B)
    for var in VARS_B:
        us_p = tab_us["pontos"][var]
        br_p = tab_br["pontos"][var]
        linha = "  ".join(
            f"{k}: {us_p.get(k, 0):+d} -> {br_p.get(k, 0):+d}"
            for k in sorted(br_p, key=lambda x: br_p[x]))
        print(f"    {var:14} {linha}")

    pts_br2 = aplicar(fx_br, tab_br, VARS_B)
    cal_br = calibrar(pts_br2, y_br.fillna(0).astype(int), w_br,
                      (~te_br & ok).to_numpy())
    risco_br = risco_do_escore(pts_br2, cal_br)

    print("\n  [3] escore recalibrado para o Brasil")
    cal_rec = calibracao(y_br[m].to_numpy(float), risco_br[m].to_numpy(float),
                         w_br[m].to_numpy(float))
    disc_rec = {
        "roc_auc": round(float(roc_auc_score(y_br[m], risco_br[m])), 4),
        "pr_auc": round(float(average_precision_score(y_br[m], risco_br[m])), 4),
    }
    for k, v in {**disc_rec, **cal_rec}.items():
        print(f"    {k:28} {v}")

    # --- [4] onde o escore americano erra, faixa a faixa -------------------
    print("\n  [4] risco previsto pela tabela dos EUA vs observado no Brasil")
    faixas = por_faixa(pts_br[m], y_br[m], w_br[m], cal_us)
    print(pd.DataFrame(faixas).to_string(index=False))

    saida = {
        "premissa": {
            "motivo": "docs/09 §2.3 — o IMC pesa 16% menos no Brasil",
            "n_vigitel_completo": int(ok.sum()),
            "n_avaliacao": int(m.sum()),
            "mapeamento_saude": {
                "excelente/muito boa": "BRFSS 1-2 · Vigitel 1",
                "boa": "BRFSS 3 · Vigitel 2",
                "regular/ruim": "BRFSS 4-5 · Vigitel 3-5",
            },
        },
        "escore_eua_aplicado_cru": {**disc_cru, "calibracao": cal_cru,
                                    "tabela_pontos": tab_us["pontos"]},
        "escore_recalibrado_br": {**disc_rec, "calibracao": cal_rec,
                                  "tabela_pontos": tab_br["pontos"],
                                  "faixas_de_risco": cal_br["faixas"]},
        "comparacao": {
            "ganho_roc_auc_milesimos": round(
                (disc_rec["roc_auc"] - disc_cru["roc_auc"]) * 1000, 1),
            "erro_de_calibracao_antes_pp": cal_cru["erro_absoluto_pp"],
            "erro_de_calibracao_depois_pp": cal_rec["erro_absoluto_pp"],
            "razao_previsto_observado_antes": cal_cru["razao_previsto_observado"],
            "razao_previsto_observado_depois": cal_rec["razao_previsto_observado"],
        },
        "por_faixa": faixas,
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("escore_brasil", "fim")

    print("\n  === RESUMO ===")
    print(json.dumps(saida["comparacao"], ensure_ascii=False, indent=2))



if __name__ == "__main__":
    main()
