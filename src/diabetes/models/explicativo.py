"""Modelagem explicativa: odds ratio ajustado, nao predicao.

Tres especificacoes rodadas lado a lado (`docs/02-proposta-de-analise.md` A3).
A **instabilidade dos coeficientes entre elas e o resultado**, nao um problema:
mostra quanto do "efeito" de um fator na verdade passa por acesso ao sistema de
saude ou por consequencia da doenca.

  M1 · risco puro  — exclui proxies de acesso e possiveis consequencias
  M2 · clinico     — M1 + saude geral, dificuldade de caminhar, dias ruins
  M3 · completo    — as 21 variaveis

E cada uma roda em duas bases (`docs/06`):
  A · arquivo entregue, sem peso
  B · BRFSS completo, ponderado por `_LLCPWT`

Sobre o alvo: 0 < 1 < 2 e **ordinal**. Ajustamos o modelo de odds proporcionais
e **testamos a hipotese** comparando os dois logits cumulativos separados
(versao pratica do teste de Brant). Se a hipotese cair -- e esperamos que caia,
porque pre-diabetes tem mecanismo de deteccao proprio -- a rejeicao e um achado,
e reportamos a multinomial.

Nota sobre inferencia ponderada: usamos GLM binomial com `freq_weights`
reescalados ao n efetivo de Kish. E uma aproximacao do erro-padrao correto;
a linearizacao de Taylor com estrato e PSU (via `samplics`) seria exata. A
aproximacao ja corrige a ordem de grandeza do IC, que e o erro que importa.

Uso:
    python -m diabetes.models.explicativo --xpt data/external/brfss2015/LLCP2015.XPT
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from diabetes.eda.associacao import n_efetivo_kish
from diabetes.eda.comparativo import carregar_bases
from diabetes.schema import (
    ESQUEMA,
    POSSIVEIS_CONSEQUENCIAS,
    PROXIES_DE_ACESSO,
    TARGET,
)

TODAS = [c for c in ESQUEMA if c != TARGET]
M1 = [c for c in TODAS if c not in PROXIES_DE_ACESSO + POSSIVEIS_CONSEQUENCIAS]
M2 = [c for c in TODAS if c not in PROXIES_DE_ACESSO]
M3 = TODAS

ESPECIFICACOES = {"M1_risco_puro": M1, "M2_clinico": M2, "M3_completo": M3}

#: variaveis continuas/ordinais padronizadas para que o OR seja por desvio-padrao,
#: e nao por unidade arbitraria (1 ponto de IMC vs 1 faixa etaria nao sao comparaveis)
PADRONIZAR = ["imc", "idade_faixa", "escolaridade", "renda_faixa",
              "saude_geral", "saude_mental_dias", "saude_fisica_dias"]


def _preparar(df: pd.DataFrame, variaveis: list[str], peso: pd.Series | None):
    cols = variaveis + [TARGET]
    d = df[cols].dropna()
    w = None if peso is None else peso.loc[d.index]
    X = d[variaveis].astype(float).copy()
    escalas = {}
    for c in variaveis:
        if c in PADRONIZAR:
            mu, sd = X[c].mean(), X[c].std()
            X[c] = (X[c] - mu) / sd
            escalas[c] = {"media": round(float(mu), 3), "dp": round(float(sd), 3)}
    X = sm.add_constant(X, has_constant="add")
    return X, d[TARGET].astype(int), w, escalas


def _ajustar_logit(X: pd.DataFrame, y: pd.Series, w: pd.Series | None) -> pd.DataFrame:
    """GLM binomial. Com peso, reescala para o n efetivo de Kish antes do ajuste."""
    if w is None:
        modelo = sm.GLM(y, X, family=sm.families.Binomial())
    else:
        fw = np.asarray(w, dtype=float)
        fw = fw * (n_efetivo_kish(w) / fw.sum())
        modelo = sm.GLM(y, X, family=sm.families.Binomial(), freq_weights=fw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = modelo.fit()
    ic = res.conf_int()
    return pd.DataFrame({
        "coef": res.params,
        "or": np.exp(res.params),
        "or_ic_baixo": np.exp(ic[0]),
        "or_ic_alto": np.exp(ic[1]),
        "z": res.tvalues,
    }).drop(index="const", errors="ignore")


def ajustar_especificacoes(df: pd.DataFrame, peso: pd.Series | None) -> dict:
    """M1/M2/M3 para o desfecho binario diabetes(2) vs resto."""
    saida = {}
    for nome, variaveis in ESPECIFICACOES.items():
        X, y, w, escalas = _preparar(df, variaveis, peso)
        tab = _ajustar_logit(X, (y == 2).astype(int), w)
        saida[nome] = {
            "n": int(len(y)),
            "n_efetivo": round(float(n_efetivo_kish(w))) if w is not None else int(len(y)),
            "escalas": escalas,
            "coeficientes": tab.round(4).to_dict("index"),
        }
    return saida


def testar_odds_proporcionais(df: pd.DataFrame, variaveis: list[str],
                              peso: pd.Series | None) -> pd.DataFrame:
    """Versao pratica do teste de Brant.

    O modelo de odds proporcionais assume que o efeito de cada variavel e o
    mesmo nos dois pontos de corte do alvo ordinal. Ajustamos os dois logits
    cumulativos separados e comparamos:

        corte 1 :  {0}      vs  {1, 2}    "tem alguma alteracao glicemica?"
        corte 2 :  {0, 1}   vs  {2}       "tem diabetes estabelecido?"

    Se os OR divergirem materialmente, a hipotese cai e a multinomial e a
    especificacao correta.
    """
    X, y, w, _ = _preparar(df, variaveis, peso)
    c1 = _ajustar_logit(X, (y >= 1).astype(int), w)
    c2 = _ajustar_logit(X, (y >= 2).astype(int), w)
    comp = pd.DataFrame({
        "or_corte1_alteracao": c1["or"].round(3),
        "or_corte2_diabetes": c2["or"].round(3),
        "razao": (c2["or"] / c1["or"]).round(3),
        "divergencia_%": ((c2["or"] / c1["or"] - 1) * 100).round(1),
        # sobreposicao de IC: criterio conservador de "mesmo efeito"
        "ic_sobrepoe": [
            not (a_hi < b_lo or b_hi < a_lo)
            for a_lo, a_hi, b_lo, b_hi in zip(
                c1["or_ic_baixo"], c1["or_ic_alto"],
                c2["or_ic_baixo"], c2["or_ic_alto"], strict=True)
        ],
    })
    return comp.sort_values("divergencia_%", key=abs, ascending=False)


def comparar_pre_vs_diabetes(df: pd.DataFrame, variaveis: list[str],
                             peso: pd.Series | None) -> pd.DataFrame:
    """Multinomial desmontada: cada classe contra a referencia, separadamente.

    Por que isto e necessario: o teste de odds proporcionais em `testar_odds_
    proporcionais` compara {0} vs {1,2} com {0,1} vs {2}. Como a classe 1 tem
    so 1,6% da amostra, os dois contrastes sao quase o mesmo por construcao --
    o teste **nao tem poder** para detectar violacao, e a nao-rejeicao nao e
    evidencia de proporcionalidade.

    O contraste informativo e direto:

        classe 1 vs 0  —  pre-diabetes contra sem diabetes
        classe 2 vs 0  —  diabetes contra sem diabetes

    Se um fator tiver efeito materialmente diferente nos dois, o alvo nao e um
    unico continuum latente e a multinomial e a especificacao correta.
    """
    cols = variaveis + [TARGET]
    d = df[cols].dropna()
    w = None if peso is None else peso.loc[d.index]

    def ajustar(classe: int) -> pd.DataFrame:
        sel = d[TARGET].isin([0, classe])
        X, y, _, _ = _preparar(d.loc[sel], variaveis, None)
        ww = None if w is None else w.loc[d.index[sel]]
        return _ajustar_logit(X, (y == classe).astype(int), ww)

    c1, c2 = ajustar(1), ajustar(2)
    return pd.DataFrame({
        "or_pre_vs_sem": c1["or"].round(3),
        "ic_pre": c1.apply(lambda r: f"[{r['or_ic_baixo']:.2f}; {r['or_ic_alto']:.2f}]", axis=1),
        "or_diab_vs_sem": c2["or"].round(3),
        "ic_diab": c2.apply(lambda r: f"[{r['or_ic_baixo']:.2f}; {r['or_ic_alto']:.2f}]", axis=1),
        "razao_diab_pre": (c2["or"] / c1["or"]).round(2),
        "ic_sobrepoe": [
            not (a_hi < b_lo or b_hi < a_lo)
            for a_lo, a_hi, b_lo, b_hi in zip(
                c1["or_ic_baixo"], c1["or_ic_alto"],
                c2["or_ic_baixo"], c2["or_ic_alto"], strict=True)
        ],
    }).sort_values("razao_diab_pre", ascending=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xpt", type=Path, required=True)
    ap.add_argument("--silver", type=Path, default=Path("data/processed/diabetes_silver.parquet"))
    ap.add_argument("--saida", type=Path, default=Path("data/processed/gold/_modelo_explicativo.json"))
    args = ap.parse_args()

    print("carregando bases…")
    a, b = carregar_bases(args.xpt, args.silver)
    peso = b["_LLCPWT"]

    print("ajustando M1/M2/M3 na base A (sem peso)…")
    res_a = ajustar_especificacoes(a, None)
    print("ajustando M1/M2/M3 na base B (ponderada)…")
    res_b = ajustar_especificacoes(b, peso)

    print("testando odds proporcionais (base B)…")
    brant = testar_odds_proporcionais(b, M2, peso)
    print("contrastando pre-diabetes vs diabetes (base B)…")
    pre_vs_diab = comparar_pre_vs_diabetes(b, M3, peso)

    # comparacao dos OR de M1 entre bases
    ca = pd.DataFrame(res_a["M1_risco_puro"]["coeficientes"]).T
    cb = pd.DataFrame(res_b["M1_risco_puro"]["coeficientes"]).T
    comp_m1 = pd.DataFrame({
        "A_OR": ca["or"].round(3), "B_OR": cb["or"].round(3),
        "B_ic": cb.apply(lambda r: f"[{r['or_ic_baixo']:.2f}; {r['or_ic_alto']:.2f}]", axis=1),
        "atenuacao_%": ((ca["or"] / cb["or"] - 1) * 100).round(1),
    }).sort_values("B_OR", ascending=False)

    # estabilidade de M1 -> M2 -> M3 na base B
    estab = pd.DataFrame({
        n: pd.DataFrame(res_b[n]["coeficientes"]).T["or"].round(3)
        for n in ESPECIFICACOES
    })
    estab["desloc_M1_M3_%"] = ((estab["M3_completo"] / estab["M1_risco_puro"] - 1) * 100).round(1)

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps({
        "base_A_sem_peso": res_a,
        "base_B_ponderada": res_b,
        "odds_proporcionais": brant.to_dict("index"),
        "pre_vs_diabetes": pre_vs_diab.to_dict("index"),
        "comparacao_M1_entre_bases": comp_m1.to_dict("index"),
        "estabilidade_M1_M2_M3": estab.to_dict("index"),
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print("\n=== M1 (risco puro): OR ajustado, base A vs base B ===")
    print(comp_m1.to_string())
    print("\n=== ESTABILIDADE M1 -> M2 -> M3 (base B ponderada) ===")
    print(estab.to_string())
    print("\n=== ODDS PROPORCIONAIS: os dois cortes tem o mesmo efeito? ===")
    print(brant.to_string())
    print("\n=== PRE-DIABETES vs DIABETES: o mesmo fator age igual nos dois? ===")
    print(pre_vs_diab.to_string())


if __name__ == "__main__":
    main()
