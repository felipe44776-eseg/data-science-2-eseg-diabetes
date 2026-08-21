"""Frente 2 — Positive-Unlabeled: de "quem consta" para "quem tem".

O problema
----------
O rotulo `s` do BRFSS nao e a doenca, e o **diagnostico autorrelatado**. Segundo o
NHANES, **27,6% dos adultos com diabetes nos EUA nao sabem** (`docs/03` §2.1). Logo:

    s = 1  =>  y = 1     quem foi diagnosticado tem a doenca
    s = 0  =>  y = ?     nao rotulado, nao negativo

Formalmente isto e **Positive-Unlabeled learning**, nao classificacao supervisionada.
Tratar s = 0 como negativo treina o modelo a reproduzir o processo de diagnostico —
que `docs/05` mostrou ser fortemente enviesado por acesso.

As tres formulacoes, em ordem de realismo
------------------------------------------
Seja c = P(s=1 | y=1), a **frequencia de rotulagem**.

  **SCAR** (Elkan-Noto, 2008) — `c` constante:  P(y=1|x) = P(s=1|x) / c
      Simples e fechado. Supoe que o diagnostico e independente do perfil dado
      que a pessoa tem a doenca. **Sabemos que isso e falso aqui.**

  **SCAR ponderado** — usa os nao rotulados de verdade, com peso
      w(x) = (1-c)/c · P(s=1|x)/(1-P(s=1|x)), em vez de so reescalar o escore.

  **SAR** (Bekker & Davis, 2020) — `c(x)` depende do perfil. E o caso real: quem
      tem plano de saude, faz check-up e tomou vacina tem muito mais chance de ser
      diagnosticado tendo a mesma doenca. Modelamos c(x) com o bloco de acesso,
      calibrado para que a media populacional bata com o ancoradouro do NHANES.

Ancoradouro e sensibilidade
---------------------------
`c` nao e identificavel so com os dados (Blanchard et al.): e preciso uma
suposicao externa. Usamos o NHANES como ancoradouro e **reportamos a analise ao
longo de uma faixa** de c, porque o valor de 2021-2023 nao e o de 2015. Alem
disso estimamos c pelos proprios dados (BBE, Garg et al. 2021) e comparamos — se
as duas estimativas discordarem muito, a suposicao SCAR esta quebrada, o que e
por si so um resultado.

Uso:
    python -m diabetes.models.pu
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

from diabetes.features.expandido import ACESSO_E_DETECCAO, RISCO
from diabetes.models.expandido import particionar
from diabetes.pipeline.estado import registrar

SEED = 42
ENTRADA = Path("data/processed/gold/brfss_expandido.parquet")

#: NHANES / CDC National Diabetes Statistics Report: 27,6% dos adultos com
#: diabetes nao sabem => c = P(s=1|y=1) = 0,724. Valor de ago/2021-ago/2023.
C_NHANES = 0.724

#: faixa de sensibilidade. O subdiagnostico em 2015 era plausivelmente MENOR que
#: hoje (menos rastreamento) ou MAIOR (menos cobertura) — a faixa cobre as duas.
FAIXA_C = [0.65, 0.70, 0.724, 0.78, 0.85, 0.90]

#: limites de c(x) na formulacao SAR. Ver a nota em `sar()`.
C_MIN, C_MAX = 0.50, 0.95


def _modelo():
    return CalibratedClassifierCV(
        HistGradientBoostingClassifier(
            max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
            min_samples_leaf=50, l2_regularization=1.0, early_stopping=True,
            validation_fraction=0.12, random_state=SEED),
        method="isotonic", cv=3)


def ajustar_ps(df: pd.DataFrame, cols: list[str], te: np.ndarray) -> np.ndarray:
    """P(s=1|x) calibrado — o classificador tradicional, que e o insumo do PU."""
    y = df["diabetes"].to_numpy()
    X = df[cols].astype("float32").to_numpy()
    m = _modelo()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X[~te], y[~te])
    p = np.zeros(len(df))
    p[te] = m.predict_proba(X[te])[:, 1]
    p[~te] = m.predict_proba(X[~te])[:, 1]   # in-sample, so para diagnostico
    return p


# --------------------------------------------------------------------------
# estimacao de c pelos proprios dados
# --------------------------------------------------------------------------

def estimar_c_bbe(p_s: np.ndarray, s: np.ndarray, quantis: int = 50) -> dict:
    """Best Bin Estimation (Garg et al. 2021), versao pratica.

    Ideia: numa regiao do espaco onde *todos* tem a doenca, a fracao rotulada
    tende a c. Percorremos os quantis do escore de cima para baixo e olhamos a
    fracao com s=1 no topo — o supremo dessa fracao estima c.

    Se o valor estimado for muito menor que o do NHANES, a leitura correta nao e
    "o NHANES esta errado": e que **nao existe regiao pura** de positivos no
    espaco de 60 variaveis de questionario. Isso mede o teto de informacao de
    novo, agora por outro caminho.
    """
    ordem = np.argsort(-p_s)
    s_ord = s[ordem]
    n = len(s_ord)
    fracoes = []
    for q in range(1, quantis + 1):
        k = int(n * q / quantis)
        fracoes.append({"topo_%": round(q / quantis * 100, 1),
                        "fracao_rotulada": round(float(s_ord[:k].mean()), 4)})
    topo = max(f["fracao_rotulada"] for f in fracoes)
    return {"c_estimado_bbe": round(topo, 4), "curva": fracoes[:12]}


# --------------------------------------------------------------------------
# as tres formulacoes
# --------------------------------------------------------------------------

def scar(p_s: np.ndarray, c: float) -> np.ndarray:
    """Elkan-Noto: P(y=1|x) = P(s=1|x) / c."""
    return np.clip(p_s / c, 0, 1)


def scar_ponderado(p_s: np.ndarray, s: np.ndarray, c: float) -> np.ndarray:
    """Peso de Elkan-Noto sobre os nao rotulados.

    Cada exemplo com s=0 e tratado como positivo com peso w(x) e negativo com
    peso 1-w(x), onde w(x) = (1-c)/c · p_s/(1-p_s). Devolvemos w, que e a
    probabilidade de o nao rotulado ser um positivo oculto.
    """
    w = (1 - c) / c * p_s / np.clip(1 - p_s, 1e-9, None)
    w = np.clip(w, 0, 1)
    return np.where(s == 1, 1.0, w)


def sar(df: pd.DataFrame, p_s: np.ndarray, te: np.ndarray, c_medio: float) -> dict:
    """Propensao de diagnostico c(x) modelada com o bloco de acesso.

    Entre os **rotulados positivos** nao ha variacao de y (todos tem y=1), entao
    a variacao de s naquele grupo nao identifica c(x) diretamente. O que fazemos
    e o pratico e declarado: modelar a **propensao de rastreamento** — quem faz
    exame, tem medico, toma vacina — e usa-la como proxy de c(x), reescalada
    para que a media ponderada pelo risco bata com `c_medio`.

    Suposicao explicita: dado o perfil de risco, quem e mais rastreado tem mais
    chance de ter o diagnostico registrado. E a hipotese central de `docs/05`.
    """
    # o alvo auxiliar e derivado de CHOLCHK, entao CHOLCHK e BLOODCHO saem das
    # features — senao o modelo de propensao apenas se copia (vazamento)
    acesso = [c for c in ACESSO_E_DETECCAO
              if c in df.columns and c not in ("CHOLCHK", "BLOODCHO")]
    # alvo auxiliar: "foi rastreado" = fez exame de colesterol nos ultimos 5 anos
    rastreado = (df["CHOLCHK"] == 1).astype(int).to_numpy()
    X = df[acesso].astype("float32").to_numpy()
    m = _modelo()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X[~te], rastreado[~te])
    prop = m.predict_proba(X)[:, 1]

    # Reescala para que a media ponderada pelo risco seja c_medio, e LIMITA a
    # faixa. O limite nao e cosmetico: c(x) proximo de zero faria p_s/c(x)
    # explodir e o ranking passaria a medir "nao foi testado" em vez de "tem
    # risco e nao foi testado", que e a pergunta.
    peso = p_s / p_s.sum()
    prop = prop * (c_medio / float(np.sum(prop * peso)))
    prop = np.clip(prop, C_MIN, C_MAX)
    p_y = np.clip(p_s / prop, 0, 1)
    return {"propensao": prop, "p_y": p_y, "variaveis": acesso,
            "faixa_c": [C_MIN, C_MAX]}


# --------------------------------------------------------------------------

def perfil_dos_ocultos(df: pd.DataFrame, p_y: np.ndarray, p_s: np.ndarray,
                       n_top: int = 20_000) -> dict:
    """Quem sao os provaveis positivos ocultos, e como diferem dos diagnosticados."""
    s = df["diabetes"].to_numpy()
    nao_rot = s == 0
    risco_oculto = np.where(nao_rot, p_y - p_s, -1.0)  # ganho do PU sobre o ingenuo
    idx = np.argsort(-risco_oculto)[:n_top]

    def resumo(m: np.ndarray) -> dict:
        return {
            "n": int(m.sum()),
            "idade_media": round(float(df.loc[m, "_AGE80"].mean()), 1),
            "imc_medio": round(float(df.loc[m, "_BMI5"].mean() / 100), 1),
            "%_hipertensao": round(float((df.loc[m, "_RFHYPE5"] == 2).mean() * 100), 1),
            "%_fez_exame_colesterol": round(float((df.loc[m, "CHOLCHK"] == 1).mean() * 100), 1),
            "%_com_plano": round(float((df.loc[m, "HLTHPLN1"] == 1).mean() * 100), 1),
            "%_sem_consulta_por_custo": round(float((df.loc[m, "MEDCOST"] == 1).mean() * 100), 1),
            "%_check_up_no_ano": round(float((df.loc[m, "CHECKUP1"] == 1).mean() * 100), 1),
            "renda_mediana_faixa": float(df.loc[m, "INCOME2"].median()),
            "%_minoria": round(float((df.loc[m, "_RACEGR3"] != 1).mean() * 100), 1),
        }

    mask_ocultos = np.zeros(len(df), bool)
    mask_ocultos[idx] = True
    return {
        "provaveis_ocultos": resumo(mask_ocultos),
        "diagnosticados": resumo(s == 1),
        "demais_nao_rotulados": resumo(nao_rot & ~mask_ocultos),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, default=ENTRADA)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_frente2_pu.json"))
    args = ap.parse_args()

    df = pd.read_parquet(args.entrada)
    te = particionar(df)
    s = df["diabetes"].to_numpy()
    w_pop = df["_LLCPWT"].to_numpy(float)
    registrar("frente2", "inicio", n=len(df))

    print("  ajustando P(s=1|x) com as 60 variaveis de risco…")
    p_s = ajustar_ps(df, RISCO, te)
    prev_s = float(np.average(s, weights=w_pop))
    print(f"    prevalencia de DIAGNOSTICO (ponderada): {prev_s*100:.3f}%")

    print("\n  estimando c pelos proprios dados (BBE)…")
    bbe = estimar_c_bbe(p_s, s)
    print(f"    c estimado pelos dados : {bbe['c_estimado_bbe']:.4f}")
    print(f"    c do NHANES            : {C_NHANES:.4f}")
    print("    (BBE << NHANES significa que nao ha regiao pura de positivos no "
          "espaco de questionario — nao que o NHANES esteja errado)")

    print("\n  sensibilidade a c — prevalencia VERDADEIRA implicada:")
    sens = []
    for c in FAIXA_C:
        p_y = scar(p_s, c)
        prev_y = float(np.average(p_y, weights=w_pop))
        ocultos = prev_y - prev_s
        sens.append({
            "c": c,
            "subdiagnostico_%": round((1 - c) * 100, 1),
            "prev_verdadeira_%": round(prev_y * 100, 3),
            "prev_diagnosticada_%": round(prev_s * 100, 3),
            "ocultos_pp": round(ocultos * 100, 3),
            "ocultos_na_amostra": int(round((p_y - s).clip(0).sum())),
        })
        print(f"    c={c:.3f}  subdiag {(1-c)*100:4.1f}%  ->  prevalencia verdadeira "
              f"{prev_y*100:6.3f}%  ({ocultos*100:+.2f} p.p. ocultos)")

    print("\n  formulacao SAR (c depende do acesso)…")
    r_sar = sar(df, p_s, te, C_NHANES)
    prev_sar = float(np.average(r_sar["p_y"], weights=w_pop))
    print(f"    propensao de rastreamento: min {r_sar['propensao'].min():.3f}  "
          f"mediana {np.median(r_sar['propensao']):.3f}  max {r_sar['propensao'].max():.3f}")
    print(f"    prevalencia verdadeira sob SAR : {prev_sar*100:.3f}%")
    print(f"    contra SCAR com o mesmo c      : {sens[2]['prev_verdadeira_%']:.3f}%")

    print("\n  perfil dos provaveis positivos ocultos…")
    perfil = perfil_dos_ocultos(df, r_sar["p_y"], p_s)
    print(pd.DataFrame(perfil).T.to_string())

    saida = {
        "premissa": {
            "c_nhanes": C_NHANES,
            "fonte": "NCHS Data Brief 516 / National Diabetes Statistics Report",
            "nota": "c = P(diagnosticado | tem diabetes) = 1 - 0,276",
        },
        "prevalencia_diagnosticada_%": round(prev_s * 100, 3),
        "bbe": bbe,
        "sensibilidade_a_c": sens,
        "sar": {
            "prevalencia_verdadeira_%": round(prev_sar * 100, 3),
            "variaveis_de_propensao": r_sar["variaveis"],
            "propensao_min": round(float(r_sar["propensao"].min()), 4),
            "propensao_mediana": round(float(np.median(r_sar["propensao"])), 4),
            "propensao_max": round(float(r_sar["propensao"].max()), 4),
        },
        "perfil": perfil,
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("frente2", "fim")


if __name__ == "__main__":
    main()
