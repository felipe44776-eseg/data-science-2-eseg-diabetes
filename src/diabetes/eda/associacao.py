"""Associacao bivariada com tamanho de efeito -- ponderada ou nao.

Regra do projeto (ADR 0005 e `docs/02`): com n = 253.680 **todo p-valor da
zero**. P-valor nao distingue nada nesta escala. O que informa e:

  * **tamanho de efeito**  — V de Cramer, odds ratio, delta de Cliff
  * **intervalo de confianca** — e, sob amostra complexa, corrigido pelo DEFF

Todas as funcoes aceitam `peso`. Sem peso, e contagem simples. Com peso
(`_LLCPWT`), a estimativa e populacional -- e a inferencia usa o **n efetivo de
Kish**, nao o n de linhas, senao o IC sai absurdamente estreito.

Ver `docs/06-analise-exploratoria.md` para a leitura dos resultados.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

Z95 = 1.959963984540054


# --------------------------------------------------------------------------
# fundamentos ponderados
# --------------------------------------------------------------------------

def n_efetivo_kish(peso: pd.Series) -> float:
    """(Σw)² / Σw² — tamanho amostral efetivo sob pesos desiguais."""
    w = np.asarray(peso, dtype=float)
    return float(w.sum() ** 2 / (w**2).sum())


def deff(peso: pd.Series) -> float:
    """Efeito de desenho pelos pesos: n / n_efetivo."""
    return len(peso) / n_efetivo_kish(peso)


def tabela_2x2(exposto: pd.Series, desfecho: pd.Series,
               peso: pd.Series | None = None) -> np.ndarray:
    """Tabela [[a, b], [c, d]] = [[E+D+, E+D-], [E-D+, E-D-]], ponderada ou nao."""
    e = np.asarray(exposto, dtype=bool)
    d = np.asarray(desfecho, dtype=bool)
    w = np.ones(len(e)) if peso is None else np.asarray(peso, dtype=float)
    return np.array([
        [w[e & d].sum(), w[e & ~d].sum()],
        [w[~e & d].sum(), w[~e & ~d].sum()],
    ])


def odds_ratio(tab: np.ndarray, n_efetivo: float | None = None) -> dict:
    """OR com IC 95% por Woolf (log-OR).

    `n_efetivo` reescala a tabela para o n efetivo de Kish antes de calcular o
    erro-padrao. Sem isso, uma tabela ponderada (cuja soma e a populacao dos EUA,
    ~250 milhoes) produziria um IC de largura zero.
    """
    a, b, c, d = tab.ravel()
    if min(a, b, c, d) <= 0:
        return {"or": np.nan, "or_ic_baixo": np.nan, "or_ic_alto": np.nan}
    if n_efetivo is not None:
        escala = n_efetivo / tab.sum()
        a, b, c, d = a * escala, b * escala, c * escala, d * escala
    or_ = (a * d) / (b * c)
    ee = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return {
        "or": float(or_),
        "or_ic_baixo": float(np.exp(np.log(or_) - Z95 * ee)),
        "or_ic_alto": float(np.exp(np.log(or_) + Z95 * ee)),
    }


def cramer_v(tab: np.ndarray, n_efetivo: float | None = None) -> float:
    """V de Cramer. Com peso, o qui-quadrado usa a tabela reescalada ao n efetivo."""
    t = np.asarray(tab, dtype=float)
    if n_efetivo is not None:
        t = t * (n_efetivo / t.sum())
    if (t <= 0).any():
        return float("nan")
    chi2 = stats.chi2_contingency(t, correction=False)[0]
    n = t.sum()
    return float(np.sqrt(chi2 / (n * (min(t.shape) - 1))))


def classificar_v(v: float) -> str:
    """Convencao de Cohen para tabelas 2x2 (gl = 1)."""
    if np.isnan(v):
        return "—"
    if v < 0.10:
        return "desprezivel"
    if v < 0.30:
        return "pequeno"
    if v < 0.50:
        return "medio"
    return "grande"


def cliff_delta(a: pd.Series, b: pd.Series, amostra: int = 20_000,
                seed: int = 42) -> float:
    """Delta de Cliff — dominancia estocastica, robusta e sem suposicao de forma.

    δ = P(a > b) − P(a < b). Calculada por amostragem quando os grupos sao
    grandes: o produto cartesiano de 213k x 35k e inviavel e desnecessario.
    """
    rng = np.random.default_rng(seed)
    x = np.asarray(a.dropna())
    y = np.asarray(b.dropna())
    if len(x) == 0 or len(y) == 0:
        return float("nan")
    if len(x) > amostra:
        x = rng.choice(x, amostra, replace=False)
    if len(y) > amostra:
        y = rng.choice(y, amostra, replace=False)
    maior = (x[:, None] > y[None, :]).mean()
    menor = (x[:, None] < y[None, :]).mean()
    return float(maior - menor)


def tendencia_ordinal(nivel: pd.Series, desfecho: pd.Series,
                      peso: pd.Series | None = None) -> dict:
    """Teste de tendencia linear (Cochran-Armitage generalizado) + prevalencia por nivel.

    Responde "a prevalencia cresce monotonicamente com o nivel?", que e a
    pergunta certa para idade, renda, escolaridade e saude geral -- e que um
    qui-quadrado de independencia nao responde.
    """
    d = pd.DataFrame({"x": nivel, "y": desfecho}).dropna()
    w = np.ones(len(d)) if peso is None else np.asarray(peso.loc[d.index], dtype=float)
    x, y = d["x"].to_numpy(float), d["y"].to_numpy(float)

    sw = w.sum()
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    cov = np.average((x - mx) * (y - my), weights=w)
    r = cov / np.sqrt(np.average((x - mx) ** 2, weights=w) * np.average((y - my) ** 2, weights=w))

    n_ef = len(d) if peso is None else n_efetivo_kish(pd.Series(w))
    z = r * np.sqrt(max(n_ef - 1, 1))

    prev = (pd.DataFrame({"x": x, "y": y, "w": w})
            .groupby("x")
            .apply(lambda g: np.average(g["y"], weights=g["w"]) * 100, include_groups=False))
    return {
        "r_tendencia": float(r),
        "z_tendencia": float(z),
        "n_efetivo": float(n_ef),
        "prev_por_nivel": {int(k): round(float(v), 2) for k, v in prev.items()},
        "prev_min": round(float(prev.min()), 2),
        "prev_max": round(float(prev.max()), 2),
        "razao_extremos": round(float(prev.max() / prev.min()), 2) if prev.min() > 0 else np.nan,
        "monotonica": bool((np.diff(prev.to_numpy()) >= 0).all()
                           or (np.diff(prev.to_numpy()) <= 0).all()),
        "soma_pesos": float(sw),
    }


# --------------------------------------------------------------------------
# varredura
# --------------------------------------------------------------------------

def associacao_binarias(df: pd.DataFrame, variaveis: list[str], desfecho: pd.Series,
                        peso: pd.Series | None = None) -> pd.DataFrame:
    """Uma linha por variavel binaria: prevalencia nos dois grupos, RR, OR, V."""
    linhas = []
    for var in variaveis:
        ok = df[var].notna() & desfecho.notna()
        e = df.loc[ok, var].astype(bool)
        d = desfecho.loc[ok].astype(bool)
        w = None if peso is None else peso.loc[ok]
        n_ef = None if w is None else n_efetivo_kish(w)

        tab = tabela_2x2(e, d, w)
        (a, b), (c, dd) = tab
        p_exp = a / (a + b) * 100 if (a + b) else np.nan
        p_nao = c / (c + dd) * 100 if (c + dd) else np.nan
        v = cramer_v(tab, n_ef)
        linha = {
            "variavel": var,
            "n": int(ok.sum()),
            "n_efetivo": round(n_ef) if n_ef else int(ok.sum()),
            "%_exposto": round(float((a + b) / tab.sum() * 100), 2),
            "prev_expostos_%": round(float(p_exp), 2),
            "prev_nao_expostos_%": round(float(p_nao), 2),
            "risco_relativo": round(float(p_exp / p_nao), 2) if p_nao else np.nan,
            "v_cramer": round(v, 4),
            "efeito": classificar_v(v),
        }
        linha.update({k: round(v_, 3) for k, v_ in odds_ratio(tab, n_ef).items()})
        linhas.append(linha)
    return (pd.DataFrame(linhas)
            .sort_values("v_cramer", ascending=False)
            .reset_index(drop=True))


def associacao_ordinais(df: pd.DataFrame, variaveis: list[str], desfecho: pd.Series,
                        peso: pd.Series | None = None) -> pd.DataFrame:
    """Uma linha por variavel ordinal: gradiente de prevalencia e tendencia."""
    linhas = []
    for var in variaveis:
        ok = df[var].notna() & desfecho.notna()
        t = tendencia_ordinal(df.loc[ok, var], desfecho.loc[ok],
                              None if peso is None else peso.loc[ok])
        linhas.append({
            "variavel": var,
            "n": int(ok.sum()),
            "n_efetivo": round(t["n_efetivo"]),
            "prev_min_%": t["prev_min"],
            "prev_max_%": t["prev_max"],
            "razao_extremos": t["razao_extremos"],
            "r_tendencia": round(t["r_tendencia"], 4),
            "monotonica": t["monotonica"],
            "prev_por_nivel": t["prev_por_nivel"],
        })
    return (pd.DataFrame(linhas)
            .sort_values("razao_extremos", ascending=False)
            .reset_index(drop=True))
