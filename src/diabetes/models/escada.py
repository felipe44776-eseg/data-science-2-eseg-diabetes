"""Trilha B — escada de modelos preditivos.

Protocolo fixado **antes** de qualquer modelo (`docs/02` B1):

  particao : StratifiedGroupKFold(5) sobre `data/processed/gold/folds.parquet`,
             grupo = hash das 21 features -> nenhuma duplicata cruza treino/teste
  holdout  : 20% separado por grupo, tocado UMA vez, no fim
  metrica  : PR-AUC (principal) · recall @ especificidade 90% · Brier ·
             calibracao. **Acuracia nao e reportada** (ADR 0005)
  baseline : prevalencia constante e regra clinica de 3 variaveis -- se o
             gradient boosting nao bater a regra clinica, nao ha projeto

Dois blocos de variaveis, e a diferenca entre eles e um resultado:

  SEM_ACESSO  exclui `exame_colesterol`, `acesso_saude`, `sem_consulta_por_custo`
              -> mede risco
  COM_ACESSO  todas as 21
              -> mede risco + trajetoria diagnostica. Melhor metrica, pior validade
                 (`docs/07` §2.3: exame_colesterol tem OR 3,45 ajustado)

Alvo: **diabetes (classe 2) vs sem diabetes (classe 0)**. A classe 1 e excluida,
nao ignorada -- `docs/07` §3 mostrou que pre-diabetes tem mecanismo proprio e
nao e ponto intermediario do mesmo continuum.

Uso:
    python -m diabetes.models.escada
"""

from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

from diabetes.pipeline.estado import registrar
from diabetes.schema import ESQUEMA, PROXIES_DE_ACESSO, TARGET

TODAS = [c for c in ESQUEMA if c != TARGET]
SEM_ACESSO = [c for c in TODAS if c not in PROXIES_DE_ACESSO]
REGRA_CLINICA = ["idade_faixa", "imc", "hipertensao"]

SEED = 42


# --------------------------------------------------------------------------
# metricas
# --------------------------------------------------------------------------

def recall_em_especificidade(y: np.ndarray, p: np.ndarray, esp: float = 0.90) -> float:
    """Sensibilidade no limiar que entrega a especificidade pedida.

    Leitura operacional de rastreamento: aceitando 10% de falso-positivo entre
    os saudaveis, que fracao dos casos eu capturo?
    """
    limiar = np.quantile(p[y == 0], esp)
    return float((p[y == 1] >= limiar).mean())


def erro_calibracao(y: np.ndarray, p: np.ndarray, faixas: int = 10) -> float:
    """ECE — erro de calibracao esperado, por decil de risco previsto."""
    bordas = np.quantile(p, np.linspace(0, 1, faixas + 1))
    bordas[-1] += 1e-9
    total = 0.0
    for i in range(faixas):
        m = (p >= bordas[i]) & (p < bordas[i + 1])
        if m.sum():
            total += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(total)


def curva_calibracao(y: np.ndarray, p: np.ndarray, faixas: int = 10) -> list[dict]:
    """Risco previsto contra observado, por decil de risco — o insumo do grafico.

    Complementa o ECE, que resume tudo num numero e apaga a direcao do erro: aqui se
    ve se o modelo e otimista na cauda alta ou pessimista no meio, que e o que
    importa para escolher limiar. Decil vazio e omitido, entao a lista pode vir com
    menos de `faixas` entradas.
    """
    bordas = np.quantile(p, np.linspace(0, 1, faixas + 1))
    bordas[-1] += 1e-9
    out = []
    for i in range(faixas):
        m = (p >= bordas[i]) & (p < bordas[i + 1])
        if m.sum():
            out.append({"previsto": round(float(p[m].mean()), 4),
                        "observado": round(float(y[m].mean()), 4),
                        "n": int(m.sum())})
    return out


