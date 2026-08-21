"""EDA em base dupla: arquivo entregue (sem peso) vs BRFSS completo (ponderado).

Toda estimativa do relatorio sai em par. A diferenca entre as duas colunas **e**
o resultado: mostra o que o pre-processamento e a ausencia de peso fizeram com
cada conclusao, variavel a variavel.

  base A — `data/processed/diabetes_silver.parquet`
           253.680 linhas · sem peso · o que o trabalho usaria por padrao

  base B — BRFSS 2015 completo, derivado sem descartar respondente
           441.456 linhas · `_LLCPWT` · exclusao par a par por variavel

Uso:
    python -m diabetes.eda.comparativo --xpt data/external/brfss2015/LLCP2015.XPT
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from diabetes.eda.associacao import (
    associacao_binarias,
    associacao_ordinais,
    cliff_delta,
    deff,
    n_efetivo_kish,
)
from diabetes.external.brfss2015 import (
    COLUNAS_BRFSS,
    DESENHO,
    carregar_xpt,
    reconstruir_sem_descarte,
)
from diabetes.schema import BINARIAS, ESQUEMA, TARGET

ORDINAIS_ANALISE = ["saude_geral", "idade_faixa", "escolaridade", "renda_faixa"]


def _desfecho_binario(s: pd.Series) -> pd.Series:
    """Diabetes diagnosticado (classe 2) vs resto. Pre-diabetes tratado a parte."""
    return (s == 2).astype("float").where(s.notna())


def carregar_bases(xpt: Path, silver: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carrega o par: A (silver, sem peso) e B (BRFSS reconstruido, com `_LLCPWT`).

    A sai como `Float32` — o silver e `uint8` e nao admite ausente, mas as duas
    bases precisam do mesmo tratamento par a par para que a comparacao seja de
    metodo e nao de tipo. B vem de `reconstruir_sem_descarte`: nenhum respondente
    e eliminado por ausencia em outra variavel, ao contrario do arquivo entregue
    (`docs/05`).
    """
    a = pd.read_parquet(silver)[list(ESQUEMA)].astype("Float32")
    bruto = carregar_xpt(xpt, colunas=COLUNAS_BRFSS + DESENHO)
    b = reconstruir_sem_descarte(bruto)
    return a, b


