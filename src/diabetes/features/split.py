"""Particionamento a prova de vazamento.

Motivacao (ADR 0002): 23.899 linhas sao identicas nas 22 colunas e 25.772 sao identicas
nas 21 features. Um `train_test_split` aleatorio coloca a MESMA linha em treino e teste,
o modelo memoriza e a metrica de teste sobe artificialmente.

A chave de grupo e o hash das 21 features. Todas as linhas que compartilham a chave
caem obrigatoriamente na mesma particao.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from diabetes.schema import ESQUEMA, TARGET

FEATURES = [c for c in ESQUEMA if c != TARGET]


def chave_de_grupo(df: pd.DataFrame, colunas: list[str] | None = None) -> pd.Series:
    """Hash estavel das features — linhas identicas recebem a mesma chave."""
    cols = colunas or FEATURES
    bruto = df[cols].astype("int64").astype(str).agg("|".join, axis=1)
    return bruto.map(lambda s: hashlib.blake2b(s.encode(), digest_size=8).hexdigest())


def particionar(
    df: pd.DataFrame,
    n_folds: int = 5,
    frac_holdout: float = 0.20,
    seed: int = 42,
) -> pd.DataFrame:
    """Devolve o df com as colunas `grupo`, `holdout` (bool) e `fold` (-1 no holdout).

    O holdout e separado por grupo ANTES dos folds e so deve ser tocado uma vez, no fim.
    """
    out = df.copy()
    out["grupo"] = chave_de_grupo(out)

    rng = np.random.default_rng(seed)
    grupos = out["grupo"].unique()
    sorteio = rng.permutation(len(grupos))
    n_hold = int(round(len(grupos) * frac_holdout))
    grupos_holdout = set(grupos[sorteio[:n_hold]])
    out["holdout"] = out["grupo"].isin(grupos_holdout)

    out["fold"] = -1
    treino = out.loc[~out["holdout"]]
    sgkf = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    for k, (_, idx_val) in enumerate(
        sgkf.split(treino, treino[TARGET], groups=treino["grupo"])
    ):
        out.loc[treino.index[idx_val], "fold"] = k
    return out


def _main() -> None:
    import argparse
    import json
    from pathlib import Path

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--silver", type=Path,
                    default=Path("data/processed/diabetes_silver.parquet"))
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/folds.parquet"))
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = pd.read_parquet(args.silver)
    part = particionar(df, n_folds=args.folds, seed=args.seed)
    auditoria = auditar_vazamento(part)
    if auditoria["grupos_cruzando_holdout"] or auditoria["grupos_cruzando_folds"]:
        raise SystemExit(f"VAZAMENTO detectado: {auditoria}")

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    part[["grupo", "holdout", "fold"]].to_parquet(args.saida, index=False)
    print(json.dumps({
        **auditoria,
        "linhas": int(len(part)),
        "holdout_%": round(float(part["holdout"].mean() * 100), 2),
        "saida": str(args.saida),
    }, ensure_ascii=False, indent=2))


def auditar_vazamento(df: pd.DataFrame) -> dict:
    """Verifica que nenhum grupo cruza particoes. Usado em teste e em CI."""
    por_grupo = df.groupby("grupo").agg(
        n_particoes=("holdout", "nunique"), n_folds=("fold", "nunique")
    )
    return {
        "grupos": int(len(por_grupo)),
        "grupos_cruzando_holdout": int((por_grupo["n_particoes"] > 1).sum()),
        "grupos_cruzando_folds": int(
            (df.loc[~df["holdout"]].groupby("grupo")["fold"].nunique() > 1).sum()
        ),
    }


if __name__ == "__main__":
    _main()
