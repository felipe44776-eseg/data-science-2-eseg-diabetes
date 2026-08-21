"""Camada de limpeza: bronze (CSV bruto) -> silver (parquet validado).

Principio: **nenhuma linha some sem registro**. Toda regra emite contagem no
relatorio de qualidade; toda linha removida vai para `data/interim/quarentena/`.
A limpeza e reproduzivel e idempotente — rodar duas vezes da o mesmo hash.

Regras implementadas (justificativa em `docs/adr/0002-limpeza.md`):

  R1  padroniza nomes pt-BR -> snake_case ASCII
  R2  converte float64 -> menor inteiro que cabe (uint8) — todos os valores sao inteiros
  R3  valida dominio contra `schema.ESQUEMA`; violacao = quarentena
  R4  marca (nao remove) duplicatas exatas — decisao de deduplicar e da camada de modelagem
  R5  marca grupos de features identicas com alvo conflitante (ruido de rotulo irredutivel)
  R6  marca IMC fisiologicamente implausivel (>60) sem imputar — autorrelato, nao erro de digitacao
  R7  deriva colunas auxiliares interpretaveis (idade_anos, renda_usd, faixas OMS de IMC)

Uso:
    python -m diabetes.clean.pipeline --entrada data/raw/diabetes_2026_raw.csv \
        --saida data/processed/diabetes_silver.parquet
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from diabetes.schema import (
    ESQUEMA,
    IDADE_PONTO_MEDIO,
    PTBR_TO_SNAKE,
    RENDA_PONTO_MEDIO,
    TARGET,
)

# limiar de plausibilidade fisiologica do IMC autorrelatado.
# BRFSS trunca em 98; adultos acima de 60 existem, mas concentram erro de
# autorrelato de altura/peso. Marcamos, nao removemos.
IMC_IMPLAUSIVEL = 60


def _faixa_oms(imc: pd.Series) -> pd.Series:
    """Classificacao OMS de IMC — usada para comparabilidade com fontes externas."""
    return pd.cut(
        imc,
        bins=[0, 18.5, 25, 30, 35, 40, np.inf],
        right=False,
        labels=["baixo_peso", "eutrofico", "sobrepeso", "obesidade_I",
                "obesidade_II", "obesidade_III"],
    )


def limpar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rel: dict = {"entrada_linhas": len(df)}

    # R1 — nomes
    df = df.rename(columns=PTBR_TO_SNAKE)
    faltando = set(ESQUEMA) - set(df.columns)
    if faltando:
        raise ValueError(f"colunas ausentes apos renomear: {sorted(faltando)}")
    df = df[list(ESQUEMA)]

    # R3 — dominio (antes do downcast, para nao mascarar valor invalido)
    mask_invalida = pd.Series(False, index=df.index)
    violacoes: dict[str, int] = {}
    for col, meta in ESQUEMA.items():
        s = df[col]
        if meta.dominio is not None:
            ruim = ~s.isin(meta.dominio)
        else:
            ruim = (s < meta.minimo) | (s > meta.maximo) | s.isna()
        if ruim.any():
            violacoes[col] = int(ruim.sum())
            mask_invalida |= ruim
    rel["violacoes_dominio"] = violacoes
    quarentena = df[mask_invalida].copy()
    df = df[~mask_invalida].copy()
    rel["linhas_quarentena"] = int(len(quarentena))

    # R2 — tipos
    for col, meta in ESQUEMA.items():
        df[col] = df[col].astype("uint8")

    # R4 — duplicatas exatas (marcadas, nao removidas)
    dup_exata = df.duplicated(keep="first")
    rel["duplicatas_exatas"] = int(dup_exata.sum())
    df["flag_duplicata_exata"] = dup_exata.values

    # R5 — mesmas features, alvo diferente => ruido de rotulo irredutivel
    feats = [c for c in ESQUEMA if c != TARGET]
    chave = df.groupby(feats, sort=False)[TARGET].transform("nunique")
    df["flag_alvo_conflitante"] = (chave > 1).values
    rel["linhas_alvo_conflitante"] = int(df["flag_alvo_conflitante"].sum())
    rel["grupos_alvo_conflitante"] = int(
        df.loc[df["flag_alvo_conflitante"], feats].drop_duplicates().shape[0]
    )

    # R6 — IMC implausivel
    df["flag_imc_extremo"] = (df["imc"] > IMC_IMPLAUSIVEL).values
    rel["imc_extremo"] = int(df["flag_imc_extremo"].sum())

    # R7 — derivadas interpretaveis
    df["idade_anos"] = df["idade_faixa"].map(IDADE_PONTO_MEDIO).astype("uint8")
    df["renda_usd"] = df["renda_faixa"].map(RENDA_PONTO_MEDIO).astype("uint32")
    df["imc_faixa_oms"] = _faixa_oms(df["imc"].astype(float))
    df["comorbidades"] = (
        df[["hipertensao", "colesterol_alto", "avc", "doenca_cardiaca"]].sum(axis=1).astype("uint8")
    )
    df["dias_ruins_total"] = (
        df[["saude_mental_dias", "saude_fisica_dias"]].sum(axis=1).clip(upper=60).astype("uint8")
    )
    df["habitos_saudaveis"] = (
        df[["atividade_fisica", "frutas", "vegetais"]].sum(axis=1)
        + (1 - df["fumante"])
        + (1 - df["alcool_excessivo"])
    ).astype("uint8")

    rel["saida_linhas"] = int(len(df))
    rel["saida_colunas"] = int(df.shape[1])
    rel["distribuicao_alvo"] = df[TARGET].value_counts().sort_index().to_dict()
    rel["distribuicao_alvo_pct"] = (
        (df[TARGET].value_counts(normalize=True).sort_index() * 100).round(3).to_dict()
    )
    rel["memoria_mb"] = round(df.memory_usage(deep=True).sum() / 1e6, 2)
    return df, quarentena, rel


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, required=True)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--relatorio", type=Path, default=Path("data/processed/_relatorio_limpeza.json"))
    ap.add_argument("--quarentena", type=Path, default=Path("data/interim/quarentena.parquet"))
    args = ap.parse_args()

    bruto = pd.read_csv(args.entrada, sep=";")
    df, quarentena, rel = limpar(bruto)

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.saida, index=False, compression="zstd")
    if len(quarentena):
        args.quarentena.parent.mkdir(parents=True, exist_ok=True)
        quarentena.to_parquet(args.quarentena, index=False)

    args.relatorio.parent.mkdir(parents=True, exist_ok=True)
    args.relatorio.write_text(json.dumps(rel, ensure_ascii=False, indent=2, default=str),
                              encoding="utf-8")
    print(json.dumps(rel, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
