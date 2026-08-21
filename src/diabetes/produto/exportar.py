"""Produto — exporta o modelo para rodar no navegador, sem servidor.

Por que da para fazer isso
--------------------------
O EBM e **aditivo**:

    logit P(y) = intercepto + Σ f_j(x_j) + Σ f_jk(x_j, x_k)

e cada `f` e uma **tabela de consulta** sobre faixas. Nao ha algebra de matriz,
nao ha arvore para percorrer: sao somas de valores tabelados. Isso significa que
a predicao pode ser reimplementada em ~30 linhas de JavaScript e dar o **mesmo
numero**, bit a bit — nao uma aproximacao.

Consequencia pratica: o produto e um arquivo HTML que funciona offline, sem
Python, sem servidor e sem internet. Da para abrir no notebook durante a
apresentacao e deixar a plateia usar.

Estrutura da tabela de consulta (`interpret` 0.7)
-------------------------------------------------
  `bins_[f][r]`      cortes da variavel f na resolucao r
  `term_scores_[t]`  vetor (ou matriz, em interacao) com len(cortes)+3 posicoes:
                     [0] = ausente · [1..n+1] = as faixas · [n+2] = desconhecido
  resolucao usada    r = min(ordem do termo − 1, resolucoes disponiveis − 1)

O indice de faixa e: 0 se ausente; senao 1 + quantidade de cortes <= valor.

Verificacao
-----------
`verificar_paridade()` reimplementa a predicao **so com o JSON exportado** e
compara com `predict_proba` do sklearn. Se divergirem, o export esta errado e o
modulo falha — antes de o JavaScript existir.

Uso:
    python -m diabetes.produto.exportar
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from diabetes.eval.escore import (
    VARS_B,
    _faixas,
    ajustar,
    aplicar,
    calibrar,
    pontos_inteiros,
)
from diabetes.models.expandido import particionar
from diabetes.pipeline.estado import registrar

ENTRADA = Path("data/processed/gold/brfss_expandido.parquet")
SAIDA = Path("reports/produto")
SEED = 42

#: variaveis do modelo interpretavel, em ordem de apresentacao no formulario.
#: Todas respondiveis por leigo — `TOLDHI2` exige exame previo e por isso e
#: marcada como opcional: o EBM tem faixa propria para ausente.
PERGUNTAS = [
    {"var": "_AGE80", "tipo": "numero", "rotulo": "Qual a sua idade?",
     "unidade": "anos", "min": 18, "max": 99, "padrao": 45},
    {"var": "_BMI5", "tipo": "imc", "rotulo": "Peso e altura",
     "ajuda": "usados só para calcular o IMC"},
    {"var": "GENHLTH", "tipo": "opcoes", "rotulo": "De modo geral, como você avalia a sua saúde?",
     "opcoes": [[1, "Excelente"], [2, "Muito boa"], [3, "Boa"],
                [4, "Regular"], [5, "Ruim"]], "padrao": 3},
    {"var": "_RFHYPE5", "tipo": "opcoes", "rotulo": "Já lhe disseram que tem pressão alta?",
     "opcoes": [[1, "Não"], [2, "Sim"]], "padrao": 1},
    {"var": "SEX", "tipo": "opcoes", "rotulo": "Sexo",
     "opcoes": [[2, "Feminino"], [1, "Masculino"]], "padrao": 2},
    {"var": "TOLDHI2", "tipo": "opcoes", "rotulo": "Já lhe disseram que tem colesterol alto?",
     "opcoes": [[2, "Não"], [1, "Sim"], [None, "Nunca fiz o exame"]],
     "padrao": 2, "nota": "exige exame prévio — “nunca fiz” é resposta válida"},
    {"var": "CHCKIDNY", "tipo": "opcoes", "rotulo": "Tem doença renal?",
     "opcoes": [[2, "Não"], [1, "Sim"]], "padrao": 2},
    {"var": "HAVARTH3", "tipo": "opcoes", "rotulo": "Tem artrite?",
     "opcoes": [[2, "Não"], [1, "Sim"]], "padrao": 2},
    {"var": "ADDEPEV2", "tipo": "opcoes", "rotulo": "Já teve diagnóstico de depressão?",
     "opcoes": [[2, "Não"], [1, "Sim"]], "padrao": 2},
    {"var": "DIFFWALK", "tipo": "opcoes",
     "rotulo": "Tem dificuldade séria para caminhar ou subir escadas?",
     "opcoes": [[2, "Não"], [1, "Sim"]], "padrao": 2},
    {"var": "INCOME2", "tipo": "opcoes", "rotulo": "Faixa de renda anual do domicílio",
     "opcoes": [[1, "menos de US$ 10 mil"], [2, "US$ 10–15 mil"], [3, "US$ 15–20 mil"],
                [4, "US$ 20–25 mil"], [5, "US$ 25–35 mil"], [6, "US$ 35–50 mil"],
                [7, "US$ 50–75 mil"], [8, "US$ 75 mil ou mais"], [None, "Prefiro não dizer"]],
     "padrao": 6, "nota": "escala do BRFSS, em dólares de 2015"},
    {"var": "_RACEGR3", "tipo": "opcoes", "rotulo": "Raça/etnia (categorias do CDC)",
     "opcoes": [[1, "Branco não-hispânico"], [2, "Negro não-hispânico"],
                [5, "Hispânico"], [4, "Multirracial"], [3, "Outro"],
                [None, "Prefiro não dizer"]],
     "padrao": 1,
     "nota": "usada como proxy de determinantes sociais, nunca como fator biológico — ver docs/10"},
]

NOMES_PT = {
    "_AGE80": "Idade", "_BMI5": "IMC", "GENHLTH": "Saúde autoavaliada",
    "_RFHYPE5": "Pressão alta", "TOLDHI2": "Colesterol alto", "SEX": "Sexo",
    "CHCKIDNY": "Doença renal", "HAVARTH3": "Artrite", "ADDEPEV2": "Depressão",
    "DIFFWALK": "Dificuldade para caminhar", "INCOME2": "Renda",
    "_RACEGR3": "Raça/etnia",
}


# --------------------------------------------------------------------------
# export do EBM
# --------------------------------------------------------------------------

def exportar_ebm(m, variaveis: list[str]) -> dict:
    """Serializa o EBM como tabelas de consulta: intercepto, cortes e scores.

    Nao e um resumo do modelo — e o modelo. Como o EBM e aditivo, a predicao vira
    soma de valores tabelados, e reimplementa-la em JavaScript da o mesmo numero.

    Para cada termo, a resolucao de bins e `r = min(ordem - 1, len(bins) - 1)`, que
    e a convencao do `interpret` 0.7: termo de interacao usa a grade mais grossa.
    `scores` sai achatado com `forma` ao lado, para o JavaScript reindexar sem
    biblioteca de array — e as posicoes extras por dimensao (ausente, faixas,
    desconhecido) vao junto, porque a pagina precisa delas para tratar campo em
    branco. Quem confirma que a indexacao ficou certa e `verificar_paridade`, nao
    esta funcao.
    """
    termos = []
    for t, feats in enumerate(m.term_features_):
        ordem = len(feats)
        cortes = []
        for f in feats:
            r = min(ordem - 1, len(m.bins_[f]) - 1)
            cortes.append([float(x) for x in np.asarray(m.bins_[f][r])])
        s = np.asarray(m.term_scores_[t], dtype=float)
        termos.append({
            "nome": str(m.term_names_[t]),
            "variaveis": [variaveis[f] for f in feats],
            "cortes": cortes,
            "forma": list(s.shape),
            "scores": [float(x) for x in s.ravel()],
        })
    return {
        "intercepto": float(np.asarray(m.intercept_).ravel()[0]),
        "variaveis": variaveis,
        "termos": termos,
        "link": "logit",
    }


#: JSON nao tem Infinity nem NaN. Python serializa como `Infinity`/`NaN`, que o
#: `JSON.parse` do navegador REJEITA — e o erro so aparece em tempo de execucao,
#: com a pagina ja aberta. Trocamos por finitos grandes e proibimos nao-finito na
#: serializacao (`allow_nan=False`), para o build falhar em vez da apresentacao.
LIMITE_FINITO = 1e12


def _finitizar(o):
    """Substitui ±inf e NaN por finitos, recursivamente."""
    if isinstance(o, dict):
        return {k: _finitizar(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_finitizar(v) for v in o]
    if isinstance(o, float):
        if o == float("inf"):
            return LIMITE_FINITO
        if o == float("-inf"):
            return -LIMITE_FINITO
        if o != o:                      # NaN
            return None
    return o


def _indice(valor, cortes: list[float]) -> int:
    """0 se ausente; senao 1 + quantos cortes sao <= valor."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return 0
    i = 1
    for c in cortes:
        if valor < c:
            break
        i += 1
    return i