def avaliar(y: np.ndarray, p: np.ndarray) -> dict:
    """Painel de metricas do protocolo. Acuracia nao entra, por decisao (ADR 0005).

    `pr_auc_ganho` e a PR-AUC dividida pela prevalencia: a PR-AUC bruta nao e
    comparavel entre amostras de prevalencia diferente, e o que se le e o ganho
    sobre o classificador constante. `recall_esp90` e `esp95` traduzem a curva em
    operacao de rastreamento. `brier` e `ece` medem calibracao — dimensao que
    PR-AUC e ROC-AUC ignoram por completo, e que e a que a Trilha C consome.
    """
    prev = float(y.mean())
    return {
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "pr_auc_ganho": round(float(average_precision_score(y, p)) / prev, 2),
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
        "recall_esp90": round(recall_em_especificidade(y, p, 0.90), 4),
        "recall_esp95": round(recall_em_especificidade(y, p, 0.95), 4),
        "brier": round(float(brier_score_loss(y, p)), 5),
        "log_loss": round(float(log_loss(y, p, labels=[0, 1])), 5),
        "ece": round(erro_calibracao(y, p), 5),
        "prevalencia": round(prev, 4),
    }


# --------------------------------------------------------------------------
# teto de Bayes empirico
# --------------------------------------------------------------------------

def teto_de_bayes(df: pd.DataFrame, variaveis: list[str]) -> dict:
    """Limite superior de acerto imposto pelo ruido de rotulo.

    Perfis identicos nas features com alvo divergente sao erro irredutivel:
    nenhum modelo, por melhor que seja, separa duas linhas identicas. O melhor
    que se pode fazer e responder a classe majoritaria do grupo.
    """
    g = df.groupby(variaveis, sort=False)[TARGET]
    tam = g.transform("size")
    maioria = g.transform(lambda s: s.value_counts().iloc[0])
    acerto_max = float((maioria / tam).groupby(
        df.groupby(variaveis, sort=False).ngroup()).first().mean())
    conflitantes = df.loc[g.transform("nunique") > 1]
    return {
        "grupos": int(df.groupby(variaveis, sort=False).ngroup().nunique()),
        "linhas_em_grupo_conflitante": int(len(conflitantes)),
        "acerto_maximo_por_grupo": round(acerto_max, 4),
        "acerto_maximo_ponderado": round(float((maioria / tam).mean()), 4),
    }


# --------------------------------------------------------------------------
# modelos
# --------------------------------------------------------------------------

def construir(nome: str, n_vars: int):
    """Cada degrau da escada. `class_weight`/pesos = custo, nunca reamostragem (ADR 0004)."""
    if nome == "0_prevalencia":
        return DummyClassifier(strategy="prior")
    if nome == "1_regra_clinica":
        return Pipeline([("z", StandardScaler()),
                         ("lr", LogisticRegression(max_iter=1000, random_state=SEED))])
    if nome == "2_logistica_l2":
        return Pipeline([("z", StandardScaler()),
                         ("lr", LogisticRegression(max_iter=2000, C=1.0,
                                                   class_weight="balanced",
                                                   random_state=SEED))])
    if nome == "3_spline":
        # spline em todas as colunas: captura a inflexao etaria em 80+ e a
        # curva em J do IMC, que o termo linear nao consegue (`docs/06` §3.1)
        return Pipeline([
            ("sp", SplineTransformer(n_knots=5, degree=3, include_bias=False)),
            ("lr", LogisticRegression(max_iter=3000, C=0.5,
                                      class_weight="balanced", random_state=SEED)),
        ])
    if nome == "4_gradient_boosting":
        return HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
            min_samples_leaf=50, l2_regularization=1.0,
            class_weight="balanced", early_stopping=True,
            validation_fraction=0.12, random_state=SEED)
    if nome == "5_gb_calibrado":
        base = HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
            min_samples_leaf=50, l2_regularization=1.0,
            early_stopping=True, validation_fraction=0.12, random_state=SEED)
        # calibracao isotonica em fold proprio: probabilidade utilizavel na Trilha C
        return CalibratedClassifierCV(base, method="isotonic", cv=3)
    raise ValueError(nome)


