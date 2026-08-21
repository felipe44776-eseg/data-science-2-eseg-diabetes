"""Analise nao supervisionada: fenotipos, padroes de comorbidade e atipicos.

Quatro tecnicas, e a escolha de cada uma tem motivo
---------------------------------------------------

**MCA, nao PCA.** A base e majoritariamente categorica. PCA supoe variavel
continua e distancia euclidiana; aplicada a binarias, ela decompoe a variancia de
Bernoulli, o que nao tem interpretacao util. A **analise de correspondencia
multipla** e o analogo correto: opera sobre a matriz indicadora e a metrica
qui-quadrado. PCA em dados binarios aparece em quase todo notebook publico deste
dataset e e um erro de metodo, nao de gosto.

**Clusters sobre as coordenadas da MCA.** Agrupar direto nas variaveis originais
com k-means repete o mesmo erro. Sobre as coordenadas da MCA, a distancia
euclidiana ja e a metrica certa.

**Regras de associacao (FP-Growth).** Responde uma pergunta que modelo nenhum
responde: quais **combinacoes** de condicoes ocorrem juntas mais do que o acaso
explicaria. `lift` e a medida — nao suporte, que so premia o que e comum.

**Isolation Forest cruzado com o PU.** `docs/12` estimou quem sao os provaveis
diabeticos nao diagnosticados. Aqui procuramos **perfis atipicos** e cruzamos: um
perfil raro, de risco alto e sem diagnostico e o candidato mais forte a caso
oculto — e a intersecao das duas listas e uma validacao mutua barata.

Uso:
    python -m diabetes.eda.naosupervisionada
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest

from diabetes.features.expandido import RISCO
from diabetes.models.expandido import particionar
from diabetes.pipeline.estado import registrar

ENTRADA = Path("data/processed/gold/brfss_expandido.parquet")
SEED = 42
N_AMOSTRA = 60_000        # MCA sobre 433 mil linhas nao cabe em memoria util

#: variaveis levadas para a MCA, ja como categorias legiveis
CATEGORICAS = {
    "_RFHYPE5": ("hipertensao", {1.0: "nao", 2.0: "sim"}),
    "TOLDHI2": ("colesterol", {2.0: "nao", 1.0: "sim"}),
    "_MICHD": ("cardiopatia", {2.0: "nao", 1.0: "sim"}),
    "CVDSTRK3": ("avc", {2.0: "nao", 1.0: "sim"}),
    "CHCKIDNY": ("doenca_renal", {2.0: "nao", 1.0: "sim"}),
    "HAVARTH3": ("artrite", {2.0: "nao", 1.0: "sim"}),
    "CHCCOPD1": ("dpoc", {2.0: "nao", 1.0: "sim"}),
    "ASTHMA3": ("asma", {2.0: "nao", 1.0: "sim"}),
    "ADDEPEV2": ("depressao", {2.0: "nao", 1.0: "sim"}),
    "DIFFWALK": ("dific_caminhar", {2.0: "nao", 1.0: "sim"}),
    "SMOKE100": ("fumou", {2.0: "nao", 1.0: "sim"}),
    "_TOTINDA": ("ativ_fisica", {2.0: "nao", 1.0: "sim"}),
    "SEX": ("sexo", {2.0: "feminino", 1.0: "masculino"}),
}


def _categorizar(df: pd.DataFrame) -> pd.DataFrame:
    d = pd.DataFrame(index=df.index)
    for col, (nome, mapa) in CATEGORICAS.items():
        d[nome] = df[col].map(mapa)
    d["idade"] = pd.cut(df["_AGE80"].astype(float), [0, 45, 65, 200],
                        labels=["18-44", "45-64", "65+"])
    d["imc"] = pd.cut(df["_BMI5"].astype(float) / 100, [0, 25, 30, 100],
                      labels=["<25", "25-29", "30+"])
    d["saude"] = pd.cut(df["GENHLTH"].astype(float), [0, 2, 3, 5],
                        labels=["boa+", "regular", "ruim"])
    d["renda"] = pd.cut(df["INCOME2"].astype(float), [0, 4, 6, 8],
                        labels=["baixa", "media", "alta"])
    return d


# --------------------------------------------------------------------------

def rodar_mca(cat: pd.DataFrame, n_comp: int = 6) -> tuple:
    import prince

    m = prince.MCA(n_components=n_comp, random_state=SEED)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = m.fit(cat)
        coord = m.transform(cat)
    inercia = [float(x) for x in m.percentage_of_variance_]
    # contribuicao de cada categoria aos dois primeiros eixos
    cc = m.column_coordinates(cat)
    eixos = {}
    for k in (0, 1):
        s = cc[k].sort_values()
        eixos[f"eixo_{k+1}"] = {
            "negativo": [{"categoria": str(i), "coord": round(float(v), 3)}
                         for i, v in s.head(6).items()],
            "positivo": [{"categoria": str(i), "coord": round(float(v), 3)}
                         for i, v in s.tail(6).items()][::-1],
        }
    return coord, inercia, eixos


def fenotipos(coord: pd.DataFrame, cat: pd.DataFrame, y: np.ndarray,
              w: np.ndarray, k: int = 5) -> list[dict]:
    km = KMeans(n_clusters=k, n_init=10, random_state=SEED)
    rot = km.fit_predict(coord.to_numpy())
    saida = []
    for c in range(k):
        m = rot == c
        perfil = {}
        for col in cat.columns:
            v = cat.loc[m, col].value_counts(normalize=True)
            if len(v):
                perfil[col] = f"{v.index[0]} ({v.iloc[0]*100:.0f}%)"
        saida.append({
            "cluster": c, "n": int(m.sum()),
            "%_da_amostra": round(float(m.mean() * 100), 1),
            "prevalencia_diabetes_%": round(float(np.average(y[m], weights=w[m]) * 100), 2),
            "perfil_modal": perfil,
        })
    return sorted(saida, key=lambda x: -x["prevalencia_diabetes_%"]), rot


def regras(cat: pd.DataFrame, y: np.ndarray, min_sup: float = 0.02,
           top: int = 15) -> list[dict]:
    """FP-Growth sobre condicoes presentes; consequente = diabetes."""
    from mlxtend.frequent_patterns import association_rules, fpgrowth

    # so o que representa presenca de condicao — "nao tem artrite" nao e padrao
    itens = pd.DataFrame({
        f"{c}={v}": (cat[c] == v)
        for c, v in [("hipertensao", "sim"), ("colesterol", "sim"),
                     ("cardiopatia", "sim"), ("avc", "sim"),
                     ("doenca_renal", "sim"), ("artrite", "sim"),
                     ("dpoc", "sim"), ("asma", "sim"), ("depressao", "sim"),
                     ("dific_caminhar", "sim"), ("fumou", "sim"),
                     ("imc", "30+"), ("idade", "65+"), ("saude", "ruim"),
                     ("renda", "baixa")]})
    itens["DIABETES"] = y.astype(bool)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        freq = fpgrowth(itens, min_support=min_sup, use_colnames=True)
        r = association_rules(freq, metric="lift", min_threshold=1.0)
    r = r[r["consequents"].apply(lambda s: s == frozenset({"DIABETES"}))]
    r = r[r["antecedents"].apply(len) >= 2].sort_values("lift", ascending=False)
    return [{
        "condicoes": sorted(str(x) for x in row["antecedents"]),
        "n_condicoes": len(row["antecedents"]),
        "suporte_%": round(float(row["support"]) * 100, 2),
        "confianca_%": round(float(row["confidence"]) * 100, 2),
        "lift": round(float(row["lift"]), 2),
    } for _, row in r.head(top).iterrows()]


def atipicos(X: pd.DataFrame, y: np.ndarray, p_oculto: np.ndarray) -> dict:
    """Isolation Forest cruzado com os provaveis positivos ocultos do PU."""
    m = IsolationForest(n_estimators=200, contamination=0.05,
                        random_state=SEED, n_jobs=-1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        escore = -m.fit(X).score_samples(X)      # maior = mais atipico

    atip = escore >= np.quantile(escore, 0.95)
    pu_alto = p_oculto >= np.quantile(p_oculto, 0.95)
    nao_rot = y == 0

    inter = atip & pu_alto & nao_rot
    esperado = float(atip.mean() * pu_alto.mean() * nao_rot.mean() * len(y))
    return {
        "n_atipicos": int(atip.sum()),
        "n_pu_alto": int(pu_alto.sum()),
        "n_intersecao_nao_rotulados": int(inter.sum()),
        "esperado_por_acaso": round(esperado),
        "lift_da_intersecao": round(inter.sum() / max(esperado, 1), 2),
        "prevalencia_entre_atipicos_%": round(float(y[atip].mean() * 100), 2),
        "prevalencia_geral_%": round(float(y.mean() * 100), 2),
    }, inter


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, default=ENTRADA)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_naosupervisionada.json"))
    args = ap.parse_args()

    from diabetes.models.pu import C_NHANES, ajustar_ps, scar

    df = pd.read_parquet(args.entrada)
    registrar("naosup", "inicio", n=len(df))

    cat_full = _categorizar(df)
    ok = cat_full.notna().all(axis=1).to_numpy()
    rng = np.random.default_rng(SEED)
    idx = rng.choice(np.where(ok)[0], min(N_AMOSTRA, ok.sum()), replace=False)
    cat = cat_full.iloc[idx].astype(str)
    y = df["diabetes"].to_numpy()[idx]
    w = df["_LLCPWT"].to_numpy(float)[idx]
    print(f"  amostra para MCA: {len(cat):,} de {ok.sum():,} completas "
          f"({cat.shape[1]} variaveis categoricas)")

    print("\n  [1] MCA — analise de correspondencia multipla")
    coord, inercia, eixos = rodar_mca(cat)
    print("    inercia explicada: " +
          "  ".join(f"eixo{i+1} {v:.1f}%" for i, v in enumerate(inercia[:4])))
    for eixo, lados in eixos.items():
        pos = ", ".join(x["categoria"] for x in lados["positivo"][:4])
        neg = ", ".join(x["categoria"] for x in lados["negativo"][:4])
        print(f"    {eixo}:  [-] {neg}")
        print(f"    {'':7}  [+] {pos}")

    print("\n  [2] fenotipos de risco (k-means sobre as coordenadas da MCA)")
    fen, rot = fenotipos(coord, cat, y, w)
    for f in fen:
        chave = {k: v for k, v in f["perfil_modal"].items()
                 if k in ("idade", "imc", "hipertensao", "saude", "artrite")}
        print(f"    cluster {f['cluster']}  n={f['n']:>6,} ({f['%_da_amostra']:>4.1f}%)  "
              f"prev {f['prevalencia_diabetes_%']:>5.2f}%   "
              + " · ".join(f"{k}:{v}" for k, v in chave.items()))

    print("\n  [3] padroes de comorbidade (FP-Growth, ordenado por lift)")
    reg = regras(cat, y)
    for r in reg[:8]:
        print(f"    lift {r['lift']:>5.2f}  conf {r['confianca_%']:>5.1f}%  "
              f"sup {r['suporte_%']:>4.1f}%  {' + '.join(r['condicoes'])}")

    print("\n  [4] atipicos cruzados com os provaveis nao diagnosticados (PU)")
    te = particionar(df)
    p_s = ajustar_ps(df, RISCO, te)
    p_y = scar(p_s, C_NHANES)
    oculto = np.clip(p_y - p_s, 0, 1)
    X = df[RISCO].astype("float32").fillna(-1)
    at, inter = atipicos(X, df["diabetes"].to_numpy(), oculto)
    for k, v in at.items():
        print(f"    {k:38} {v}")

    # perfil da intersecao
    perfil_inter = {
        "n": int(inter.sum()),
        "idade_media": round(float(df.loc[inter, "_AGE80"].mean()), 1),
        "imc_medio": round(float(df.loc[inter, "_BMI5"].mean() / 100), 1),
        "%_hipertensao": round(float((df.loc[inter, "_RFHYPE5"] == 2).mean() * 100), 1),
        "%_doenca_renal": round(float((df.loc[inter, "CHCKIDNY"] == 1).mean() * 100), 1),
        "%_fez_exame": round(float((df.loc[inter, "CHOLCHK"] == 1).mean() * 100), 1),
        "%_minoria": round(float((df.loc[inter, "_RACEGR3"] != 1).mean() * 100), 1),
    }
    print("\n    perfil da intersecao (atipico + PU alto + nao rotulado):")
    for k, v in perfil_inter.items():
        print(f"      {k:20} {v}")

    saida = {
        "n_amostra_mca": int(len(cat)),
        "mca": {"inercia_%": [round(v, 2) for v in inercia], "eixos": eixos},
        "fenotipos": fen,
        "regras_de_associacao": reg,
        "atipicos": at,
        "perfil_intersecao": perfil_inter,
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("naosup", "fim")



if __name__ == "__main__":
    main()
