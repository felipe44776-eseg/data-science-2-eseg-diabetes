"""Frente 5 — inferencia de amostra complexa e pesos para o arquivo entregue.

Duas entregas distintas:

  A. **Inferencia correta.** Substituir nossa aproximacao de Kish por variancia
     de amostra complexa com `_STSTR` (estrato) e `_PSU`, via linearizacao de
     Taylor (`samplics`). Promove todo IC do projeto de "ordem de grandeza certa"
     para "correto".

  B. **Pesos publicaveis.** Calcular, por raking, um vetor de pesos que torne o
     arquivo de 253.680 linhas aproximadamente nao-enviesado para as margens
     populacionais. E o subproduto reutilizavel: quem usar o CSV do Kaggle passa
     a poder estimar prevalencia sem o vies de 32,7% medido em `docs/05`.

Por que raking e nao pos-estratificacao simples: a tabela cruzada completa de
idade x sexo x raca x escolaridade x renda tem celulas vazias em 253 mil linhas.
O raking (*iterative proportional fitting*) casa as **margens** uma a uma ate
convergir, o que e estavel com celula rala e e exatamente o metodo que o proprio
CDC usa para construir `_LLCPWT`.

Uso:
    python -m diabetes.external.pesos
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from diabetes.eda.associacao import n_efetivo_kish
from diabetes.pipeline.estado import registrar

EXPANDIDO = Path("data/processed/gold/brfss_expandido.parquet")
SILVER = Path("data/processed/diabetes_silver.parquet")

#: margens usadas no raking. Escolhidas por serem (a) as que governaram a exclusao
#: de 42,5% da amostra e (b) as que mais deslocam a prevalencia de diabetes.
MARGENS = ["idade_g", "sexo", "raca_g", "escolaridade_g", "renda_g"]

#: margem de ACESSO. Fica separada porque o trade-off e severo: fecha mais vies,
#: mas exige que os 3,7% do arquivo que nao fizeram exame de colesterol
#: representem 25,5% da populacao. Ver `docs/11` §4.
MARGEM_ACESSO = "exame_g"

LIMITE_PESO = 8.0   # aparo de peso extremo, em multiplos da media


# --------------------------------------------------------------------------
# A. inferencia de amostra complexa
# --------------------------------------------------------------------------

def prevalencia_por_metodo(df: pd.DataFrame) -> pd.DataFrame:
    """Compara tres niveis de rigor no IC da mesma estimativa pontual."""
    d = df[["diabetes", "_LLCPWT", "_STSTR", "_PSU"]].dropna()
    y = d["diabetes"].to_numpy(float)
    w = d["_LLCPWT"].to_numpy(float)
    p = float(np.average(y, weights=w))
    linhas = []

    # (1) ingenuo: amostra aleatoria simples, ignora peso e desenho
    ee = np.sqrt(y.mean() * (1 - y.mean()) / len(y))
    linhas.append({"metodo": "1 · aleatoria simples (ignora peso e desenho)",
                   "prevalencia_%": round(y.mean() * 100, 3),
                   "ee_%": round(ee * 100, 4),
                   "ic95": f"[{(y.mean() - 1.96 * ee) * 100:.2f}; {(y.mean() + 1.96 * ee) * 100:.2f}]",
                   "n_efetivo": len(y)})

    # (2) nossa aproximacao ate aqui: ponto ponderado, variancia pelo n efetivo de Kish
    n_ef = n_efetivo_kish(d["_LLCPWT"])
    ee = np.sqrt(p * (1 - p) / n_ef)
    linhas.append({"metodo": "2 · ponderado + n efetivo de Kish (nossa aproximacao)",
                   "prevalencia_%": round(p * 100, 3),
                   "ee_%": round(ee * 100, 4),
                   "ic95": f"[{(p - 1.96 * ee) * 100:.2f}; {(p + 1.96 * ee) * 100:.2f}]",
                   "n_efetivo": round(n_ef)})

    # (3) correto: linearizacao de Taylor com estrato e PSU
    ee_t = _ee_taylor(y, w, d["_STSTR"].to_numpy(), d["_PSU"].to_numpy())
    linhas.append({"metodo": "3 · Taylor com _STSTR e _PSU (correto)",
                   "prevalencia_%": round(p * 100, 3),
                   "ee_%": round(ee_t * 100, 4),
                   "ic95": f"[{(p - 1.96 * ee_t) * 100:.2f}; {(p + 1.96 * ee_t) * 100:.2f}]",
                   "n_efetivo": round(p * (1 - p) / ee_t**2)})
    return pd.DataFrame(linhas)


def _ee_taylor(y: np.ndarray, w: np.ndarray, estrato: np.ndarray,
               psu: np.ndarray) -> float:
    """Erro-padrao de uma razao (media ponderada) sob amostragem estratificada.

    Linearizacao de Taylor: a media ponderada e uma razao, cuja variancia se
    estima pelo residuo z = w(y - p), agregado por PSU dentro de estrato.
    """
    p = np.average(y, weights=w)
    z = w * (y - p)
    total_w = w.sum()

    var = 0.0
    d = pd.DataFrame({"z": z, "estrato": estrato, "psu": psu})
    for _, g in d.groupby("estrato", sort=False):
        por_psu = g.groupby("psu", sort=False)["z"].sum().to_numpy()
        n = len(por_psu)
        if n < 2:            # estrato com um unico PSU nao contribui variancia
            continue
        var += n / (n - 1) * ((por_psu - por_psu.mean()) ** 2).sum()
    return float(np.sqrt(var) / total_w)


# --------------------------------------------------------------------------
# B. pesos por raking para o arquivo entregue
# --------------------------------------------------------------------------

def _categorizar(df: pd.DataFrame, fonte: str) -> pd.DataFrame:
    """Grupos comuns as duas bases. Nomes iguais, codificacao igual."""
    out = pd.DataFrame(index=df.index)
    if fonte == "brfss":
        idade, sexo = df["_AGE80"], df["SEX"]
        raca, esc, renda = df["_RACEGR3"], df["EDUCA"], df["INCOME2"]
    else:  # arquivo entregue (silver)
        idade, sexo = df["idade_anos"], (df["sexo"] == 1).map({True: 1, False: 2})
        raca = pd.Series(np.nan, index=df.index)   # nao existe no arquivo entregue
        esc, renda = df["escolaridade"], df["renda_faixa"]
    out["idade_g"] = pd.cut(idade.astype(float),
                            [0, 34, 44, 54, 64, 74, 200], labels=[1, 2, 3, 4, 5, 6])
    out["sexo"] = sexo.astype(float)
    out["raca_g"] = raca.astype(float)
    out["escolaridade_g"] = pd.cut(esc.astype(float), [0, 3, 4, 5, 6],
                                   labels=[1, 2, 3, 4])
    out["renda_g"] = pd.cut(renda.astype(float), [0, 3, 5, 6, 7, 8],
                            labels=[1, 2, 3, 4, 5])
    # margem de acesso: exame de colesterol nos ultimos 5 anos
    if fonte == "brfss":
        out["exame_g"] = (df["CHOLCHK"] == 1).astype(float).where(df["CHOLCHK"].notna())
    else:
        out["exame_g"] = df["exame_colesterol"].astype(float)
    return out


def margens_alvo(brfss: pd.DataFrame, cats: pd.DataFrame,
                 variaveis: list[str]) -> dict[str, pd.Series]:
    """Proporcao populacional de cada margem, estimada com `_LLCPWT`."""
    w = brfss["_LLCPWT"].astype(float)
    alvo = {}
    for v in variaveis:
        m = cats[v].notna()
        s = pd.DataFrame({"c": cats.loc[m, v].astype(float), "w": w[m]}) \
            .groupby("c")["w"].sum()
        alvo[v] = s / s.sum()
    return alvo


def raking(cats: pd.DataFrame, alvo: dict[str, pd.Series], variaveis: list[str],
           iteracoes: int = 300, tol: float = 1e-8) -> tuple[np.ndarray, list[float]]:
    """Iterative proportional fitting. Devolve pesos e o historico de convergencia."""
    w = np.ones(len(cats), dtype=float)
    historico = []
    codigos = {v: cats[v].astype(float).to_numpy() for v in variaveis}
    for _ in range(iteracoes):
        for v in variaveis:
            c = codigos[v]
            valido = ~np.isnan(c)
            atual = pd.Series(w[valido]).groupby(c[valido]).sum()
            atual = atual / atual.sum()
            mapa = (alvo[v] / atual).reindex(atual.index).fillna(1.0).to_dict()
            w[valido] *= np.array([mapa.get(x, 1.0) for x in c[valido]])
        w *= len(w) / w.sum()                 # normaliza para media 1
        # desvio medido DEPOIS do passe completo, senao o criterio de parada
        # avalia um estado que ja foi corrigido
        maior_desvio = 0.0
        for v in variaveis:
            c = codigos[v]
            valido = ~np.isnan(c)
            atual = pd.Series(w[valido]).groupby(c[valido]).sum()
            atual = atual / atual.sum()
            maior_desvio = max(maior_desvio,
                               float((atual - alvo[v].reindex(atual.index)).abs().max()))
        historico.append(maior_desvio)
        if maior_desvio < tol:
            break
    # apara peso extremo: peso muito grande inflaria a variancia sem ganho de vies
    w = np.clip(w, 1 / LIMITE_PESO, LIMITE_PESO)
    w *= len(w) / w.sum()
    return w, historico


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--expandido", type=Path, default=EXPANDIDO)
    ap.add_argument("--silver", type=Path, default=SILVER)
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/_frente5_pesos.json"))
    ap.add_argument("--pesos", type=Path,
                    default=Path("data/processed/gold/pesos_arquivo_entregue.parquet"))
    args = ap.parse_args()

    registrar("frente5", "inicio")
    brfss = pd.read_parquet(args.expandido)
    silver = pd.read_parquet(args.silver)

    print("  [A] inferencia de amostra complexa…")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tab = prevalencia_por_metodo(brfss)
    print(tab.to_string(index=False))

    print("\n  [B] raking do arquivo entregue…")
    cat_br = _categorizar(brfss, "brfss")
    cat_si = _categorizar(silver, "silver")
    # raca nao existe no arquivo entregue: o raking usa as margens disponiveis
    variaveis = [v for v in MARGENS if cat_si[v].notna().any()]
    print(f"    margens utilizaveis: {variaveis}")
    alvo = margens_alvo(brfss, cat_br, variaveis)
    w, hist = raking(cat_si, alvo, variaveis)
    print(f"    convergiu em {len(hist)} iteracoes · desvio final {hist[-1]:.2e}")
    print(f"    peso: min {w.min():.3f}  mediana {np.median(w):.3f}  max {w.max():.3f}")
    print(f"    n efetivo apos raking: {n_efetivo_kish(pd.Series(w)):,.0f} de {len(w):,}")

    # o teste: o peso corrige a prevalencia?
    y = (silver["diabetes"] == 2).to_numpy(float)
    ref = float(np.average(brfss["diabetes"], weights=brfss["_LLCPWT"]))
    antes, depois = float(y.mean()), float(np.average(y, weights=w))
    print(f"\n    prevalencia no arquivo entregue, SEM peso : {antes*100:.3f}%")
    print(f"    prevalencia no arquivo entregue, COM peso : {depois*100:.3f}%")
    print(f"    referencia populacional (BRFSS ponderado)  : {ref*100:.3f}%")
    print(f"    vies antes {(antes-ref)*100:+.3f} p.p.  ->  depois {(depois-ref)*100:+.3f} p.p.  "
          f"({(1-abs(depois-ref)/abs(antes-ref))*100:.1f}% do vies removido)")

    # validacao cruzada das margens: casaram?
    conferencia = []
    for v in variaveis:
        m = cat_si[v].notna().to_numpy()
        obt = pd.Series(w[m]).groupby(cat_si[v].astype(float)[m].to_numpy()).sum()
        obt = obt / obt.sum()
        conferencia.append({"margem": v,
                            "desvio_max_pp": round(float(
                                (obt - alvo[v].reindex(obt.index)).abs().max() * 100), 4)})

    # --- variante com margem de acesso -------------------------------------
    print("\n  [C] variante com margem de ACESSO...")
    v_ac = [*variaveis, MARGEM_ACESSO]
    alvo_ac = margens_alvo(brfss, cat_br, v_ac)
    w_ac, hist_ac = raking(cat_si, alvo_ac, v_ac)
    p_ac = float(np.average(y, weights=w_ac))
    ne_ac = float(n_efetivo_kish(pd.Series(w_ac)))
    print(f"    prevalencia {p_ac*100:.3f}%  vies {(p_ac-ref)*100:+.3f} p.p.  "
          f"({(1-abs(p_ac-ref)/abs(antes-ref))*100:.1f}% removido)")
    print(f"    CUSTO: n efetivo {ne_ac:,.0f} (DEFF {len(w_ac)/ne_ac:.2f})  "
          f"razao de pesos {w_ac.max()/w_ac.min():.0f}:1")

    # --- curva do aparo de peso: vies contra variancia ----------------------
    global LIMITE_PESO
    curva = []
    original = LIMITE_PESO
    for lim in (3.0, 5.0, 8.0, 15.0, 1e9):
        LIMITE_PESO = lim
        wl, _ = raking(cat_si, alvo, variaveis)
        pl = float(np.average(y, weights=wl))
        nel = float(n_efetivo_kish(pd.Series(wl)))
        curva.append({"aparo": "sem" if lim > 1e8 else lim,
                      "prevalencia_%": round(pl * 100, 3),
                      "vies_pp": round((pl - ref) * 100, 3),
                      "n_efetivo": round(nel),
                      "deff": round(len(wl) / nel, 2)})
    LIMITE_PESO = original

    pd.DataFrame({"peso_demografico": w, "peso_com_acesso": w_ac})         .to_parquet(args.pesos, index=False)
    saida = {
        "inferencia_complexa": tab.to_dict("records"),
        "raking": {
            "margens": variaveis,
            "iteracoes": len(hist),
            "desvio_final": hist[-1],
            "limite_de_aparo": LIMITE_PESO,
            "peso_min": round(float(w.min()), 4),
            "peso_mediana": round(float(np.median(w)), 4),
            "peso_max": round(float(w.max()), 4),
            "n_efetivo": round(float(n_efetivo_kish(pd.Series(w)))),
            "deff_do_peso": round(len(w) / float(n_efetivo_kish(pd.Series(w))), 3),
            "conferencia_margens": conferencia,
        },
        "correcao_de_vies": {
            "referencia_populacional_%": round(ref * 100, 3),
            "arquivo_sem_peso_%": round(antes * 100, 3),
            "arquivo_com_peso_%": round(depois * 100, 3),
            "vies_antes_pp": round((antes - ref) * 100, 3),
            "vies_depois_pp": round((depois - ref) * 100, 3),
            "vies_removido_%": round((1 - abs(depois - ref) / abs(antes - ref)) * 100, 1),
        },
        "variante_com_acesso": {
            "margens": v_ac,
            "prevalencia_%": round(p_ac * 100, 3),
            "vies_pp": round((p_ac - ref) * 100, 3),
            "vies_removido_%": round((1 - abs(p_ac - ref) / abs(antes - ref)) * 100, 1),
            "n_efetivo": round(ne_ac),
            "deff": round(len(w_ac) / ne_ac, 2),
            "razao_de_pesos": round(float(w_ac.max() / w_ac.min())),
            "aviso": ("exige que os 3,7% do arquivo sem exame de colesterol representem "
                      "25,5% da populacao; dobra o efeito de desenho"),
        },
        "curva_de_aparo": curva,
        "arquivo_de_pesos": str(args.pesos),
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")
    registrar("frente5", "fim")
    print("\n    conferencia das margens (desvio maximo, pontos percentuais):")
    print(pd.DataFrame(conferencia).to_string(index=False))


if __name__ == "__main__":
    main()
