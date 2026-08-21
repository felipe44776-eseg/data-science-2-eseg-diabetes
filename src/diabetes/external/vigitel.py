"""Vigitel 2015 — comparacao binacional de odds ratio.

Por que Vigitel e nao outra fonte: e o **analogo desenhado** do BRFSS. Inquerito
telefonico, adultos >= 18 anos, autorrelato de diagnostico medico, com peso de
pos-estratificacao por raking. E existe **para o mesmo ano de 2015**, o que
elimina o ano como explicacao alternativa de qualquer diferenca.

A pergunta: os fatores de risco de diabetes se comportam igual nos dois paises?
Fator que se mantem nos dois e robusto; fator que diverge revela o efeito do
sistema de saude (SUS universal vs. cobertura privada) sobre o **diagnostico**.

Unidades em escala natural, nao padronizadas: o desvio-padrao de IMC difere entre
as duas populacoes, entao OR por DP nao seria comparavel. Usamos:
IMC por 5 kg/m2, idade por faixa de 5 anos, escolaridade por nivel harmonizado.

Uso:
    python -m diabetes.external.vigitel
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
from diabetes.external.brfss2015 import (
    COLUNAS_BRFSS,
    DESENHO,
    carregar_xpt,
    reconstruir_sem_descarte,
)
from diabetes.pipeline.estado import registrar

VIGITEL = Path("data/external/vigitel")
XPT = Path("data/external/brfss2015/LLCP2015.XPT")
SAIDA = Path("data/external/vigitel/_comparacao_binacional.json")

#: variaveis presentes e comparaveis nas DUAS pesquisas.
#: O que ficou de fora e por que esta em `NAO_COMPARAVEL`.
COMUM = ["hipertensao", "imc5", "fumante", "atividade_fisica", "frutas",
         "sexo", "idade_faixa", "escolaridade3"]

NAO_COMPARAVEL = {
    "colesterol_alto": "Vigitel 2015 nao pergunta diagnostico de colesterol alto",
    "avc": "ausente no Vigitel 2015",
    "doenca_cardiaca": "ausente no Vigitel 2015",
    "vegetais": "Vigitel mede feijao e hortalicas com pergunta de forma diferente",
    "saude_geral": ("EXISTE no Vigitel (q74) — mas a escala difere: o BRFSS separa "
                    "'excelente' de 'muito boa' e o Vigitel nao. Fora do modelo comum "
                    "de OR por isso; usada no escore brasileiro com mapeamento "
                    "declarado em docs/18 §1"),
    "saude_mental_dias": "ausente no Vigitel 2015",
    "saude_fisica_dias": "ausente no Vigitel 2015",
    "dificuldade_caminhar": "ausente no Vigitel 2015",
    "renda_faixa": "Vigitel nao coleta renda de forma comparavel",
    "sem_consulta_por_custo": "ausente no Vigitel 2015",
    "exame_colesterol": "Vigitel 2015 pergunta o exame, mas a janela temporal difere",
    "alcool_excessivo": ("BRFSS mede volume semanal; Vigitel mede binge (5/4 doses "
                         "numa ocasiao). Construtos diferentes — nao comparar"),
}

#: idade em anos -> faixa BRFSS `_AGEG5YR` (1 = 18-24 ... 13 = 80+)
LIMITES_IDADE = [25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]


def faixa_etaria(anos: pd.Series) -> pd.Series:
    return pd.Series(np.digitize(anos.to_numpy(float), LIMITES_IDADE) + 1,
                     index=anos.index).astype("Float32")


def escolaridade_3(brfss_educa: pd.Series) -> pd.Series:
    """Colapsa EDUCA (1-6) para a escala de 3 niveis do Vigitel `fesc`.

    1 = ate 8 anos de estudo · 2 = 9 a 11 anos · 3 = 12 anos ou mais
    """
    e = brfss_educa.astype(float).to_numpy()  # Float32 nullable -> ndarray para np.select
    return pd.Series(np.select(
        [e <= 2, e <= 4, e <= 6], [1.0, 2.0, 3.0], default=np.nan),
        index=brfss_educa.index).astype("Float32")


# --------------------------------------------------------------------------

#: colunas extraidas do .xls para o parquet. Inclui mais do que a comparacao
#: binacional usa, porque `escore_brasil` consome o mesmo arquivo — extrair duas
#: vezes um .xls de 58 MB seria desperdicio.
COLUNAS_VIGITEL = [
    "ano", "cidade", "pesorake", "q6", "q7", "q9", "q11", "q9_i", "q11_i",
    "q15", "q27", "q37", "q38", "q42", "q44", "q60", "q64",
    "q74",          # estado de saude autoavaliado — usado no escore brasileiro
    "q75", "q76", "q88", "fesc", "fxesc", "q8_anos", "r138", "excpeso_i",
]


def extrair_parquet(xls: Path, destino: Path) -> int:
    """Le o .xls (58 MB, formato OLE2) uma vez e grava o parquet de trabalho."""
    df = pd.read_excel(xls, usecols=lambda c: c in COLUNAS_VIGITEL)
    faltando = set(COLUNAS_VIGITEL) - set(df.columns)
    if faltando:
        print(f"    aviso: colunas ausentes no Vigitel 2015: {sorted(faltando)}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino, index=False)
    return len(df)


def carregar_vigitel(caminho: Path) -> pd.DataFrame:
    """Harmoniza o Vigitel 2015 para o esquema do projeto."""
    cols = ["ano", "cidade", "pesorake", "q6", "q7", "q9_i", "q11_i", "q27",
            "q42", "q60", "q64", "q75", "q76", "q88", "fesc", "r138"]
    if caminho.suffix == ".parquet":
        v = pd.read_parquet(caminho)
    else:
        v = pd.read_excel(caminho, usecols=lambda c: c in cols)

    out = pd.DataFrame(index=v.index)

    # alvo: q76 1=sim 2=nao 777=nao sabe. r138=1 -> diabetes apenas na gravidez,
    # que o BRFSS tambem manda para a categoria "sem diabetes" (DIABETE3=2 -> 0)
    alvo = v["q76"].where(v["q76"].isin([1, 2]))
    alvo = alvo.replace({1: 1, 2: 0})
    alvo = alvo.mask((alvo == 1) & (v["r138"] == 1), 0)
    out["diabetes"] = alvo.astype("Float32")

    out["hipertensao"] = v["q75"].where(v["q75"].isin([1, 2])).replace({1: 1, 2: 0}).astype("Float32")
    imc = v["q9_i"] / (v["q11_i"] / 100) ** 2
    out["imc5"] = (imc.where(imc.between(12, 98)) / 5).astype("Float32")

    # fumante = ja fumou (atual ou ex), para casar com SMOKE100 do BRFSS
    out["fumante"] = ((v["q60"].isin([1, 2])) | (v["q64"].isin([1, 2]))).astype("Float32")

    out["atividade_fisica"] = v["q42"].where(v["q42"].isin([1, 2])).replace({1: 1, 2: 0}).astype("Float32")
    # q27 == 4 -> todos os dias; equivale a _FRTLT1 (>= 1x/dia)
    out["frutas"] = v["q27"].where(v["q27"].between(1, 6)).eq(4).astype("Float32")
    out["acesso_saude"] = v["q88"].where(v["q88"].isin([1, 2, 3])).isin([1, 2]).astype("Float32")
    out["sexo"] = v["q7"].where(v["q7"].isin([1, 2])).replace({1: 1, 2: 0}).astype("Float32")
    out["idade_faixa"] = faixa_etaria(v["q6"])
    out["escolaridade3"] = v["fesc"].where(v["fesc"].isin([1, 2, 3])).astype("Float32")
    out["peso"] = v["pesorake"].astype(float)
    out["cidade"] = v["cidade"]
    return out


def carregar_brfss(xpt: Path) -> pd.DataFrame:
    bruto = carregar_xpt(xpt, colunas=COLUNAS_BRFSS + DESENHO)
    b = reconstruir_sem_descarte(bruto)
    out = pd.DataFrame(index=b.index)
    out["diabetes"] = (b["diabetes"] == 2).astype("Float32").where(b["diabetes"].notna())
    for c in ("hipertensao", "fumante", "atividade_fisica", "frutas", "sexo",
              "idade_faixa", "acesso_saude"):
        out[c] = b[c]
    out["imc5"] = b["imc"] / 5
    out["escolaridade3"] = escolaridade_3(b["escolaridade"])
    out["peso"] = b["_LLCPWT"].astype(float)
    return out


# --------------------------------------------------------------------------

def ajustar(df: pd.DataFrame, variaveis: list[str]) -> pd.DataFrame:
    """Logistica ponderada, com peso reescalado ao n efetivo de Kish."""
    d = df[[*variaveis, "diabetes", "peso"]].dropna()
    X = sm.add_constant(d[variaveis].astype(float), has_constant="add")
    w = d["peso"].to_numpy(float)
    w = w * (n_efetivo_kish(d["peso"]) / w.sum())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = sm.GLM(d["diabetes"].astype(int), X,
                     family=sm.families.Binomial(), freq_weights=w).fit()
    ic = res.conf_int()
    return pd.DataFrame({
        "or": np.exp(res.params),
        "ic_baixo": np.exp(ic[0]),
        "ic_alto": np.exp(ic[1]),
    }).drop(index="const", errors="ignore")


def prevalencia(df: pd.DataFrame) -> dict:
    d = df[["diabetes", "peso"]].dropna()
    return {
        "n": int(len(d)),
        "n_efetivo": round(float(n_efetivo_kish(d["peso"]))),
        "bruta_%": round(float(d["diabetes"].mean() * 100), 3),
        "ponderada_%": round(float(np.average(d["diabetes"], weights=d["peso"]) * 100), 3),
    }


def comparar(br: pd.DataFrame, us: pd.DataFrame) -> dict:
    o_br, o_us = ajustar(br, COMUM), ajustar(us, COMUM)
    comp = pd.DataFrame({
        "OR_Brasil": o_br["or"].round(3),
        "IC_Brasil": o_br.apply(lambda r: f"[{r['ic_baixo']:.2f}; {r['ic_alto']:.2f}]", axis=1),
        "OR_EUA": o_us["or"].round(3),
        "IC_EUA": o_us.apply(lambda r: f"[{r['ic_baixo']:.2f}; {r['ic_alto']:.2f}]", axis=1),
        "razao_BR_EUA": (o_br["or"] / o_us["or"]).round(2),
        "mesma_direcao": ((o_br["or"] - 1) * (o_us["or"] - 1) > 0),
        "ic_sobrepoe": [
            not (a_hi < b_lo or b_hi < a_lo)
            for a_lo, a_hi, b_lo, b_hi in zip(
                o_br["ic_baixo"], o_br["ic_alto"],
                o_us["ic_baixo"], o_us["ic_alto"], strict=True)
        ],
    }).sort_values("razao_BR_EUA", ascending=False)

    # acesso a saude tem significado radicalmente diferente sob o SUS:
    # rodado a parte, nunca dentro do modelo comum
    acesso = {
        "Brasil_%_plano_privado": round(float(np.average(
            br["acesso_saude"].dropna(),
            weights=br.loc[br["acesso_saude"].notna(), "peso"]) * 100), 2),
        "EUA_%_com_cobertura": round(float(np.average(
            us["acesso_saude"].dropna(),
            weights=us.loc[us["acesso_saude"].notna(), "peso"]) * 100), 2),
        "nota": ("no Brasil q88 mede plano PRIVADO — a cobertura publica pelo SUS e "
                 "universal e nao aparece nesta variavel; nos EUA HLTHPLN1 mede "
                 "qualquer cobertura. Nao sao a mesma coisa e nao entram no modelo"),
    }
    return {"odds_ratio": comp.to_dict("index"), "acesso": acesso}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vigitel", type=Path,
                    default=VIGITEL / "vigitel2015_bruto.parquet")
    ap.add_argument("--xpt", type=Path, default=XPT)
    ap.add_argument("--saida", type=Path, default=SAIDA)
    args = ap.parse_args()

    xls = VIGITEL / "Vigitel-2015-peso-rake.xls"
    if not args.vigitel.exists():
        if not xls.exists():
            raise SystemExit(f"microdados do Vigitel ausentes: {xls}. "
                             "URL e hash em data/external/FONTES.md")
        print(f"  extraindo o parquet de trabalho de {xls.name}…")
        n = extrair_parquet(xls, args.vigitel)
        print(f"    {n:,} linhas gravadas em {args.vigitel}")
    fonte = args.vigitel
    registrar("vigitel", "inicio", fonte=str(fonte))

    print("  carregando Vigitel 2015…")
    br = carregar_vigitel(fonte)
    print(f"    {len(br):,} respondentes · {br['cidade'].nunique()} capitais")
    print("  carregando BRFSS 2015…")
    us = carregar_brfss(args.xpt)
    print(f"    {len(us):,} respondentes")

    prev = {"Brasil_Vigitel_2015": prevalencia(br), "EUA_BRFSS_2015": prevalencia(us)}
    res = comparar(br, us)

    saida = {
        "fontes": {
            "Brasil": "Vigitel 2015 (Ministerio da Saude) — 27 capitais, peso rake",
            "EUA": "BRFSS 2015 (CDC) — 50 estados + DC + territorios, peso _LLCPWT",
        },
        "ressalva_de_cobertura": ("Vigitel cobre apenas capitais; BRFSS cobre todo o "
                                  "pais. A diferenca de cobertura geografica e a "
                                  "principal limitacao desta comparacao."),
        "variaveis_comuns": COMUM,
        "variaveis_nao_comparaveis": NAO_COMPARAVEL,
        "prevalencia": prev,
        **res,
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("vigitel", "fim", saida=str(args.saida))

    print("\n=== PREVALENCIA DE DIABETES (autorrelato de diagnostico) ===")
    print(pd.DataFrame(prev).T.to_string())
    print("\n=== ODDS RATIO AJUSTADO — mesmo modelo nas duas pesquisas ===")
    print(pd.DataFrame(res["odds_ratio"]).T.to_string())
    print("\n=== ACESSO ===")
    print(json.dumps(res["acesso"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
