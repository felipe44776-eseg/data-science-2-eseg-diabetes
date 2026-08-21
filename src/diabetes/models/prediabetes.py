"""Pre-diabetes como problema proprio: um classificador de trajetoria diagnostica.

Por que esta frente existe
--------------------------
`docs/07` §3 mostrou que pre-diabetes **nao e ponto intermediario** do mesmo
continuum: nove variaveis divergem entre as duas classes e duas invertem de
direcao. `docs/12` mostrou que a classe so existe para quem foi testado.

Decidimos entao **excluir** a classe 1 da modelagem preditiva (`docs/08`). Isso
resolveu o problema errado: excluir e admitir que nao sabemos o que ela e, nao
descobrir.

A hipotese a testar
-------------------
Se `pre_diabetes = 1` for majoritariamente **artefato de deteccao**, entao:

  H1. variaveis de ACESSO devem predizer a classe 1 melhor que variaveis de RISCO;
  H2. o contraste informativo nao e "quem tem pre-diabetes" — e **quem, entre os
      testados, recebeu o rotulo**;
  H3. condicionado a ter sido testado, o perfil de risco de quem recebe o rotulo
      de pre-diabetes deve ficar entre o de "sem diabetes" e o de "diabetes";
  H4. quem tem risco fisiologico alto e NAO foi testado nao aparece na classe 1 —
      ele fica na classe 0, indistinguivel de quem e saudavel.

Tres modelos, cada um respondendo uma pergunta diferente
--------------------------------------------------------
  A. **{1} vs {0}**  entre TODOS  — o que o dado bruto oferece
  B. **{1} vs {0}**  entre os TESTADOS — remove a etapa de deteccao do contraste
  C. **{1} vs {2}**  entre os TESTADOS — dado que foi diagnosticado, o que separa
     pre de diabetes estabelecido?

A diferenca entre A e B mede quanto da "predicao de pre-diabetes" e, na verdade,
predicao de quem faz exame.

Uso:
    python -m diabetes.models.prediabetes
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
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, roc_auc_score

from diabetes.external.brfss2015 import carregar_xpt
from diabetes.features.expandido import (
    ACESSO_E_DETECCAO,
    ALVO,
    DESENHO,
    ORIGINAIS,
    RISCO,
    TODAS,
    VAZAMENTO,
    _limpar_codigos,
)
from diabetes.pipeline.estado import registrar

XPT = Path("data/external/brfss2015/LLCP2015.XPT")
SEED = 42

#: proxy de "foi testado": fez exame de colesterol nos ultimos 5 anos.
#: E o melhor marcador disponivel de contato recente com o sistema de saude —
#: quem faz esse exame e quem faz glicemia na mesma coleta.
def testado(bruto: pd.DataFrame) -> pd.Series:
    """Proxy de "foi testado": fez exame de colesterol nos ultimos 5 anos.

    Nao ha no BRFSS pergunta direta sobre teste de glicemia utilizavel — `PDIABTST`
    esta em `VAZAMENTO`, porque decorre da propria suspeita de diabetes. `CHOLCHK`
    e o melhor marcador disponivel de contato recente com o sistema de saude: a
    glicemia costuma sair na mesma coleta. Toda a leitura de H2 e H4 depende desta
    suposicao — se ela cair, cai o modulo.
    """
    return (bruto["CHOLCHK"] == 1)


def _modelo():
    return CalibratedClassifierCV(
        HistGradientBoostingClassifier(
            max_iter=350, learning_rate=0.06, max_leaf_nodes=31,
            min_samples_leaf=40, l2_regularization=1.0, early_stopping=True,
            validation_fraction=0.12, random_state=SEED),
        method="isotonic", cv=3)


def rodar(X: pd.DataFrame, y: np.ndarray, te: np.ndarray, rotulo: str) -> dict:
    """Ajusta um contraste e devolve (metricas, modelo ajustado, predicao no teste).

    `pr_auc_ganho` normaliza pela prevalencia do proprio teste: os contrastes deste
    modulo (pre vs sem, diabetes vs sem, pre vs diabetes, so testados) tem
    prevalencias muito diferentes, e a PR-AUC crua nao e comparavel entre eles — o
    que se compara e quantas vezes cada modelo bate o classificador constante.

    A anotacao de retorno cobre so o primeiro elemento; sai uma tupla.
    """
    m = _modelo()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X[~te], y[~te])
    p = m.predict_proba(X[te])[:, 1]
    r = {
        "rotulo": rotulo,
        "n_treino": int((~te).sum()), "n_teste": int(te.sum()),
        "prevalencia_%": round(float(y.mean() * 100), 3),
        "roc_auc": round(float(roc_auc_score(y[te], p)), 4),
        "pr_auc": round(float(average_precision_score(y[te], p)), 4),
        "pr_auc_ganho": round(float(average_precision_score(y[te], p)) / y[te].mean(), 2),
        "n_variaveis": X.shape[1],
    }
    print(f"    {rotulo:46} ROC {r['roc_auc']:.4f}  PR {r['pr_auc']:.4f}  "
          f"ganho {r['pr_auc_ganho']:.2f}x  (n={len(y):,}, prev {r['prevalencia_%']:.2f}%)")
    return r, m, p


def importancia(m, X: pd.DataFrame, y: np.ndarray, te: np.ndarray,
                n: int = 8000) -> list[dict]:
    """Importancia por permutacao no teste, com cada variavel rotulada por bloco.

    Permutacao e nao ganho de impureza: o modelo e um `CalibratedClassifierCV`, que
    nao expoe importancia nativa, e a permutacao mede o que a **metrica** perde, nao
    como a arvore foi construida. Subamostra de 8 mil linhas e 3 repeticoes por
    custo — o topo do ranking e estavel, a ordem exata no meio da lista nao e.

    O campo `bloco` e a resposta a H1: o que interessa e quantas das primeiras
    colocadas sao de acesso, e nao de risco.
    """
    rng = np.random.default_rng(SEED)
    idx = np.where(te)[0]
    sub = rng.choice(idx, min(n, len(idx)), replace=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        imp = permutation_importance(m, X.iloc[sub], y[sub], n_repeats=3,
                                     random_state=SEED, scoring="roc_auc", n_jobs=-1)
    s = pd.Series(imp.importances_mean, index=X.columns).sort_values(ascending=False)
    return [{"variavel": k, "importancia": round(float(v), 5),
             "bloco": "acesso" if k in ACESSO_E_DETECCAO else "risco"}
            for k, v in s.head(15).items()]


def main() -> None:
    """Testa H1-H4 sobre pre-diabetes como artefato de deteccao; grava `gold/_prediabetes.json`."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xpt", type=Path, default=XPT)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_prediabetes.json"))
    args = ap.parse_args()

    registrar("prediabetes", "inicio")
    print("  lendo o BRFSS com as tres classes…")
    necessarias = set(TODAS) | set(ORIGINAIS) | set(DESENHO) | {ALVO}
    bruto = carregar_xpt(args.xpt, colunas=sorted(necessarias))
    for c in bruto.columns:
        if VAZAMENTO.match(c) and c != ALVO:
            raise AssertionError(f"vazamento: {c}")

    # 1 sim · 2 gestacional · 3 nao · 4 pre-diabetes
    d = bruto[bruto[ALVO].isin([1, 2, 3, 4])].copy()
    classe = d[ALVO].map({1: 2, 2: 0, 3: 0, 4: 1})       # 0 sem · 1 pre · 2 diabetes
    X = pd.DataFrame({c: _limpar_codigos(d[c], c) for c in TODAS}, index=d.index)
    tst = testado(d)

    rng = np.random.default_rng(SEED)
    te_all = rng.random(len(d)) < 0.25

    print(f"    n={len(d):,}   sem {(classe==0).sum():,}  "
          f"pre {(classe==1).sum():,}  diabetes {(classe==2).sum():,}")
    print(f"    testados (exame de colesterol <=5 anos): {tst.mean()*100:.1f}%")

    saida = {"n": int(len(d)),
             "distribuicao": {int(k): int(v) for k, v in classe.value_counts().items()},
             "pct_testado": round(float(tst.mean() * 100), 2)}

    # --- H1: acesso prediz melhor que risco? ------------------------------
    print("\n  [H1] acesso prediz pre-diabetes melhor que risco?")
    sel = classe.isin([0, 1]).to_numpy()
    y01 = (classe[sel] == 1).to_numpy().astype(int)
    te01 = te_all[sel]
    blocos = {"risco (60 vars)": RISCO, "acesso (9 vars)": list(ACESSO_E_DETECCAO),
              "ambos (69 vars)": TODAS}
    r_h1 = {}
    for nome, cols in blocos.items():
        r, _, _ = rodar(X.loc[sel, cols].astype("float32"), y01, te01,
                        f"pre vs sem — {nome}")
        r_h1[nome] = r
    saida["H1_blocos"] = r_h1

    # comparacao com o mesmo teste para DIABETES, que e o controle
    print("\n       (controle: o mesmo, para diabetes estabelecido)")
    sel2 = classe.isin([0, 2]).to_numpy()
    y02 = (classe[sel2] == 2).to_numpy().astype(int)
    te02 = te_all[sel2]
    r_ctrl = {}
    for nome, cols in blocos.items():
        r, _, _ = rodar(X.loc[sel2, cols].astype("float32"), y02, te02,
                        f"diabetes vs sem — {nome}")
        r_ctrl[nome] = r
    saida["H1_controle_diabetes"] = r_ctrl

    # --- H2: condicionar em ter sido testado -------------------------------
    print("\n  [H2] e se o contraste for so entre os TESTADOS?")
    selT = (classe.isin([0, 1]) & tst).to_numpy()
    yT = (classe[selT] == 1).to_numpy().astype(int)
    r_test, m_test, _ = rodar(X.loc[selT, RISCO].astype("float32"), yT,
                              te_all[selT], "pre vs sem, so testados — risco")
    saida["H2_so_testados"] = r_test

    # --- H3/C: dado que foi diagnosticado, pre ou diabetes? ----------------
    print("\n  [C] entre os diagnosticados: pre-diabetes ou diabetes?")
    selD = classe.isin([1, 2]).to_numpy()
    yD = (classe[selD] == 2).to_numpy().astype(int)
    r_d, m_d, _ = rodar(X.loc[selD, RISCO].astype("float32"), yD,
                        te_all[selD], "diabetes vs pre — risco")
    saida["C_pre_vs_diabetes"] = r_d

    # --- o que importa em cada contraste -----------------------------------
    print("\n  importancia por permutacao — 'pre vs sem' com TODAS as variaveis")
    r_todas, m_todas, _ = rodar(X.loc[sel, TODAS].astype("float32"), y01, te01,
                                "pre vs sem — todas (para importancia)")
    imp = importancia(m_todas, X.loc[sel, TODAS].astype("float32"), y01, te01)
    saida["importancia_pre_vs_sem"] = imp
    for i in imp[:10]:
        print(f"    {i['bloco']:7} {i['variavel']:14} {i['importancia']:.5f}")

    n_acesso = sum(1 for i in imp[:10] if i["bloco"] == "acesso")
    saida["acesso_no_top10"] = n_acesso

    # --- H4: quem tem risco alto e nao foi testado --------------------------
    print("\n  [H4] onde estao os de risco alto que NAO foram testados?")
    r_risco_geral, m_rg, _ = rodar(X[RISCO].astype("float32"),
                                   (classe == 2).to_numpy().astype(int), te_all,
                                   "risco fisiologico (diabetes vs resto)")
    p_risco = m_rg.predict_proba(X[RISCO].astype("float32"))[:, 1]
    alto = p_risco >= np.quantile(p_risco, 0.90)
    tab = []
    for rot, m in (("testado", tst.to_numpy()), ("nao testado", ~tst.to_numpy())):
        mm = alto & m
        tab.append({
            "grupo": f"risco alto · {rot}", "n": int(mm.sum()),
            "%_sem_diabetes": round(float((classe[mm] == 0).mean() * 100), 2),
            "%_pre_diabetes": round(float((classe[mm] == 1).mean() * 100), 2),
            "%_diabetes": round(float((classe[mm] == 2).mean() * 100), 2),
        })
    saida["H4_risco_alto"] = tab
    print(pd.DataFrame(tab).to_string(index=False))

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("prediabetes", "fim")


if __name__ == "__main__":
    main()
