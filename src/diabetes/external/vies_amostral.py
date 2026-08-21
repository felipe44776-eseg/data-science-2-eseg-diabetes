"""Mede o vies introduzido pelo pre-processamento que gerou o arquivo entregue.

Duas perguntas:

  1. **Quanto a prevalencia muda?** Compara a prevalencia de diabetes em quatro
     estimativas: arquivo entregue sem peso · BRFSS completo sem peso ·
     BRFSS completo com `_LLCPWT` · subamostra analitica com `_LLCPWT`.

  2. **Quem foi descartado?** Compara o perfil dos 187.776 excluidos com o dos
     253.680 mantidos, em idade, sexo, escolaridade, renda, saude e diabetes.

Nota metodologica sobre o peso: `_LLCPWT` e calibrado para a amostra COMPLETA
(pos-estratificacao por raking). Aplicado a uma subamostra nao-aleatoria ele
deixa de somar a populacao corretamente. Reportamos assim mesmo -- e a pratica
usual e o proprio desvio e informativo -- mas com a ressalva explicita.

Uso:
    python -m diabetes.external.vies_amostral --xpt data/external/brfss2015/LLCP2015.XPT
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from diabetes.external.brfss2015 import DESENHO, carregar_xpt, reconstruir

# variaveis extras para caracterizar quem foi excluido
PERFIL = ["_AGEG5YR", "SEX", "EDUCA", "INCOME2", "GENHLTH", "DIABETE3", "_BMI5", "_RFHYPE5"]

RECODE_DIABETES = {1: 2, 2: 0, 3: 0, 4: 1}


def _prop_ponderada(valores: pd.Series, pesos: pd.Series) -> pd.Series:
    """Proporcao ponderada por categoria."""
    t = pd.DataFrame({"v": valores, "w": pesos}).dropna()
    s = t.groupby("v")["w"].sum()
    return s / s.sum()


def _ic_binomial(p: float, n: float, deff: float = 1.0) -> tuple[float, float]:
    """IC 95% de proporcao, com correcao opcional pelo efeito de desenho."""
    ee = np.sqrt(p * (1 - p) / n * deff)
    return p - 1.96 * ee, p + 1.96 * ee


def comparar_prevalencia(bruto: pd.DataFrame, mantidos: pd.DataFrame) -> pd.DataFrame:
    """Quatro estimativas da prevalencia de diabetes diagnosticado."""
    # universo completo: todo respondente com DIABETE3 interpretavel
    full = bruto[bruto["DIABETE3"].isin([1, 2, 3, 4])].copy()
    full["diabetes"] = full["DIABETE3"].replace(RECODE_DIABETES)
    w = full["_LLCPWT"]

    idx_mant = mantidos.index
    sub = full.loc[full.index.intersection(idx_mant)]

    linhas = []

    def add(rotulo, serie, pesos, nota):
        if pesos is None:
            props = serie.value_counts(normalize=True)
            n_ef = len(serie)
        else:
            props = _prop_ponderada(serie, pesos)
            # tamanho efetivo de Kish: (sum w)^2 / sum w^2
            n_ef = pesos.sum() ** 2 / (pesos**2).sum()
        p2 = float(props.get(2, 0.0))
        lo, hi = _ic_binomial(p2, n_ef)
        linhas.append({
            "estimativa": rotulo,
            "n": int(len(serie)),
            "n_efetivo": round(float(n_ef)),
            "sem_diabetes_%": round(float(props.get(0, 0)) * 100, 3),
            "pre_diabetes_%": round(float(props.get(1, 0)) * 100, 3),
            "diabetes_%": round(p2 * 100, 3),
            "ic95_diabetes": f"[{lo*100:.2f}; {hi*100:.2f}]",
            "nota": nota,
        })

    add("a · arquivo entregue, SEM peso", sub["diabetes"], None,
        "o que o trabalho usaria se ignorasse tudo isto")
    add("b · BRFSS completo, SEM peso", full["diabetes"], None,
        "isola o efeito do descarte de 42,5% da amostra")
    add("c · BRFSS completo, COM _LLCPWT", full["diabetes"], w,
        "estimativa populacional correta — a referencia")
    add("d · subamostra analitica, COM _LLCPWT", sub["diabetes"], full.loc[sub.index, "_LLCPWT"],
        "peso aplicado a subamostra: valido? ver ressalva metodologica")
    return pd.DataFrame(linhas)


def perfil_excluidos(bruto: pd.DataFrame, mantidos_idx: pd.Index) -> pd.DataFrame:
    """Compara o perfil de quem ficou e de quem saiu."""
    df = bruto.copy()
    df["mantido"] = df.index.isin(mantidos_idx)

    especificacoes = [
        ("idade_faixa_media (1-13)", "_AGEG5YR", lambda s: s.where(s < 14).mean()),
        ("% 65 anos ou mais", "_AGEG5YR", lambda s: (s.between(10, 13)).mean() * 100),
        ("% masculino", "SEX", lambda s: (s == 1).mean() * 100),
        ("escolaridade media (1-6)", "EDUCA", lambda s: s.where(s < 9).mean()),
        ("% sem ensino medio completo", "EDUCA", lambda s: (s.where(s < 9) < 4).mean() * 100),
        ("renda media (1-8)", "INCOME2", lambda s: s.where(s <= 8).mean()),
        ("% renda nao declarada (77/99)", "INCOME2", lambda s: s.isin([77, 99]).mean() * 100),
        ("saude geral media (1-5)", "GENHLTH", lambda s: s.where(s <= 5).mean()),
        ("% saude regular ou ruim", "GENHLTH", lambda s: (s.where(s <= 5) >= 4).mean() * 100),
        ("IMC medio", "_BMI5", lambda s: (s / 100).mean()),
        ("% hipertensao", "_RFHYPE5", lambda s: (s.where(s < 9) == 2).mean() * 100),
        ("% diabetes (DIABETE3=1)", "DIABETE3", lambda s: (s.where(s.isin([1, 2, 3, 4])) == 1).mean() * 100),
        ("% pre-diabetes (DIABETE3=4)", "DIABETE3", lambda s: (s.where(s.isin([1, 2, 3, 4])) == 4).mean() * 100),
    ]

    linhas = []
    for rotulo, var, fn in especificacoes:
        mant = fn(df.loc[df["mantido"], var])
        excl = fn(df.loc[~df["mantido"], var])
        linhas.append({
            "indicador": rotulo,
            "mantidos (253.680)": round(float(mant), 2),
            "excluidos (187.776)": round(float(excl), 2),
            "diferenca": round(float(excl - mant), 2),
        })
    return pd.DataFrame(linhas)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xpt", type=Path, required=True)
    ap.add_argument("--saida", type=Path, default=Path("data/external/brfss2015/_analise_vies.json"))
    args = ap.parse_args()

    from diabetes.external.brfss2015 import COLUNAS_BRFSS

    cols = sorted(set(COLUNAS_BRFSS + DESENHO + PERFIL))
    print("lendo XPT…")
    bruto = carregar_xpt(args.xpt, colunas=cols)
    print(f"  {len(bruto):,} respondentes")

    mantidos, _, _ = reconstruir(bruto)

    prev = comparar_prevalencia(bruto, mantidos)
    perfil = perfil_excluidos(bruto, mantidos.index)

    print("\n=== PREVALENCIA — quatro estimativas ===")
    print(prev.to_string(index=False))
    print("\n=== PERFIL — quem ficou vs quem saiu ===")
    print(perfil.to_string(index=False))

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps({
        "prevalencia": prev.to_dict("records"),
        "perfil": perfil.to_dict("records"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
