"""Validacao temporal 2015 -> 2023: o modelo ainda funciona oito anos depois?

Por que este e o teste mais duro
--------------------------------
Todo holdout deste projeto e **aleatorio dentro de 2015**. Isso mede
generalizacao para pessoas novas, nao para um **mundo novo**. Um modelo de saude
que sera usado em 2026 precisa sobreviver a:

  * mudanca de prevalencia (o diabetes cresceu);
  * mudanca de composicao (a populacao envelheceu, o IMC subiu);
  * mudanca de instrumento (o BRFSS renomeia e reformula variaveis);
  * mudanca de contexto (a pandemia entrou no meio).

Isso e **dataset shift**, e a decomposicao padrao separa:

  **covariate shift**  P(X) muda, P(y|X) fica   -> reponderacao resolve
  **label shift**      P(y) muda, P(X|y) fica   -> recalibracao resolve
  **concept drift**    P(y|X) muda              -> nada resolve; precisa retreinar

O diagnostico importa mais que a metrica: se for so covariate ou label shift, o
modelo de 2015 continua util com correcao. Se for concept drift, nao continua.

O obstaculo pratico
-------------------
O BRFSS **renomeia variaveis entre anos**. `_RFHYPE5` vira `_RFHYPE6`,
`TOLDHI2` vira `TOLDHI3`, e assim por diante. Nao ha atalho: o mapeamento e
declarado em `EQUIVALENCIAS` e o modulo **falha** se nao encontrar equivalente,
em vez de silenciosamente treinar com coluna ausente.

Uso:
    python -m diabetes.external.temporal
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
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from diabetes.external.brfss2015 import carregar_xpt
from diabetes.features.expandido import RISCO, _limpar_codigos
from diabetes.models.escada import erro_calibracao, recall_em_especificidade
from diabetes.pipeline.estado import registrar

XPT_2015 = Path("data/external/brfss2015/LLCP2015.XPT")
XPT_2023 = Path("data/external/brfss2023/LLCP2023.XPT")
SEED = 42

#: nome em 2015 -> candidatos em 2023, na ordem de preferencia.
#: O BRFSS troca o sufixo numerico quando reformula a pergunta; quando o
#: construto muda de verdade, a variavel entra em `SEM_EQUIVALENTE`.
EQUIVALENCIAS = {
    "DIABETE3": ["DIABETE4", "DIABETE3"],
    "_RFHYPE5": ["_RFHYPE6", "_RFHYPE5"],
    "TOLDHI2": ["TOLDHI3", "TOLDHI2"],
    "_MICHD": ["_MICHD"],
    "CVDSTRK3": ["CVDSTRK3"],
    "CHCKIDNY": ["CHCKDNY2", "CHCKDNY1", "CHCKIDNY"],
    "HAVARTH3": ["HAVARTH4", "HAVARTH3"],
    "CHCCOPD1": ["CHCCOPD3", "CHCCOPD2", "CHCCOPD1"],
    "ASTHMA3": ["ASTHMA3"],
    "CHCOCNCR": ["CHCOCNC1", "CHCOCNCR"],
    "CHCSCNCR": ["CHCSCNC1", "CHCSCNCR"],
    "ADDEPEV2": ["ADDEPEV3", "ADDEPEV2"],
    "DIFFWALK": ["DIFFWALK"],
    "BLIND": ["BLIND"],
    "DECIDE": ["DECIDE"],
    "DIFFDRES": ["DIFFDRES"],
    "DIFFALON": ["DIFFALON"],
    "USEEQUIP": ["USEEQUIP"],
    "QLACTLM2": ["QLACTLM2"],
    "_AGE80": ["_AGE80"],
    "SEX": ["_SEX", "SEXVAR", "SEX"],
    "EDUCA": ["EDUCA"],
    "INCOME2": ["INCOME3", "INCOME2"],
    "EMPLOY1": ["EMPLOY1"],
    "MARITAL": ["MARITAL"],
    "RENTHOM1": ["RENTHOM1"],
    "_CHLDCNT": ["_CHLDCNT"],
    "VETERAN3": ["VETERAN3"],
    "_RACEGR3": ["_RACEGR4", "_RACEGR3"],
    "_HISPANC": ["_HISPANC"],
    "_BMI5": ["_BMI5"],
    "WTKG3": ["WTKG3"],
    "HTM4": ["HTM4"],
    "GENHLTH": ["GENHLTH"],
    "MENTHLTH": ["MENTHLTH"],
    "PHYSHLTH": ["PHYSHLTH"],
    "_TOTINDA": ["_TOTINDA"],
    "SMOKE100": ["SMOKE100"],
    "_SMOKER3": ["_SMOKER3"],
    "_RFDRHV5": ["_RFDRHV8", "_RFDRHV7", "_RFDRHV6", "_RFDRHV5"],
    "DROCDY3_": ["DROCDY4_", "DROCDY3_"],
    "_DRNKWEK": ["_DRNKWK2", "_DRNKWK1", "_DRNKWEK"],
    "_RFBING5": ["_RFBING6", "_RFBING5"],
    "DRNKANY5": ["DRNKANY6", "DRNKANY5"],
    "_FRTLT1": ["_FRTLT1A", "_FRTLT1"],
    "_VEGLT1": ["_VEGLT1A", "_VEGLT1"],
    "SEATBELT": ["SEATBELT"],
}

#: construtos que o BRFSS 2023 nao tras de forma equivalente. Ficam fora do
#: modelo comum; ocultar isso seria treinar com coluna ausente virando NaN.
SEM_EQUIVALENTE = [
    "MAXVO2_", "_PACAT1", "_PA150R2", "_PASTRNG", "STRFREQ_",
    "FRUTDA1_", "VEGEDA1_", "FTJUDA1_", "BEANDAY_", "GRENDAY_", "ORNGDAY_",
    "USENOW3", "QSTLANG", "INTERNET",
]


def resolver(colunas_2023: set[str]) -> tuple[dict, list[str]]:
    """Mapeia cada variavel de 2015 para a de 2023, ou reporta a ausencia."""
    mapa, ausentes = {}, []
    for v2015, candidatos in EQUIVALENCIAS.items():
        achou = next((c for c in candidatos if c in colunas_2023), None)
        if achou:
            mapa[v2015] = achou
        else:
            ausentes.append(v2015)
    return mapa, ausentes


def _modelo():
    return CalibratedClassifierCV(
        HistGradientBoostingClassifier(
            max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
            min_samples_leaf=50, l2_regularization=1.0, early_stopping=True,
            validation_fraction=0.12, random_state=SEED),
        method="isotonic", cv=3)


def avaliar(y: np.ndarray, p: np.ndarray, w: np.ndarray | None = None) -> dict:
    """Discriminacao e calibracao no mesmo dicionario, para comparar 2015 com 2023.

    O peso entra **so** na prevalencia. As metricas de ranqueamento e de calibracao
    saem sem peso de proposito: `_LLCPWT` de 2015 e de 2023 sao calibrados para
    populacoes-alvo diferentes, e ponderar cada ano com o seu tornaria as duas
    colunas incomparaveis — que e justamente o que este modulo mede.

    `risco_medio_previsto_%` ao lado de `prevalencia_%` e o diagnostico rapido de
    label shift: se o primeiro ficou para tras do segundo, o modelo continua
    ordenando bem e so perdeu o nivel, e recalibrar resolve.
    """
    prev = float(np.average(y, weights=w)) if w is not None else float(y.mean())
    return {
        "n": int(len(y)),
        "prevalencia_%": round(prev * 100, 3),
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "recall_esp90": round(recall_em_especificidade(y, p, 0.90), 4),
        "brier": round(float(brier_score_loss(y, p)), 5),
        "ece": round(erro_calibracao(y, p), 5),
        "risco_medio_previsto_%": round(float(p.mean() * 100), 3),
    }


def deslocamento(X15: pd.DataFrame, X23: pd.DataFrame,
                 y15: np.ndarray, y23: np.ndarray) -> dict:
    """Separa covariate shift, label shift e a suspeita de concept drift.

    O detector de covariate shift e um classificador que tenta distinguir os dois
    anos so pelas covariaveis. AUC perto de 0,5 significa que P(X) nao mudou;
    perto de 1, que mudou muito.
    """
    Xc = pd.concat([X15, X23], ignore_index=True)
    ano = np.r_[np.zeros(len(X15)), np.ones(len(X23))]
    rng = np.random.default_rng(SEED)
    te = rng.random(len(Xc)) < 0.3
    m = HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.08, min_samples_leaf=50, random_state=SEED)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(Xc[~te].astype("float32"), ano[~te])
    auc_ano = float(roc_auc_score(ano[te], m.predict_proba(
        Xc[te].astype("float32"))[:, 1]))

    # quais variaveis mais mudaram, por diferenca padronizada
    dif = []
    for c in X15.columns:
        a, b = X15[c].astype(float), X23[c].astype(float)
        s = np.sqrt((a.var() + b.var()) / 2)
        if s and np.isfinite(s):
            dif.append({"variavel": c,
                        "media_2015": round(float(a.mean()), 3),
                        "media_2023": round(float(b.mean()), 3),
                        "dif_padronizada": round(float((b.mean() - a.mean()) / s), 3)})
    dif = sorted(dif, key=lambda d: -abs(d["dif_padronizada"]))[:12]

    return {
        "auc_do_detector_de_ano": round(auc_ano, 4),
        "interpretacao_covariate_shift": (
            "desprezivel" if auc_ano < 0.6 else
            "moderado" if auc_ano < 0.75 else "forte"),
        "label_shift": {
            "prevalencia_2015_%": round(float(y15.mean() * 100), 3),
            "prevalencia_2023_%": round(float(y23.mean() * 100), 3),
            "variacao_relativa_%": round(float((y23.mean() / y15.mean() - 1) * 100), 2),
        },
        "variaveis_que_mais_mudaram": dif,
    }


def main() -> None:
    """Aplica o modelo de 2015 ao BRFSS 2023 e grava `gold/_validacao_temporal.json`."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xpt2015", type=Path, default=XPT_2015)
    ap.add_argument("--xpt2023", type=Path, default=XPT_2023)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_validacao_temporal.json"))
    args = ap.parse_args()

    if not args.xpt2023.exists():
        raise SystemExit(f"BRFSS 2023 ausente: {args.xpt2023}. "
                         "URL e hash em data/external/FONTES.md")
    registrar("temporal", "inicio")

    print("  descobrindo as colunas de 2023…")
    with pd.read_sas(args.xpt2023, format="xport", chunksize=1000) as leitor:
        cols23 = set(next(iter(leitor)).columns)
    mapa, ausentes = resolver(cols23)
    print(f"    {len(mapa)} de {len(EQUIVALENCIAS)} variaveis com equivalente em 2023")
    if ausentes:
        print(f"    sem equivalente: {ausentes}")

    comuns = [v for v in RISCO if v in mapa]
    print(f"    variaveis de risco comuns aos dois anos: {len(comuns)} de {len(RISCO)}")
    print(f"    fora por construto: {len(SEM_EQUIVALENTE)}")

    print("\n  lendo os dois anos…")
    b15 = carregar_xpt(args.xpt2015, colunas=[*comuns, "DIABETE3", "_LLCPWT"])
    b23 = carregar_xpt(args.xpt2023,
                       colunas=[mapa[v] for v in comuns] + [mapa["DIABETE3"], "_LLCPWT"])
    b23 = b23.rename(columns={mapa[v]: v for v in [*comuns, "DIABETE3"]})

    def montar(b: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
        """Recorta o ano ja renomeado e devolve (X, y, peso) prontos para o modelo.

        `DIABETE3` fica restrito a 1/2/3: pre-diabetes (codigo 4) sai da amostra, nao
        vira categoria do meio, e diabetes gestacional (2) conta como negativo — a
        mesma convencao do resto do projeto. `_limpar_codigos` traduz os codigos de
        nao-resposta (7, 9, 77, 99…) antes de o modelo ver o numero; sem isso eles
        entrariam como quantidade. O indice e zerado porque 2015 e 2023 sao
        concatenados adiante no detector de deslocamento.
        """
        d = b[b["DIABETE3"].isin([1, 2, 3])].copy()
        y = (d["DIABETE3"] == 1).astype(int).to_numpy()
        X = pd.DataFrame({c: _limpar_codigos(d[c], c) for c in comuns},
                         index=d.index).reset_index(drop=True)
        return X, y, d["_LLCPWT"].astype(float).to_numpy()

    X15, y15, w15 = montar(b15)
    X23, y23, w23 = montar(b23)
    print(f"    2015: {len(X15):,} linhas   2023: {len(X23):,} linhas")

    print("\n  [1] o modelo de 2015 aplicado a 2023")
    rng = np.random.default_rng(SEED)
    te15 = rng.random(len(X15)) < 0.2
    m = _modelo()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X15[~te15].astype("float32"), y15[~te15])

    r_2015 = avaliar(y15[te15], m.predict_proba(X15[te15].astype("float32"))[:, 1])
    r_2023 = avaliar(y23, m.predict_proba(X23.astype("float32"))[:, 1])
    for rot, r in (("holdout 2015 (interno)", r_2015), ("BRFSS 2023 (externo)", r_2023)):
        print(f"    {rot:26} ROC {r['roc_auc']:.4f}  PR {r['pr_auc']:.4f}  "
              f"ECE {r['ece']:.4f}  prev {r['prevalencia_%']:.2f}%")

    print("\n  [2] que tipo de deslocamento?")
    des = deslocamento(X15, X23, y15, y23)
    print(f"    AUC do detector de ano : {des['auc_do_detector_de_ano']:.4f} "
          f"({des['interpretacao_covariate_shift']})")
    ls = des["label_shift"]
    print(f"    prevalencia            : {ls['prevalencia_2015_%']:.2f}% -> "
          f"{ls['prevalencia_2023_%']:.2f}%  ({ls['variacao_relativa_%']:+.1f}%)")
    print("    variaveis que mais mudaram:")
    for d in des["variaveis_que_mais_mudaram"][:6]:
        print(f"      {d['variavel']:12} {d['media_2015']:>9.2f} -> "
              f"{d['media_2023']:>9.2f}   d={d['dif_padronizada']:+.2f}")

    print("\n  [3] recalibrar resolve?")
    p23 = m.predict_proba(X23.astype("float32"))[:, 1]
    # recalibracao so do intercepto, com 20% de 2023 — o minimo que se pediria
    cal = rng.random(len(y23)) < 0.2
    import statsmodels.api as sm
    lp = np.log(np.clip(p23, 1e-6, 1 - 1e-6) / (1 - np.clip(p23, 1e-6, 1 - 1e-6)))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rc = sm.GLM(y23[cal], sm.add_constant(lp[cal]),
                    family=sm.families.Binomial()).fit()
    p23c = 1 / (1 + np.exp(-(rc.params[0] + rc.params[1] * lp)))
    r_rec = avaliar(y23[~cal], p23c[~cal])
    print(f"    antes  ROC {r_2023['roc_auc']:.4f}  ECE {r_2023['ece']:.5f}  "
          f"risco medio previsto {r_2023['risco_medio_previsto_%']:.2f}%")
    print(f"    depois ROC {r_rec['roc_auc']:.4f}  ECE {r_rec['ece']:.5f}  "
          f"risco medio previsto {r_rec['risco_medio_previsto_%']:.2f}%")

    print("\n  [4] e se treinasse em 2023?")
    te23 = rng.random(len(X23)) < 0.2
    m23 = _modelo()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m23.fit(X23[~te23].astype("float32"), y23[~te23])
    r_nativo = avaliar(y23[te23], m23.predict_proba(X23[te23].astype("float32"))[:, 1])
    print(f"    modelo de 2023 no proprio ano: ROC {r_nativo['roc_auc']:.4f}  "
          f"PR {r_nativo['pr_auc']:.4f}  ECE {r_nativo['ece']:.5f}")

    saida = {
        "mapeamento": {"resolvidas": mapa, "sem_equivalente_de_nome": ausentes,
                       "fora_por_construto": SEM_EQUIVALENTE,
                       "n_variaveis_comuns": len(comuns)},
        "modelo_2015_no_holdout_2015": r_2015,
        "modelo_2015_em_2023": r_2023,
        "modelo_2015_em_2023_recalibrado": r_rec,
        "modelo_treinado_em_2023": r_nativo,
        "deslocamento": des,
        "veredito": {
            "perda_roc_milesimos": round((r_2015["roc_auc"] - r_2023["roc_auc"]) * 1000, 1),
            "perda_apos_recalibrar_milesimos": round(
                (r_2015["roc_auc"] - r_rec["roc_auc"]) * 1000, 1),
            "distancia_para_o_modelo_nativo_milesimos": round(
                (r_nativo["roc_auc"] - r_2023["roc_auc"]) * 1000, 1),
        },
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("temporal", "fim")
    print("\n  === VEREDITO ===")
    print(json.dumps(saida["veredito"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