ESCADA = ["0_prevalencia", "1_regra_clinica", "2_logistica_l2", "3_spline",
          "4_gradient_boosting", "5_gb_calibrado"]


def variaveis_de(nome: str, bloco: list[str]) -> list[str]:
    """Degrau 1 usa a regra clinica de 3 variaveis; todo o resto usa o bloco inteiro.

    O baseline clinico precisa ficar identico nos dois blocos (com e sem proxies de
    acesso). Se ele acompanhasse o bloco, a comparacao entre blocos estaria mudando
    duas coisas ao mesmo tempo e a diferenca deixaria de ser atribuivel aos proxies.
    """
    return REGRA_CLINICA if nome == "1_regra_clinica" else bloco


def rodar_bloco(df: pd.DataFrame, folds: pd.DataFrame, bloco: list[str],
                rotulo: str) -> dict:
    """Roda a escada inteira num bloco de variaveis e devolve metricas por degrau.

    Restringe ao alvo binario 0 vs 2: pre-diabetes e **excluido**, nao tratado como
    ponto intermediario, porque tem mecanismo proprio (`docs/07` §3).

    A validacao cruzada usa os folds ja congelados em `folds.parquet`
    (StratifiedGroupKFold por hash das 21 features), entao nenhuma duplicata exata
    cruza treino e validacao — ADR 0002. O vetor `oof` nasce NaN e so e preenchido
    nas linhas de treino: qualquer metrica que tente ler predicao out-of-fold no
    holdout quebra, em vez de misturar as duas particoes em silencio.

    O holdout de 20% e tocado uma unica vez por degrau, no ajuste final; nada —
    hiperparametro, limiar, escolha de variavel — e decidido olhando para ele.
    """
    d = df.loc[df[TARGET].isin([0, 2])].copy()
    f = folds.loc[d.index]
    y = (d[TARGET] == 2).astype(int).to_numpy()

    treino = ~f["holdout"].to_numpy()
    resultados: dict = {}

    for nome in ESCADA:
        variaveis = variaveis_de(nome, bloco)
        X = d[variaveis].astype("float32").to_numpy()
        t0 = time.time()

        # validacao cruzada por grupo (folds ja congelados, sem vazamento)
        oof = np.full(len(d), np.nan)
        for k in sorted(f.loc[treino, "fold"].unique()):
            tr = treino & (f["fold"].to_numpy() != k)
            va = treino & (f["fold"].to_numpy() == k)
            m = construir(nome, len(variaveis))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m.fit(X[tr], y[tr])
            oof[va] = m.predict_proba(X[va])[:, 1]

        # ajuste final em todo o treino, avaliado no holdout intocado
        m = construir(nome, len(variaveis))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m.fit(X[treino], y[treino])
        p_hold = m.predict_proba(X[~treino])[:, 1]

        resultados[nome] = {
            "variaveis": len(variaveis),
            "segundos": round(time.time() - t0, 1),
            "cv_oof": avaliar(y[treino], oof[treino]),
            "holdout": avaliar(y[~treino], p_hold),
            "calibracao_holdout": curva_calibracao(y[~treino], p_hold),
        }
        print(f"    {nome:22} PR-AUC oof {resultados[nome]['cv_oof']['pr_auc']:.4f}  "
              f"holdout {resultados[nome]['holdout']['pr_auc']:.4f}  "
              f"recall@esp90 {resultados[nome]['holdout']['recall_esp90']:.3f}  "
              f"({resultados[nome]['segundos']}s)")

    return {"rotulo": rotulo, "n": int(len(d)), "n_treino": int(treino.sum()),
            "n_holdout": int((~treino).sum()),
            "prevalencia": round(float(y.mean()), 4),
            "modelos": resultados}


