"""Camada causal — DAG explicito, ajuste por backdoor, refutacao e E-value.

O que esta frente pode e o que nao pode
----------------------------------------
Dados **transversais** nao estabelecem causalidade. Nenhum metodo muda isso. O
que se pode fazer com honestidade e:

  1. **declarar as suposicoes** num DAG, em vez de esconde-las na escolha de
     covariaveis — publicar o DAG vale mais que qualquer numero;
  2. **derivar** dele quais variaveis ajustar (criterio de backdoor) e, mais
     importante, quais **nao** ajustar (mediador, colisor);
  3. **refutar**: se o efeito sobrevive a placebo, confundidor aleatorio e
     subconjunto, e robusto *dentro das suposicoes do DAG* — e so isso;
  4. **quantificar a fragilidade** com o **E-value** (VanderWeele & Ding, 2017):
     quao forte teria de ser um confundidor **nao medido** para anular o efeito.

O E-value e o unico numero desta pagina que nao depende do DAG estar certo. Ele
mede o quanto de confundimento residual seria necessario — o leitor julga se
isso e plausivel.

A pergunta escolhida
--------------------
**Atividade fisica reduz o risco de diabetes?**

E a melhor pergunta disponivel porque `docs/07` §2.1 mostrou que o efeito
aparente **desaparece** ao entrar `saude_geral` (OR 0,852 -> 0,988), e a leitura
depende inteiramente de `saude_geral` ser mediador ou colisor. O DAG resolve a
ambiguidade — declarando a suposicao, nao provando-a.

O DAG declarado
---------------
    idade, sexo, raca, renda, escolaridade   -> confundidores (afetam os dois)
    IMC                                       -> MEDIADOR (atividade -> IMC -> diabetes)
    saude_geral, dific_caminhar, dias ruins   -> CONSEQUENCIA do diabetes
    hipertensao, colesterol                   -> MEDIADOR (sindrome metabolica)

Consequencias imediatas e nao obvias:
  * ajustar por IMC estima o **efeito direto**, nao o total — e o efeito total e
    o que interessa a saude publica;
  * ajustar por `saude_geral` **abre vies de colisor** e por isso M2/M3 de
    `docs/07` nao devem ser lidos como causais.

Uso:
    python -m diabetes.causal.dag
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from diabetes.pipeline.estado import registrar

ENTRADA = Path("data/processed/gold/brfss_expandido.parquet")
SEED = 42

TRATAMENTO = "_TOTINDA"        # 1 = praticou atividade fisica · 2 = nao
DESFECHO = "diabetes"

#: o DAG, declarado. Cada papel muda o que se pode ajustar.
PAPEIS = {
    "confundidor": ["_AGE80", "SEX", "_RACEGR3", "INCOME2", "EDUCA", "EMPLOY1"],
    "mediador": ["_BMI5", "_RFHYPE5", "TOLDHI2"],
    "consequencia": ["GENHLTH", "DIFFWALK", "PHYSHLTH", "QLACTLM2"],
    "proxy_de_deteccao": ["CHOLCHK", "HLTHPLN1", "CHECKUP1"],
}

DAG_TEXTO = """
digraph {
  idade -> atividade;  idade -> diabetes;
  sexo -> atividade;   sexo -> diabetes;
  raca -> atividade;   raca -> diabetes;
  renda -> atividade;  renda -> diabetes;
  escolaridade -> atividade; escolaridade -> diabetes;
  emprego -> atividade; emprego -> diabetes;

  atividade -> imc;    imc -> diabetes;                 // mediador
  atividade -> hipertensao; hipertensao -> diabetes;    // mediador
  atividade -> diabetes;                                // efeito direto

  diabetes -> saude_geral;                              // consequencia
  diabetes -> dificuldade_caminhar;
  diabetes -> dias_ruins;
  atividade -> saude_geral;                             // -> COLISOR
}
"""


# --------------------------------------------------------------------------

def _preparar(df: pd.DataFrame, ajustes: list[str]) -> tuple:
    cols = [TRATAMENTO, DESFECHO, "_LLCPWT", *ajustes]
    d = df[cols].dropna()
    t = (d[TRATAMENTO] == 1).astype(int).to_numpy()        # 1 = fez atividade
    y = d[DESFECHO].astype(int).to_numpy()
    w = d["_LLCPWT"].astype(float).to_numpy()
    X = d[ajustes].astype(float) if ajustes else pd.DataFrame(index=d.index)
    return t, y, w, X


def efeito(df: pd.DataFrame, ajustes: list[str], rotulo: str) -> dict:
    """OR do tratamento sobre o desfecho, ajustado pelo conjunto dado."""
    t, y, w, X = _preparar(df, ajustes)
    M = sm.add_constant(pd.concat(
        [pd.Series(t, index=X.index, name="atividade"), X], axis=1))
    ww = w * (len(w) / w.sum())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = sm.GLM(y, M, family=sm.families.Binomial(), freq_weights=ww).fit()
    ic = r.conf_int()
    out = {
        "conjunto": rotulo, "n": int(len(y)), "n_ajustes": len(ajustes),
        "or": round(float(np.exp(r.params["atividade"])), 4),
        "ic95": [round(float(np.exp(ic.loc["atividade", 0])), 4),
                 round(float(np.exp(ic.loc["atividade", 1])), 4)],
    }
    print(f"    {rotulo:44} OR {out['or']:.4f}  IC {out['ic95']}  (n={out['n']:,})")
    return out


# --------------------------------------------------------------------------
# E-value
# --------------------------------------------------------------------------

def e_value(or_: float, limite: float | None = None) -> dict:
    """VanderWeele & Ding (2017), aproximacao para desfecho raro via risco relativo.

    E = RR + sqrt(RR*(RR-1)), com RR o efeito na direcao protetora invertido.
    Le-se: um confundidor nao medido precisaria estar associado ao tratamento E
    ao desfecho por um risco relativo de pelo menos E, ALEM de tudo que ja foi
    ajustado, para explicar o efeito observado.
    """
    def _e(x: float) -> float:
        x = 1 / x if x < 1 else x
        return x + np.sqrt(x * (x - 1))

    saida = {"e_value_estimativa": round(float(_e(or_)), 3)}
    if limite is not None:
        # E-value do limite do IC mais proximo do nulo: se o IC cruza 1, e 1
        cruza = (or_ < 1 and limite >= 1) or (or_ > 1 and limite <= 1)
        saida["e_value_ic"] = 1.0 if cruza else round(float(_e(limite)), 3)
    return saida


# --------------------------------------------------------------------------
# refutacao
# --------------------------------------------------------------------------

def refutar(df: pd.DataFrame, ajustes: list[str], or_obs: float) -> list[dict]:
    """Tres testes. Sobreviver a eles nao prova causa — falhar prova que nao e."""
    rng = np.random.default_rng(SEED)
    t, y, w, X = _preparar(df, ajustes)
    testes = []

    def ajusta(tt, yy, XX, ww) -> float:
        """Reajusta o mesmo GLM logistico e devolve so o OR do tratamento.

        Fechada sobre nada: recebe tudo por parametro justamente para que os tres
        testes de refutacao troquem uma peca de cada vez (tratamento embaralhado,
        covariavel de ruido, subamostra) sem tocar no resto da especificacao. O peso
        entra reescalado para media 1 — `freq_weights` cru leria `_LLCPWT` como
        contagem e produziria erro-padrao de uma amostra de 250 milhoes.
        """
        M = sm.add_constant(pd.concat(
            [pd.Series(tt, index=XX.index, name="atividade"), XX], axis=1))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = sm.GLM(yy, M, family=sm.families.Binomial(),
                       freq_weights=ww * (len(ww) / ww.sum())).fit()
        return float(np.exp(r.params["atividade"]))

    # 1 · placebo: embaralha o tratamento. O efeito TEM de sumir.
    or_p = ajusta(rng.permutation(t), y, X, w)
    testes.append({
        "teste": "placebo (tratamento embaralhado)",
        "or_esperado": 1.0, "or_obtido": round(or_p, 4),
        "passou": bool(abs(or_p - 1) < 0.03),
        "leitura": "se o efeito sobrevive ao placebo, o modelo esta capturando ruido",
    })

    # 2 · confundidor aleatorio: acrescenta ruido. O efeito NAO pode mudar.
    Xr = X.copy()
    Xr["_ruido"] = rng.normal(size=len(X))
    or_r = ajusta(t, y, Xr, w)
    testes.append({
        "teste": "confundidor aleatorio acrescentado",
        "or_esperado": round(or_obs, 4), "or_obtido": round(or_r, 4),
        "passou": bool(abs(or_r - or_obs) / or_obs < 0.02),
        "leitura": "sensibilidade a covariavel irrelevante indica especificacao instavel",
    })

    # 3 · subconjunto aleatorio: metade dos dados. O efeito deve se manter.
    sub = rng.random(len(t)) < 0.5
    or_s = ajusta(t[sub], y[sub], X[sub], w[sub])
    testes.append({
        "teste": "subconjunto aleatorio (50%)",
        "or_esperado": round(or_obs, 4), "or_obtido": round(or_s, 4),
        "passou": bool(abs(or_s - or_obs) / or_obs < 0.10),
        "leitura": "instabilidade em subamostra indica dependencia de poucas observacoes",
    })
    return testes


def main() -> None:
    """Roda a camada causal (backdoor, refutacao, E-value) e grava `gold/_causal.json`."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entrada", type=Path, default=ENTRADA)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_causal.json"))
    args = ap.parse_args()

    df = pd.read_parquet(args.entrada)
    registrar("causal", "inicio", n=len(df))
    print("  pergunta: atividade fisica reduz o risco de diabetes?")
    print(f"  DAG declarado com {sum(len(v) for v in PAPEIS.values())} variaveis "
          f"em {len(PAPEIS)} papeis\n")

    print("  [1] o que o DAG manda ajustar — e o que ele PROIBE")
    conj = {
        "sem ajuste (associacao bruta)": [],
        "BACKDOOR — so confundidores": PAPEIS["confundidor"],
        "+ mediadores (efeito DIRETO, nao total)":
            PAPEIS["confundidor"] + PAPEIS["mediador"],
        "+ consequencias (COLISOR — invalido)":
            PAPEIS["confundidor"] + PAPEIS["mediador"] + PAPEIS["consequencia"],
    }
    efeitos = [efeito(df, cols, rot) for rot, cols in conj.items()]

    principal = efeitos[1]     # backdoor: o unico que estima efeito total
    print(f"\n    -> estimativa causal (efeito TOTAL, sob o DAG): "
          f"OR {principal['or']:.4f} {principal['ic95']}")

    print("\n  [2] refutacao")
    ref = refutar(df, PAPEIS["confundidor"], principal["or"])
    for t in ref:
        print(f"    {'PASSOU' if t['passou'] else 'FALHOU':7} {t['teste']:38} "
              f"OR {t['or_obtido']:.4f} (esperado {t['or_esperado']})")

    print("\n  [3] E-value — quao forte teria de ser um confundidor nao medido?")
    ev = e_value(principal["or"], max(principal["ic95"]))
    print(f"    E-value da estimativa : {ev['e_value_estimativa']}")
    print(f"    E-value do limite do IC: {ev['e_value_ic']}")
    print(f"    Leitura: um confundidor nao medido precisaria de RR >= "
          f"{ev['e_value_estimativa']} com o tratamento E com o desfecho,")
    print("             alem de tudo que ja foi ajustado, para anular o efeito.")

    print("\n  [4] escala de referencia — E-value de efeitos conhecidos nesta base")
    escala = []
    for var, nome in (("_RFHYPE5", "hipertensao"), ("_BMI5", "IMC")):
        d = df[[var, DESFECHO, "_LLCPWT", *PAPEIS["confundidor"]]].dropna()
        x = (d[var] == 2).astype(float) if var == "_RFHYPE5" else d[var] / 100 / 5
        M = sm.add_constant(pd.concat(
            [x.rename("x"), d[PAPEIS["confundidor"]].astype(float)], axis=1))
        ww = d["_LLCPWT"].astype(float).to_numpy()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = sm.GLM(d[DESFECHO].astype(int), M, family=sm.families.Binomial(),
                       freq_weights=ww * (len(ww) / ww.sum())).fit()
        o = float(np.exp(r.params["x"]))
        e = e_value(o)["e_value_estimativa"]
        escala.append({"fator": nome, "or": round(o, 3), "e_value": e})
        print(f"    {nome:14} OR {o:.3f}  ->  E-value {e}")

    saida = {
        "pergunta": "atividade fisica reduz o risco de diabetes?",
        "dag": DAG_TEXTO.strip(), "papeis": PAPEIS,
        "efeitos_por_conjunto": efeitos,
        "estimativa_causal_efeito_total": principal,
        "refutacao": ref,
        "e_value": ev,
        "escala_de_referencia": escala,
        "ressalva": ("dados transversais: o resultado e 'efeito sob as suposicoes "
                     "do DAG', nunca 'causa'. O E-value e o unico numero que nao "
                     "depende do DAG estar certo."),
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("causal", "fim")


if __name__ == "__main__":
    main()