def prever_do_json(modelo: dict, linha: dict) -> tuple[float, list[dict]]:
    """Reimplementacao da predicao usando SO o JSON exportado.

    E a mesma logica que o JavaScript executa. Se esta funcao bater com o
    sklearn, o navegador tambem bate.
    """
    total = modelo["intercepto"]
    contrib = []
    for termo in modelo["termos"]:
        idx = [_indice(linha.get(v), termo["cortes"][k])
               for k, v in enumerate(termo["variaveis"])]
        forma = termo["forma"]
        plano = 0
        for k, i in enumerate(idx):
            i = min(i, forma[k] - 1)
            plano = plano * forma[k] + i
        s = termo["scores"][plano]
        total += s
        contrib.append({"termo": termo["nome"], "contribuicao": s})
    return 1.0 / (1.0 + np.exp(-total)), contrib


def gerar_casos_paridade(m, df: pd.DataFrame, variaveis: list[str],
                         destino: Path, n: int = 500) -> int:
    """Casos com a probabilidade do sklearn, para o teste em Node conferir.

    Inclui deliberadamente linhas com valor **ausente** — a faixa "ausente" do
    EBM e o que permite a resposta "nunca fiz o exame" na pagina, e e o caminho
    mais facil de quebrar sem perceber.
    """
    rng = np.random.default_rng(SEED)
    amostra = df.sample(min(n, len(df)), random_state=SEED).copy()
    # forca ausencia em algumas linhas, nas variaveis que a pagina deixa em branco
    for col in ("TOLDHI2", "INCOME2", "_RACEGR3"):
        alvo = rng.choice(amostra.index, size=max(len(amostra) // 12, 5), replace=False)
        amostra.loc[alvo, col] = np.nan
    p = m.predict_proba(amostra[variaveis].astype("float32"))[:, 1]
    casos = [{
        "entrada": {v: (None if pd.isna(r[v]) else float(r[v])) for v in variaveis},
        "p_python": float(pp),
    } for (_, r), pp in zip(amostra.iterrows(), p, strict=True)]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(_finitizar({"casos": casos}), ensure_ascii=False,
                   allow_nan=False, separators=(",", ":")), encoding="utf-8")
    return len(casos)


def verificar_paridade(m, modelo: dict, df: pd.DataFrame, variaveis: list[str],
                       n: int = 3000) -> dict:
    """O JSON exportado reproduz `predict_proba`? Se nao, o export esta errado."""
    amostra = df.sample(min(n, len(df)), random_state=SEED)
    p_sk = m.predict_proba(amostra[variaveis].astype("float32"))[:, 1]
    p_js = np.array([
        prever_do_json(modelo, {v: (None if pd.isna(r[v]) else float(r[v]))
                                for v in variaveis})[0]
        for _, r in amostra.iterrows()])
    dif = np.abs(p_sk - p_js)
    return {"n": int(len(amostra)), "erro_max": float(dif.max()),
            "erro_medio": float(dif.mean()),
            "aprovado": bool(dif.max() < 1e-9)}


# --------------------------------------------------------------------------

def main() -> None:
    """Ajusta o EBM, verifica paridade com o JS e grava `reports/produto/modelo.json`."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, default=ENTRADA)
    ap.add_argument("--saida", type=Path, default=SAIDA / "modelo.json")
    args = ap.parse_args()

    from interpret.glassbox import ExplainableBoostingClassifier

    df = pd.read_parquet(args.entrada)
    te = particionar(df)
    variaveis = [p["var"] for p in PERGUNTAS]
    registrar("produto", "inicio", n=len(df))

    print("  ajustando o EBM do produto…")
    X = df[variaveis].astype("float32")
    y = df["diabetes"].to_numpy()
    m = ExplainableBoostingClassifier(
        feature_names=variaveis, interactions=8, max_bins=64,
        outer_bags=8, random_state=SEED, n_jobs=-1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X[~te], y[~te])

    from sklearn.metrics import average_precision_score, roc_auc_score
    p_te = m.predict_proba(X[te])[:, 1]
    metricas = {
        "roc_auc": round(float(roc_auc_score(y[te], p_te)), 4),
        "pr_auc": round(float(average_precision_score(y[te], p_te)), 4),
        "n_treino": int((~te).sum()), "n_holdout": int(te.sum()),
    }
    print(f"    ROC-AUC {metricas['roc_auc']}  PR-AUC {metricas['pr_auc']}")

    modelo = _finitizar(exportar_ebm(m, variaveis))
    # ida e volta pelo TEXTO: e exatamente o que o navegador recebe. Se algo nao
    # for serializavel (inf, NaN), falha aqui e nao na apresentacao.
    modelo = json.loads(json.dumps(modelo, allow_nan=False))
    print("  verificando paridade entre o JSON e o sklearn…")
    par = verificar_paridade(m, modelo, df[te], variaveis)
    print(f"    erro maximo {par['erro_max']:.3e}  ->  "
          f"{'APROVADO' if par['aprovado'] else 'REPROVADO'}")
    if not par["aprovado"]:
        raise SystemExit("export do EBM nao reproduz o modelo — abortando")

    # --- escore de papel ---------------------------------------------------
    print("  exportando o escore de 5 perguntas…")
    faixas = _faixas(df)
    coef, _ = ajustar(df, faixas, VARS_B, ~te)
    tab = pontos_inteiros(coef, VARS_B)
    pts = aplicar(faixas, tab, VARS_B)
    cal = calibrar(pts, df["diabetes"].astype(int), df["_LLCPWT"].astype(float), ~te)

    # --- distribuicao populacional de risco, para o percentil --------------
    w = df.loc[te, "_LLCPWT"].to_numpy(float)
    ordem = np.argsort(p_te)
    acum = np.cumsum(w[ordem]) / w.sum()
    percentis = [{"risco": round(float(p_te[ordem][i]), 5),
                  "percentil": round(float(acum[i]) * 100, 2)}
                 for i in np.linspace(0, len(p_te) - 1, 200).astype(int)]

    saida = {
        "gerado_por": "python -m diabetes.produto.exportar",
        "fonte": "BRFSS 2015 (CDC), 432.968 respondentes",
        "metricas": metricas,
        "paridade_export": par,
        "perguntas": PERGUNTAS,
        "nomes_pt": NOMES_PT,
        "ebm": modelo,
        "escore_papel": {"variaveis": VARS_B, "tabela": tab["pontos"],
                         "calibracao": cal},
        "percentis": percentis,
        "referencias": {
            "prevalencia_eua_diagnosticada_%": 10.67,
            "prevalencia_eua_verdadeira_%": 14.29,
            "prevalencia_brasil_vigitel_2015_%": 7.08,
            "nota": "docs/05, docs/09 e docs/12",
        },
    }
    n_casos = gerar_casos_paridade(m, df[te], variaveis,
                                   args.saida.parent / "_casos_paridade.json")
    print(f"  {n_casos} casos de paridade gerados para o teste em Node")

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(
        json.dumps(_finitizar(saida), ensure_ascii=False, allow_nan=False,
                   separators=(",", ":")),
        encoding="utf-8")
    kb = args.saida.stat().st_size / 1024
    print(f"  {args.saida}  ({kb:.0f} KB, {len(modelo['termos'])} termos)")
    registrar("produto", "fim", kb=round(kb))


if __name__ == "__main__":
    main()