def comparar(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    """Roda a EDA inteira nas duas bases e devolve o dicionario A-vs-B.

    O resultado nao e "a estimativa"; e o par. `delta_exposicao` e `delta_OR_%`
    medem o efeito conjunto do pre-processamento do Kaggle e da ausencia de peso —
    nao erro amostral, e por isso nao vem com IC. `deff_pesos` da o multiplicador
    que corrige o erro-padrao ingenuo de B (`docs/05`); IC calculado sem ele e
    estreito demais.

    O alvo e binarizado em diabetes diagnosticado (classe 2) contra o resto: a
    classe 1 fica **fora**, nao no meio, porque pre-diabetes tem mecanismo proprio
    (`docs/07` §3). Como sempre, o alvo mede diagnostico autorrelatado, nao doenca.
    """
    da, db = _desfecho_binario(a[TARGET]), _desfecho_binario(b[TARGET])
    peso = b["_LLCPWT"]

    resultado: dict = {}

    # --- cobertura e desenho -------------------------------------------------
    resultado["desenho"] = {
        "base_A_linhas": int(len(a)),
        "base_B_linhas": int(len(b)),
        "base_B_com_alvo_valido": int(db.notna().sum()),
        "deff_pesos": round(float(deff(peso)), 3),
        "n_efetivo_B": round(float(n_efetivo_kish(peso))),
        "ic_multiplicador": round(float(np.sqrt(deff(peso))), 3),
    }

    # --- prevalencia do alvo -------------------------------------------------
    va = a[TARGET].value_counts(normalize=True).sort_index() * 100
    m = b[TARGET].notna()
    vb = (pd.DataFrame({"y": b.loc[m, TARGET], "w": peso[m]})
          .groupby("y")["w"].sum().pipe(lambda s: s / s.sum() * 100))
    resultado["alvo"] = {
        "A_sem_peso_%": {int(k): round(float(v), 3) for k, v in va.items()},
        "B_ponderado_%": {int(k): round(float(v), 3) for k, v in vb.items()},
    }

    # --- binarias ------------------------------------------------------------
    bins = [c for c in BINARIAS if c in a.columns]
    ta = associacao_binarias(a, bins, da).set_index("variavel")
    tb = associacao_binarias(b, bins, db, peso).set_index("variavel")
    comp = pd.DataFrame({
        "A_%_exposto": ta["%_exposto"],
        "B_%_exposto": tb["%_exposto"],
        "delta_exposicao": (ta["%_exposto"] - tb["%_exposto"]).round(2),
        "A_prev_expostos": ta["prev_expostos_%"],
        "B_prev_expostos": tb["prev_expostos_%"],
        "A_OR": ta["or"], "A_ic": ta.apply(lambda r: f"[{r['or_ic_baixo']:.2f}; {r['or_ic_alto']:.2f}]", axis=1),
        "B_OR": tb["or"], "B_ic": tb.apply(lambda r: f"[{r['or_ic_baixo']:.2f}; {r['or_ic_alto']:.2f}]", axis=1),
        "delta_OR_%": ((ta["or"] / tb["or"] - 1) * 100).round(1),
        "A_V": ta["v_cramer"], "B_V": tb["v_cramer"],
        "efeito_B": tb["efeito"],
        "B_n_efetivo": tb["n_efetivo"],
    }).sort_values("B_OR", ascending=False)
    resultado["binarias"] = comp.reset_index().to_dict("records")

    # --- ordinais ------------------------------------------------------------
    oa = associacao_ordinais(a, ORDINAIS_ANALISE, da).set_index("variavel")
    ob = associacao_ordinais(b, ORDINAIS_ANALISE, db, peso).set_index("variavel")
    resultado["ordinais"] = pd.DataFrame({
        "A_prev_min": oa["prev_min_%"], "A_prev_max": oa["prev_max_%"],
        "A_razao": oa["razao_extremos"],
        "B_prev_min": ob["prev_min_%"], "B_prev_max": ob["prev_max_%"],
        "B_razao": ob["razao_extremos"],
        "A_r": oa["r_tendencia"], "B_r": ob["r_tendencia"],
        "monotonica_B": ob["monotonica"],
        "A_prev_por_nivel": oa["prev_por_nivel"], "B_prev_por_nivel": ob["prev_por_nivel"],
    }).reset_index().to_dict("records")

    # --- IMC (continua) ------------------------------------------------------
    imc_a = a.loc[da == 1, "imc"], a.loc[da == 0, "imc"]
    mb = b["imc"].notna() & db.notna()
    resultado["imc"] = {
        "A_media_diabetes": round(float(imc_a[0].mean()), 2),
        "A_media_sem": round(float(imc_a[1].mean()), 2),
        "A_cliff_delta": round(cliff_delta(imc_a[0], imc_a[1]), 4),
        "B_media_diabetes_pond": round(float(np.average(
            b.loc[mb & (db == 1), "imc"], weights=peso[mb & (db == 1)])), 2),
        "B_media_sem_pond": round(float(np.average(
            b.loc[mb & (db == 0), "imc"], weights=peso[mb & (db == 0)])), 2),
        "A_prev_por_faixa_oms": _prev_por_faixa_imc(a["imc"], da, None),
        "B_prev_por_faixa_oms": _prev_por_faixa_imc(b["imc"], db, peso),
    }
    return resultado


def _prev_por_faixa_imc(imc: pd.Series, desfecho: pd.Series,
                        peso: pd.Series | None) -> dict:
    faixa = pd.cut(imc.astype(float), [0, 18.5, 25, 30, 35, 40, np.inf], right=False,
                   labels=["baixo_peso", "eutrofico", "sobrepeso",
                           "obesidade_I", "obesidade_II", "obesidade_III"])
    d = pd.DataFrame({"f": faixa, "y": desfecho}).dropna()
    d["w"] = 1.0 if peso is None else peso.loc[d.index].to_numpy()
    g = d.groupby("f", observed=True).apply(
        lambda x: np.average(x["y"], weights=x["w"]) * 100, include_groups=False)
    return {str(k): round(float(v), 2) for k, v in g.items()}


def main() -> None:
    """Compara arquivo entregue e BRFSS completo e grava `gold/_eda_comparativa.json`."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xpt", type=Path, required=True)
    ap.add_argument("--silver", type=Path, default=Path("data/processed/diabetes_silver.parquet"))
    ap.add_argument("--saida", type=Path, default=Path("data/processed/gold/_eda_comparativa.json"))
    args = ap.parse_args()

    print("carregando as duas bases…")
    a, b = carregar_bases(args.xpt, args.silver)
    print(f"  A (arquivo entregue): {len(a):,}   B (BRFSS completo): {len(b):,}")

    res = comparar(a, b)

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")

    print("\n=== DESENHO ===")
    print(json.dumps(res["desenho"], indent=2))
    print("\n=== ALVO ===")
    print(json.dumps(res["alvo"], indent=2))
    print("\n=== BINARIAS (ordenado por OR ponderado) ===")
    print(pd.DataFrame(res["binarias"])[
        ["variavel", "A_%_exposto", "B_%_exposto", "delta_exposicao",
         "A_OR", "B_OR", "B_ic", "delta_OR_%", "B_V", "efeito_B"]
    ].to_string(index=False))
    print("\n=== ORDINAIS ===")
    print(pd.DataFrame(res["ordinais"])[
        ["variavel", "A_prev_min", "A_prev_max", "A_razao",
         "B_prev_min", "B_prev_max", "B_razao", "monotonica_B"]
    ].to_string(index=False))
    print("\n=== IMC ===")
    print(json.dumps(res["imc"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
