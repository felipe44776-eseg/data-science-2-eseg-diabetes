"""Frente 3 — EBM interpretavel e predicao conforme.

Duas peças que resolvem problemas diferentes do mesmo entregavel clinico.

**EBM (Explainable Boosting Machine, Nori et al.)** — modelo aditivo generalizado
com interacoes de pares, ajustado por boosting ciclico. Acuracia de arvore com
interpretabilidade de modelo aditivo:

    logit P(y) = intercepto + Σ f_j(x_j) + Σ f_jk(x_j, x_k)

Cada `f_j` e uma **funcao de forma** que se pode desenhar e auditar. Nao e
aproximacao post hoc como SHAP: e o proprio modelo. Para um escore clinico isso
importa mais que o terceiro decimal do AUC.

Motivo especifico aqui: `docs/06` mostrou que a idade **cai em 80+** (mortalidade
seletiva) e que o IMC tem **curva em J**. Termo linear nao representa nenhuma das
duas; o EBM mostra as duas em grafico, para um medico conferir.

**Restricoes de monotonicidade** — o gradient boosting aceita direcao imposta.
Impomos onde a direcao e conhecida a priori (IMC, hipertensao, colesterol) e
**deliberadamente nao impomos na idade**, porque sabemos que ela nao e monotonica.

**Predicao conforme (Vovk; Angelopoulos & Bates)** — em vez de uma probabilidade
pontual, conjuntos com **cobertura garantida** sem suposicao distribucional.
Para rastreamento, "este limiar garante >= 70% de sensibilidade com 95% de
confianca" e mais acionavel e mais honesto que "probabilidade 0,31".

Usamos duas variantes:
  * **Mondrian** (condicional por classe) — cobertura garantida em CADA classe,
    o que importa sob desbalanceamento de 87/13;
  * **Controle de risco conforme** — escolhe o limiar que garante um recall-alvo.

Uso:
    python -m diabetes.models.glassbox
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from diabetes.features.expandido import RISCO
from diabetes.models.escada import erro_calibracao, recall_em_especificidade
from diabetes.models.expandido import particionar
from diabetes.pipeline.estado import registrar

SEED = 42
ENTRADA = Path("data/processed/gold/brfss_expandido.parquet")

#: direcao conhecida a priori. +1 = risco cresce com a variavel.
#: `_AGE80` fica FORA de proposito: `docs/06` §3.1 mostrou queda em 80+.
MONOTONICAS = {
    "_BMI5": +1,        # IMC maior, mais risco — monotonico no intervalo util
    "_RFHYPE5": +1,     # 1 = nao, 2 = sim
    "TOLDHI2": -1,      # 1 = sim, 2 = nao  -> risco cai com o codigo
    "GENHLTH": +1,      # 1 excelente .. 5 ruim
    "CHCKIDNY": -1,     # 1 = sim, 2 = nao
}

#: subconjunto para o EBM: o modelo aditivo fica ilegivel com 60 termos.
#: Escolhidas por `docs/08` §4 (curva de parcimonia) + `docs/10` (ablacao).
EBM_VARS = ["GENHLTH", "_BMI5", "_RFHYPE5", "TOLDHI2", "_AGE80",
            "CHCKIDNY", "_RACEGR3", "INCOME2", "SEX", "HAVARTH3",
            "ADDEPEV2", "DIFFWALK"]


def _limiar_para_recall(y: np.ndarray, p: np.ndarray, alvo: float) -> float:
    return float(np.quantile(p[y == 1], 1 - alvo))


# --------------------------------------------------------------------------
# EBM
# --------------------------------------------------------------------------

def ajustar_ebm(df: pd.DataFrame, te: np.ndarray) -> dict:
    from interpret.glassbox import ExplainableBoostingClassifier

    y = df["diabetes"].to_numpy()
    X = df[EBM_VARS].astype("float32")
    m = ExplainableBoostingClassifier(
        feature_names=EBM_VARS, interactions=8, max_bins=64,
        outer_bags=8, random_state=SEED, n_jobs=-1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X[~te], y[~te])
    p = m.predict_proba(X[te])[:, 1]

    glob = m.explain_global()
    dados = glob.data()
    importancia = sorted(
        zip(dados["names"], dados["scores"], strict=True),
        key=lambda kv: -kv[1])

    # funcoes de forma das duas variaveis cuja nao-linearidade motivou o EBM
    formas = {}
    for var in ("_AGE80", "_BMI5"):
        if var not in m.term_names_:
            continue
        i = m.term_names_.index(var)
        d = glob.data(i)
        x = d["names"]
        centros = [(x[k] + x[k + 1]) / 2 for k in range(len(x) - 1)] \
            if len(x) == len(d["scores"]) + 1 else list(x)
        formas[var] = [{"x": round(float(a), 2), "contribuicao_logit": round(float(b), 4)}
                       for a, b in zip(centros, d["scores"], strict=False)]
    return {
        "p": p,
        "importancia": [{"termo": str(n), "importancia": round(float(v), 5)}
                        for n, v in importancia[:20]],
        "formas": formas,
        "n_termos": len(m.term_names_),
    }


# --------------------------------------------------------------------------
# monotonicidade
# --------------------------------------------------------------------------

def ajustar_monotonico(df: pd.DataFrame, te: np.ndarray, impor: bool) -> np.ndarray:
    y = df["diabetes"].to_numpy()
    X = df[RISCO].astype("float32").to_numpy()
    restr = [MONOTONICAS.get(c, 0) for c in RISCO] if impor else None
    m = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=50,
        l2_regularization=1.0, early_stopping=True, validation_fraction=0.12,
        monotonic_cst=restr, random_state=SEED)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X[~te], y[~te])
    return m.predict_proba(X[te])[:, 1]


# --------------------------------------------------------------------------
# predicao conforme
# --------------------------------------------------------------------------

def conforme_mondrian(p_cal: np.ndarray, y_cal: np.ndarray, p_te: np.ndarray,
                      alfa: float = 0.10) -> dict:
    """Conjuntos de predicao com cobertura >= 1-alfa **em cada classe**.

    Escore de nao-conformidade: 1 - p(classe verdadeira). O quantil e calculado
    **por classe** (Mondrian), o que garante cobertura condicional — sob 87/13,
    o conforme marginal entregaria cobertura quase perfeita na classe majoritaria
    e ruim na minoritaria, exatamente onde ela importa.
    """
    q = {}
    for cls in (0, 1):
        m = y_cal == cls
        escore = 1 - np.where(cls == 1, p_cal[m], 1 - p_cal[m])
        n = m.sum()
        nivel = min(np.ceil((n + 1) * (1 - alfa)) / n, 1.0)
        q[cls] = float(np.quantile(escore, nivel, method="higher"))

    inclui0 = (1 - (1 - p_te)) <= q[0]
    inclui1 = (1 - p_te) <= q[1]
    tam = inclui0.astype(int) + inclui1.astype(int)
    return {"quantil_classe0": q[0], "quantil_classe1": q[1],
            "inclui0": inclui0, "inclui1": inclui1, "tamanho": tam}


def avaliar_conforme(cj: dict, y_te: np.ndarray, alfa: float) -> dict:
    cob = {}
    for cls, inc in ((0, cj["inclui0"]), (1, cj["inclui1"])):
        m = y_te == cls
        cob[f"cobertura_classe{cls}"] = round(float(inc[m].mean()), 4)
    tam = cj["tamanho"]
    return {
        "alvo_cobertura": 1 - alfa,
        **cob,
        "%_conjunto_vazio": round(float((tam == 0).mean() * 100), 2),
        "%_conjunto_unitario": round(float((tam == 1).mean() * 100), 2),
        "%_conjunto_ambiguo": round(float((tam == 2).mean() * 100), 2),
        "%_singleton_diabetes": round(float(
            ((tam == 1) & cj["inclui1"]).mean() * 100), 2),
    }


def controle_de_risco(p_cal: np.ndarray, y_cal: np.ndarray, p_te: np.ndarray,
                      y_te: np.ndarray, recalls: tuple = (0.70, 0.80, 0.90)) -> list[dict]:
    """Limiar que garante o recall-alvo, calibrado fora da amostra de teste.

    E a pergunta operacional de rastreamento: "quero achar 80% dos casos —
    quantas pessoas preciso testar?"
    """
    out = []
    for alvo in recalls:
        lim = _limiar_para_recall(y_cal, p_cal, alvo)
        sel = p_te >= lim
        rec = float(y_te[sel].sum() / y_te.sum())
        out.append({
            "recall_alvo": alvo,
            "limiar": round(lim, 5),
            "recall_obtido": round(rec, 4),
            "%_populacao_testada": round(float(sel.mean() * 100), 2),
            "precisao": round(float(y_te[sel].mean()), 4),
            "nns": round(float(1 / y_te[sel].mean()), 1),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, default=ENTRADA)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_frente3_glassbox.json"))
    args = ap.parse_args()

    df = pd.read_parquet(args.entrada)
    te = particionar(df)
    y = df["diabetes"].to_numpy()
    y_te = y[te]
    registrar("frente3", "inicio", n=len(df))

    print("  [1] monotonicidade — custa performance?")
    p_livre = ajustar_monotonico(df, te, impor=False)
    p_mono = ajustar_monotonico(df, te, impor=True)
    comp_mono = {}
    for rot, p in (("sem restricao", p_livre), ("com restricao", p_mono)):
        comp_mono[rot] = {
            "roc_auc": round(float(roc_auc_score(y_te, p)), 4),
            "pr_auc": round(float(average_precision_score(y_te, p)), 4),
            "recall_esp90": round(recall_em_especificidade(y_te, p, 0.90), 4),
        }
        print(f"    {rot:16} ROC-AUC {comp_mono[rot]['roc_auc']:.4f}  "
              f"PR-AUC {comp_mono[rot]['pr_auc']:.4f}")
    comp_mono["custo_pr_auc_%"] = round(
        (1 - comp_mono["com restricao"]["pr_auc"] / comp_mono["sem restricao"]["pr_auc"]) * 100, 2)
    print(f"    custo da restricao: {comp_mono['custo_pr_auc_%']}% de PR-AUC")

    print("\n  [2] EBM (glassbox)…")
    ebm = ajustar_ebm(df, te)
    m_ebm = {
        "roc_auc": round(float(roc_auc_score(y_te, ebm["p"])), 4),
        "pr_auc": round(float(average_precision_score(y_te, ebm["p"])), 4),
        "recall_esp90": round(recall_em_especificidade(y_te, ebm["p"], 0.90), 4),
        "ece": round(erro_calibracao(y_te, ebm["p"]), 5),
        "n_variaveis": len(EBM_VARS),
        "n_termos": ebm["n_termos"],
    }
    print(f"    {len(EBM_VARS)} variaveis, {ebm['n_termos']} termos  "
          f"ROC-AUC {m_ebm['roc_auc']:.4f}  PR-AUC {m_ebm['pr_auc']:.4f}  "
          f"ECE {m_ebm['ece']:.5f}")
    print("    top 8 termos:", ", ".join(
        t["termo"] for t in ebm["importancia"][:8]))

    print("\n  [3] predicao conforme (Mondrian, por classe)…")
    # metade do holdout calibra o conforme, metade avalia — o conforme precisa
    # de um conjunto que o modelo nao viu E que nao foi usado para o quantil
    idx = np.where(te)[0]
    rng = np.random.default_rng(SEED)
    emb = rng.permutation(len(idx))
    cal_i, av_i = idx[emb[: len(idx) // 2]], idx[emb[len(idx) // 2:]]
    p_full = np.zeros(len(df))
    p_full[te] = p_livre
    conf = {}
    for alfa in (0.05, 0.10, 0.20):
        cj = conforme_mondrian(p_full[cal_i], y[cal_i], p_full[av_i], alfa)
        conf[f"alfa_{alfa}"] = avaliar_conforme(cj, y[av_i], alfa)
        c = conf[f"alfa_{alfa}"]
        print(f"    alfa={alfa:.2f}  cobertura classe0 {c['cobertura_classe0']:.4f}  "
              f"classe1 {c['cobertura_classe1']:.4f}  "
              f"ambiguos {c['%_conjunto_ambiguo']:.1f}%")

    print("\n  [4] controle de risco conforme — quantos testar para achar X%?")
    risco = controle_de_risco(p_full[cal_i], y[cal_i], p_full[av_i], y[av_i])
    print(pd.DataFrame(risco).to_string(index=False))

    saida = {
        "monotonicidade": {"restricoes": MONOTONICAS, **comp_mono},
        "ebm": {"variaveis": EBM_VARS, "metricas": m_ebm,
                "importancia": ebm["importancia"], "formas": ebm["formas"]},
        "conforme": conf,
        "controle_de_risco": risco,
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("frente3", "fim")


if __name__ == "__main__":
    main()