def demonstrar_vazamento(df: pd.DataFrame, folds: pd.DataFrame,
                         bloco: list[str]) -> dict:
    """Quanto a metrica sobe com particao aleatoria ingenua, em vez de por grupo.

    Nao e curiosidade: e a diferenca entre medir generalizacao e medir memorizacao
    (`docs/01` §1.1). Reportado para dimensionar o erro que este dataset convida
    a cometer.
    """
    from sklearn.model_selection import train_test_split

    d = df.loc[df[TARGET].isin([0, 2])].copy()
    y = (d[TARGET] == 2).astype(int).to_numpy()
    X = d[bloco].astype("float32").to_numpy()

    idx = np.arange(len(d))
    tr_i, te_i = train_test_split(idx, test_size=0.2, random_state=SEED, stratify=y)
    m = construir("4_gradient_boosting", len(bloco))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X[tr_i], y[tr_i])
    ingenuo = avaliar(y[te_i], m.predict_proba(X[te_i])[:, 1])

    f = folds.loc[d.index]
    treino = ~f["holdout"].to_numpy()
    m = construir("4_gradient_boosting", len(bloco))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X[treino], y[treino])
    grupo = avaliar(y[~treino], m.predict_proba(X[~treino])[:, 1])

    gemeas = int(pd.Series(f["grupo"].to_numpy()[te_i]).isin(
        set(f["grupo"].to_numpy()[tr_i])).sum())
    return {
        "split_aleatorio": ingenuo,
        "split_por_grupo": grupo,
        "linhas_teste_com_gemea_no_treino": gemeas,
        "pct_teste_contaminado": round(gemeas / len(te_i) * 100, 2),
        "inflacao_pr_auc_%": round(
            (ingenuo["pr_auc"] / grupo["pr_auc"] - 1) * 100, 2),
        "inflacao_roc_auc_%": round(
            (ingenuo["roc_auc"] / grupo["roc_auc"] - 1) * 100, 2),
    }


def curva_de_parcimonia(df: pd.DataFrame, folds: pd.DataFrame, bloco: list[str],
                        teto: float, passos: int = 8) -> dict:
    """Selecao gulosa para frente: quanto se perde usando poucas variaveis?

    Responde diretamente a pergunta da Trilha C — se um escore de 5 perguntas
    chega perto do modelo de 21, o entregavel e o escore, porque roda numa
    unidade basica de saude sem computador.

    Avalia com logistica (nao gradient boosting): o candidato a escore precisa
    ser um modelo linear, para virar pontos inteiros no papel.
    """
    d = df.loc[df[TARGET].isin([0, 2])].copy()
    f = folds.loc[d.index]
    y = (d[TARGET] == 2).astype(int).to_numpy()
    treino = ~f["holdout"].to_numpy()

    def pr_auc(variaveis: list[str]) -> float:
        """PR-AUC no holdout de um subconjunto de variaveis, com a logistica L2.

        Reajusta o modelo do zero a cada candidato — a selecao gulosa chama isto O(k·p)
        vezes, e e por isso que o degrau avaliado e a logistica e nao o boosting.

        Ressalva que vale para toda a curva: a selecao escolhe a variavel **olhando para
        o mesmo holdout** onde reporta a metrica. A curva serve para dimensionar quantas
        perguntas bastam, nao para publicar o numero final do escore — esse sai da
        Trilha C, com particao propria.
        """
        X = d[variaveis].astype("float32").to_numpy()
        m = construir("2_logistica_l2", len(variaveis))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m.fit(X[treino], y[treino])
        return float(average_precision_score(y[~treino], m.predict_proba(X[~treino])[:, 1]))

    escolhidas: list[str] = []
    restantes = list(bloco)
    curva = []
    while restantes and len(escolhidas) < passos:
        melhor, melhor_v = None, -1.0
        for c in restantes:
            v = pr_auc([*escolhidas, c])
            if v > melhor_v:
                melhor, melhor_v = c, v
        escolhidas.append(melhor)
        restantes.remove(melhor)
        curva.append({
            "n_variaveis": len(escolhidas),
            "adicionada": melhor,
            "pr_auc": round(melhor_v, 4),
            "%_do_teto": round(melhor_v / teto * 100, 1),
            "variaveis": list(escolhidas),
        })
        print(f"    {len(escolhidas)} vars (+{melhor:22}) PR-AUC {melhor_v:.4f}  "
              f"{melhor_v / teto * 100:5.1f}% do melhor modelo")
    return {"teto_referencia": round(teto, 4), "curva": curva}


