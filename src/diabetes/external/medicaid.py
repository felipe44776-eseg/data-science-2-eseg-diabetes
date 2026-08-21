"""Frente 4 — expansao do Medicaid como experimento natural.

Motivo da decisao
-----------------
O tema central deste projeto e o **vies de acesso ao diagnostico**: `docs/05`
mediu que o arquivo entregue e uma amostra de quem tem acesso; `docs/12` mostrou
que os provaveis diabeticos nao diagnosticados sao clinicamente identicos aos
diagnosticados e diferem so em acesso. Tudo isso foi estabelecido por **ajuste de
covariaveis em dados transversais**, que nao identifica efeito causal.

Em 2014, parte dos estados americanos expandiu o Medicaid e parte nao. Isso e
**variacao exogena de acesso**, no ano imediatamente anterior a nossa base — e
permite estimar o efeito causal do acesso sobre a **taxa de diagnostico**, que e
a pergunta que o projeto vem fazendo desde `docs/01`.

Desenho
-------
    tratados : 25 jurisdicoes que expandiram em 1/1/2014
    controles: 14 que nao expandiram ate 2019
    excluidos: adotantes escalonados (MI, NH, PA, IN, AK, MT, LA, VA, ME, ...)

Excluir os escalonados nao e conveniencia: DiD com adocao escalonada e
inconsistente sob efeito heterogeneo (Goodman-Bacon 2021). Com adocao unica em
uma data, o estimador de dois periodos e valido.

    populacao: adultos de BAIXA RENDA (< 25 mil USD) — os afetados pela politica
    controle interno: adultos de renda alta (>= 50 mil) — nao elegiveis
    -> tripla diferenca (DDD), que absorve choques estaduais que atingem todas
       as faixas de renda

    periodo: 2011-2019. Referencia 2013. 2020+ excluido (COVID).

Dados: `data.cdc.gov` dataset `dttw-5yxu` — prevalencia BRFSS por estado, ano,
faixa de renda, ja ponderada pelo CDC.

Uso:
    python -m diabetes.external.medicaid
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

API = "https://data.cdc.gov/resource/dttw-5yxu.json"
SAIDA = Path("data/external/medicaid")

#: expandiram em 1/1/2014 (KFF). 24 estados + DC.
TRATADOS = {"AZ", "AR", "CA", "CO", "CT", "DE", "DC", "HI", "IL", "IA", "KY",
            "MD", "MA", "MN", "NV", "NJ", "NM", "NY", "ND", "OH", "OR", "RI",
            "VT", "WA", "WV"}

#: nao expandiram ate 2019. WI fica de FORA das duas listas: cobriu adultos ate
#: 100% da linha de pobreza por waiver em 2014, entao nao e controle limpo.
CONTROLES = {"AL", "FL", "GA", "KS", "MS", "MO", "NC", "OK", "SC", "SD",
             "TN", "TX", "WY"}

#: adotantes escalonados — excluidos do desenho (ver docstring)
ESCALONADOS = {"MI", "NH", "PA", "IN", "AK", "MT", "LA", "VA", "ME", "ID",
               "NE", "UT", "WI"}

BAIXA_RENDA = ["Less than $15,000", "$15,000-$24,999"]
ALTA_RENDA = ["$50,000+"]

ANOS = list(range(2011, 2020))
ANO_REF = 2013
ANO_TRATAMENTO = 2014

#: desfecho principal + mecanismos. `response` selecionada por pergunta.
DESFECHOS = {
    "diabetes": ("Diabetes", "Yes"),
    "cobertura": ("Health Care Coverage", "Yes"),
    "barreira_custo": ("Health Care Cost", "Yes"),
    "colesterol_checado": ("Cholesterol Checked", "Yes"),
}


def _buscar(params: dict, tentativas: int = 3) -> list[dict]:
    url = API + "?" + urllib.parse.urlencode(params)
    for k in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.loads(r.read())
        except Exception:
            if k == tentativas - 1:
                raise
            time.sleep(3)
    return []


def baixar_painel(destino: Path) -> pd.DataFrame:
    """Painel estado x ano x faixa de renda x desfecho."""
    linhas = []
    estados = sorted(TRATADOS | CONTROLES)
    for chave, (topico, resposta) in DESFECHOS.items():
        for faixa in BAIXA_RENDA + ALTA_RENDA:
            dados = _buscar({
                "$select": "year,locationabbr,break_out,response,data_value,sample_size",
                "$where": (f"topic='{topico}' and response='{resposta}' and "
                           f"break_out='{faixa}' and "
                           f"year between '{ANOS[0]}' and '{ANOS[-1]}'"),
                "$limit": "50000",
            })
            for r in dados:
                if r.get("locationabbr") not in estados or r.get("data_value") is None:
                    continue
                linhas.append({
                    "desfecho": chave, "ano": int(r["year"]),
                    "uf": r["locationabbr"], "faixa": faixa,
                    "valor": float(r["data_value"]),
                    "n": float(r.get("sample_size") or 0),
                })
            print(f"    {chave:20} {faixa:20} {len(dados):>6} registros")
    df = pd.DataFrame(linhas)
    df["tratado"] = df["uf"].isin(TRATADOS).astype(int)
    df["baixa_renda"] = df["faixa"].isin(BAIXA_RENDA).astype(int)
    df["pos"] = (df["ano"] >= ANO_TRATAMENTO).astype(int)
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino, index=False)
    return df


# --------------------------------------------------------------------------
# estimacao
# --------------------------------------------------------------------------

def _agregar(df: pd.DataFrame, desfecho: str, baixa: bool) -> pd.DataFrame:
    """Media por estado-ano dentro do estrato de renda, ponderada por n."""
    d = df[(df.desfecho == desfecho) & (df.baixa_renda == int(baixa))]
    g = (d.groupby(["uf", "ano", "tratado"])
           .apply(lambda x: np.average(x["valor"], weights=np.maximum(x["n"], 1)),
                  include_groups=False)
           .rename("valor").reset_index())
    return g


def did(df: pd.DataFrame, desfecho: str, baixa: bool = True) -> dict:
    """DiD de dois periodos com efeitos fixos de estado e ano.

    Estimado por OLS com dummies; erro-padrao agrupado por estado, que e o nivel
    do tratamento (Bertrand, Duflo & Mullainathan 2004 — nao agrupar aqui
    subestima grosseiramente o erro-padrao em painel).
    """
    import statsmodels.api as sm

    g = _agregar(df, desfecho, baixa)
    g["pos"] = (g["ano"] >= ANO_TRATAMENTO).astype(int)
    g["did"] = g["tratado"] * g["pos"]
    X = pd.get_dummies(g[["uf", "ano"]].astype(str), drop_first=True).astype(float)
    X["did"] = g["did"].to_numpy()
    X = sm.add_constant(X)
    m = sm.OLS(g["valor"], X).fit(cov_type="cluster",
                                  cov_kwds={"groups": g["uf"]})
    return {
        "desfecho": desfecho,
        "estrato": "baixa renda" if baixa else "renda alta",
        "n_estado_ano": int(len(g)),
        "n_estados": int(g["uf"].nunique()),
        "efeito_pp": round(float(m.params["did"]), 4),
        "ee": round(float(m.bse["did"]), 4),
        "ic95": [round(float(m.conf_int().loc["did", 0]), 4),
                 round(float(m.conf_int().loc["did", 1]), 4)],
        "p": round(float(m.pvalues["did"]), 4),
        "media_pre_tratados": round(float(
            g[(g.tratado == 1) & (g.ano < ANO_TRATAMENTO)]["valor"].mean()), 3),
        "media_pre_controles": round(float(
            g[(g.tratado == 0) & (g.ano < ANO_TRATAMENTO)]["valor"].mean()), 3),
    }


def ddd(df: pd.DataFrame, desfecho: str) -> dict:
    """Tripla diferenca: (baixa - alta renda) x (tratado - controle) x (pos - pre)."""
    import statsmodels.api as sm

    g = pd.concat([_agregar(df, desfecho, True).assign(baixa=1),
                   _agregar(df, desfecho, False).assign(baixa=0)])
    g["pos"] = (g["ano"] >= ANO_TRATAMENTO).astype(int)
    X = pd.get_dummies(g[["uf", "ano"]].astype(str), drop_first=True).astype(float)
    X["baixa"] = g["baixa"].to_numpy()
    X["baixa_x_pos"] = (g["baixa"] * g["pos"]).to_numpy()
    X["baixa_x_trat"] = (g["baixa"] * g["tratado"]).to_numpy()
    X["trat_x_pos"] = (g["tratado"] * g["pos"]).to_numpy()
    X["ddd"] = (g["baixa"] * g["tratado"] * g["pos"]).to_numpy()
    X = sm.add_constant(X)
    m = sm.OLS(g["valor"], X).fit(cov_type="cluster", cov_kwds={"groups": g["uf"]})
    return {
        "desfecho": desfecho, "n_estado_ano_estrato": int(len(g)),
        "efeito_pp": round(float(m.params["ddd"]), 4),
        "ee": round(float(m.bse["ddd"]), 4),
        "ic95": [round(float(m.conf_int().loc["ddd", 0]), 4),
                 round(float(m.conf_int().loc["ddd", 1]), 4)],
        "p": round(float(m.pvalues["ddd"]), 4),
    }


def estudo_de_evento(df: pd.DataFrame, desfecho: str, baixa: bool = True) -> dict:
    """Efeito por ano, com 2013 como referencia.

    Os coeficientes ANTERIORES a 2014 sao o teste de tendencias paralelas: se
    forem proximos de zero, a suposicao de identificacao e plausivel. Se nao
    forem, o DiD nao esta identificado — e reportar isso e obrigatorio.
    """
    import statsmodels.api as sm

    g = _agregar(df, desfecho, baixa)
    X = pd.get_dummies(g[["uf", "ano"]].astype(str), drop_first=True).astype(float)
    for ano in ANOS:
        if ano == ANO_REF:
            continue
        X[f"t{ano}"] = ((g["ano"] == ano) & (g["tratado"] == 1)).astype(float).to_numpy()
    X = sm.add_constant(X)
    m = sm.OLS(g["valor"], X).fit(cov_type="cluster", cov_kwds={"groups": g["uf"]})

    coef = []
    for ano in ANOS:
        if ano == ANO_REF:
            coef.append({"ano": ano, "efeito_pp": 0.0, "ee": 0.0,
                         "ic95": [0.0, 0.0], "referencia": True})
            continue
        k = f"t{ano}"
        coef.append({
            "ano": ano, "efeito_pp": round(float(m.params[k]), 4),
            "ee": round(float(m.bse[k]), 4),
            "ic95": [round(float(m.conf_int().loc[k, 0]), 4),
                     round(float(m.conf_int().loc[k, 1]), 4)],
            "referencia": False,
        })
    pre = [c for c in coef if c["ano"] < ANO_TRATAMENTO and not c["referencia"]]
    return {
        "desfecho": desfecho, "coeficientes": coef,
        "teste_tendencias_paralelas": {
            "anos_pre": [c["ano"] for c in pre],
            "maior_efeito_pre_pp": round(max((abs(c["efeito_pp"]) for c in pre),
                                             default=0.0), 4),
            "algum_pre_significante": any(
                not (c["ic95"][0] <= 0 <= c["ic95"][1]) for c in pre),
        },
    }


def poder_do_desenho(r_did: list[dict], c_subdiag: float = 0.276) -> dict:
    """"Nao detectamos" e diferente de "nao existe". Este calculo separa os dois.

    A cadeia causal plausivel e: expansao -> mais cobertura -> mais rastreamento
    -> mais diagnostico. O efeito sobre o DIAGNOSTICO e o efeito sobre a
    cobertura multiplicado pela fracao de recem-cobertos que tem diabetes ainda
    nao diagnosticado. Se esse produto for menor que a diferenca minima
    detectavel do desenho, o resultado nulo nao informa nada sobre o mecanismo.
    """
    cob = next(r for r in r_did if r["desfecho"] == "cobertura")
    dia = next(r for r in r_did if r["desfecho"] == "diabetes")
    prev_pre = dia["media_pre_tratados"] / 100        # prevalencia na baixa renda
    # entre os recem-cobertos, quantos tem diabetes nao diagnosticado:
    #   prevalencia verdadeira = diagnosticada / (1 - subdiagnostico)
    prev_verdadeira = prev_pre / (1 - c_subdiag)
    fracao_oculta = prev_verdadeira * c_subdiag
    efeito_maximo = cob["efeito_pp"] / 100 * fracao_oculta * 100   # em p.p.
    mde = 2.8 * dia["ee"]     # diferenca minima detectavel, poder 80%, alfa 5%
    return {
        "efeito_sobre_cobertura_pp": cob["efeito_pp"],
        "prevalencia_diagnosticada_baixa_renda_%": round(prev_pre * 100, 2),
        "prevalencia_verdadeira_implicada_%": round(prev_verdadeira * 100, 2),
        "fracao_com_diabetes_oculto_%": round(fracao_oculta * 100, 2),
        "efeito_MAXIMO_esperado_sobre_diagnostico_pp": round(efeito_maximo, 4),
        "erro_padrao_do_desenho_pp": dia["ee"],
        "diferenca_minima_detectavel_pp": round(mde, 4),
        "razao_mde_sobre_efeito_esperado": round(mde / max(efeito_maximo, 1e-9), 1),
        "veredito": ("o desenho NAO tem poder para detectar o efeito esperado — "
                     "o nulo e inconclusivo, nao evidencia de ausencia"
                     if mde > efeito_maximo else
                     "o desenho tem poder; o nulo e informativo"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--painel", type=Path, default=SAIDA / "painel_brfss_estados.parquet")
    ap.add_argument("--saida", type=Path, default=SAIDA / "_frente4_medicaid.json")
    ap.add_argument("--rebaixar", action="store_true", help="forca novo download")
    args = ap.parse_args()

    from diabetes.pipeline.estado import registrar
    registrar("frente4", "inicio")

    if args.painel.exists() and not args.rebaixar:
        df = pd.read_parquet(args.painel)
        print(f"  painel em cache: {len(df):,} linhas")
    else:
        print("  baixando painel do CDC…")
        df = baixar_painel(args.painel)
    print(f"  estados tratados {df[df.tratado == 1].uf.nunique()} · "
          f"controles {df[df.tratado == 0].uf.nunique()} · anos {df.ano.min()}-{df.ano.max()}")

    print("\n  [1] DiD — adultos de BAIXA RENDA")
    r_did = [did(df, k, baixa=True) for k in DESFECHOS]
    print(pd.DataFrame(r_did)[["desfecho", "efeito_pp", "ee", "ic95", "p",
                               "media_pre_tratados", "media_pre_controles"]]
          .to_string(index=False))

    print("\n  [2] placebo — adultos de RENDA ALTA (nao elegiveis)")
    r_alta = [did(df, k, baixa=False) for k in DESFECHOS]
    print(pd.DataFrame(r_alta)[["desfecho", "efeito_pp", "ee", "ic95", "p"]]
          .to_string(index=False))

    print("\n  [3] tripla diferenca")
    r_ddd = [ddd(df, k) for k in DESFECHOS]
    print(pd.DataFrame(r_ddd).to_string(index=False))

    print("\n  [4] o desenho tem poder para o efeito esperado?")
    poder = poder_do_desenho(r_did)
    for k, v in poder.items():
        print(f"    {k:50} {v}")

    print("\n  [5] estudo de evento e tendencias paralelas")
    eventos = {k: estudo_de_evento(df, k) for k in DESFECHOS}
    for k, e in eventos.items():
        t = e["teste_tendencias_paralelas"]
        print(f"    {k:20} maior efeito pre-2014: {t['maior_efeito_pre_pp']:+.3f} p.p."
              f"   algum significante: {t['algum_pre_significante']}")

    saida = {
        "desenho": {
            "tratados": sorted(TRATADOS), "controles": sorted(CONTROLES),
            "excluidos_escalonados": sorted(ESCALONADOS),
            "populacao": "adultos com renda < 25 mil USD",
            "controle_interno": "adultos com renda >= 50 mil USD",
            "periodo": [ANOS[0], ANOS[-1]], "ano_referencia": ANO_REF,
            "erro_padrao": "agrupado por estado",
            "fonte": "data.cdc.gov dttw-5yxu (BRFSS ponderado pelo CDC)",
        },
        "did_baixa_renda": r_did,
        "placebo_renda_alta": r_alta,
        "tripla_diferenca": r_ddd,
        "poder_do_desenho": poder,
        "estudo_de_evento": eventos,
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("frente4", "fim")


if __name__ == "__main__":
    main()