def main() -> None:
    """Roda a escada nos dois blocos, teto de Bayes, parcimonia e vazamento; grava `gold/_escada_modelos.json`."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--silver", type=Path,
                    default=Path("data/processed/diabetes_silver.parquet"))
    ap.add_argument("--folds", type=Path,
                    default=Path("data/processed/gold/folds.parquet"))
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_escada_modelos.json"))
    args = ap.parse_args()

    df = pd.read_parquet(args.silver)
    folds = pd.read_parquet(args.folds)
    folds.index = df.index
    registrar("modelos", "inicio", n=len(df))

    print("  teto de Bayes empirico…")
    teto = teto_de_bayes(df.loc[df[TARGET].isin([0, 2])], SEM_ACESSO)
    print(f"    acerto maximo por grupo: {teto['acerto_maximo_ponderado']:.4f}")

    print("  bloco SEM proxies de acesso (mede risco)…")
    sem = rodar_bloco(df, folds, SEM_ACESSO, "sem proxies de acesso")

    print("  bloco COM proxies de acesso (risco + trajetoria diagnostica)…")
    com = rodar_bloco(df, folds, TODAS, "com proxies de acesso")

    print("  curva de parcimonia (quantas variaveis bastam?)…")
    parcimonia = curva_de_parcimonia(
        df, folds, SEM_ACESSO, com["modelos"]["5_gb_calibrado"]["holdout"]["pr_auc"])

    print("  demonstracao de vazamento por duplicata…")
    vaz = demonstrar_vazamento(df, folds, SEM_ACESSO)
    print(f"    split aleatorio infla PR-AUC em {vaz['inflacao_pr_auc_%']}% "
          f"({vaz['pct_teste_contaminado']}% do teste contaminado)")

    saida = {
        "protocolo": {
            "alvo": "diabetes (classe 2) vs sem diabetes (classe 0); classe 1 excluida",
            "particao": "StratifiedGroupKFold(5) por hash das features + holdout 20%",
            "seed": SEED,
            "desbalanceamento": "class_weight balanced (ADR 0004) — sem reamostragem",
            "metrica_principal": "PR-AUC (ADR 0005) — acuracia nao reportada",
        },
        "teto_de_bayes": teto,
        "parcimonia": parcimonia,
        "sem_proxies_de_acesso": sem,
        "com_proxies_de_acesso": com,
        "vazamento": vaz,
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("modelos", "fim", saida=str(args.saida))

    print("\n=== RESUMO (holdout) ===")
    linhas = []
    for chave, res in (("sem acesso", sem), ("com acesso", com)):
        for nome, r in res["modelos"].items():
            linhas.append({"bloco": chave, "modelo": nome,
                           "vars": r["variaveis"],
                           "PR_AUC": r["holdout"]["pr_auc"],
                           "ganho_vs_prev": r["holdout"]["pr_auc_ganho"],
                           "ROC_AUC": r["holdout"]["roc_auc"],
                           "recall@esp90": r["holdout"]["recall_esp90"],
                           "Brier": r["holdout"]["brier"],
                           "ECE": r["holdout"]["ece"]})
    print(pd.DataFrame(linhas).to_string(index=False))


if __name__ == "__main__":
    main()
