"""Testes das medidas de associacao e da inferencia ponderada.

O ponto critico coberto aqui: **peso amostral nao pode inflar a precisao**.
Uma tabela ponderada soma a populacao dos EUA (~250 milhoes); se o erro-padrao
usasse esse total, todo IC teria largura zero e toda conclusao pareceria certa.
`test_peso_nao_estreita_ic` congela essa protecao.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from diabetes.eda.associacao import (
    classificar_v,
    cliff_delta,
    cramer_v,
    deff,
    n_efetivo_kish,
    odds_ratio,
    tabela_2x2,
    tendencia_ordinal,
)

# --- n efetivo e DEFF -----------------------------------------------------

def test_peso_uniforme_nao_perde_eficiencia():
    w = pd.Series(np.ones(1000))
    assert n_efetivo_kish(w) == pytest.approx(1000)
    assert deff(w) == pytest.approx(1.0)


def test_peso_desigual_reduz_n_efetivo():
    w = pd.Series([1.0] * 500 + [10.0] * 500)
    assert n_efetivo_kish(w) < 1000
    assert deff(w) > 1.0


def test_n_efetivo_e_invariante_a_escala():
    """Multiplicar todos os pesos por k nao muda a informacao contida neles."""
    w = pd.Series([1.0, 3.0, 7.0, 2.0])
    assert n_efetivo_kish(w) == pytest.approx(n_efetivo_kish(w * 1000))


# --- tabela e odds ratio --------------------------------------------------

def test_tabela_2x2_sem_peso_conta_linhas():
    e = pd.Series([1, 1, 0, 0, 1])
    d = pd.Series([1, 0, 1, 0, 1])
    assert tabela_2x2(e, d).sum() == 5


def test_tabela_2x2_com_peso_soma_pesos():
    e = pd.Series([1, 0])
    d = pd.Series([1, 0])
    w = pd.Series([10.0, 5.0])
    assert tabela_2x2(e, d, w).sum() == pytest.approx(15.0)


def test_odds_ratio_conhecido():
    # [[a=30, b=70], [c=10, d=90]] -> OR = (30*90)/(70*10) = 3,857
    tab = np.array([[30.0, 70.0], [10.0, 90.0]])
    r = odds_ratio(tab)
    assert r["or"] == pytest.approx(3.857, abs=1e-3)
    assert r["or_ic_baixo"] < r["or"] < r["or_ic_alto"]


def test_odds_ratio_e_um_quando_nao_ha_associacao():
    assert odds_ratio(np.array([[50.0, 50.0], [50.0, 50.0]]))["or"] == pytest.approx(1.0)


def test_odds_ratio_devolve_nan_com_cela_vazia():
    assert np.isnan(odds_ratio(np.array([[10.0, 0.0], [5.0, 5.0]]))["or"])


def test_peso_nao_estreita_ic():
    """Reescalar ao n efetivo mantem o IC honesto mesmo com pesos enormes.

    Sem a reescala, uma tabela cuja soma e a populacao produziria IC de
    largura ~zero -- precisao inventada.
    """
    tab_linhas = np.array([[30.0, 70.0], [10.0, 90.0]])
    tab_pop = tab_linhas * 25_000  # como se os pesos somassem milhoes

    sem = odds_ratio(tab_linhas)
    ingenuo = odds_ratio(tab_pop)                      # sem correcao: IC colapsa
    corrigido = odds_ratio(tab_pop, n_efetivo=200.0)   # com n efetivo

    larg = lambda r: r["or_ic_alto"] - r["or_ic_baixo"]  # noqa: E731
    assert larg(ingenuo) < larg(sem) / 10, "sem correcao o IC colapsaria"
    assert larg(corrigido) > larg(sem), "n efetivo menor -> IC mais largo"
    for r in (sem, ingenuo, corrigido):
        assert r["or"] == pytest.approx(3.857, abs=1e-3), "o ponto estimado nao muda"


# --- V de Cramer ----------------------------------------------------------

def test_cramer_v_zero_sem_associacao():
    assert cramer_v(np.array([[50.0, 50.0], [50.0, 50.0]])) == pytest.approx(0.0, abs=1e-9)


def test_cramer_v_alto_com_associacao_forte():
    assert cramer_v(np.array([[95.0, 5.0], [5.0, 95.0]])) > 0.8


def test_classificar_v_segue_cohen():
    assert classificar_v(0.05) == "desprezivel"
    assert classificar_v(0.20) == "pequeno"
    assert classificar_v(0.40) == "medio"
    assert classificar_v(0.60) == "grande"


# --- delta de Cliff -------------------------------------------------------

def test_cliff_delta_um_quando_grupos_nao_se_sobrepoem():
    a = pd.Series(range(100, 200))
    b = pd.Series(range(0, 100))
    assert cliff_delta(a, b) == pytest.approx(1.0)


def test_cliff_delta_zero_para_grupos_identicos():
    a = pd.Series(range(100))
    assert cliff_delta(a, a.copy()) == pytest.approx(0.0, abs=0.05)


def test_cliff_delta_inverte_com_a_ordem():
    a, b = pd.Series(range(100, 200)), pd.Series(range(0, 100))
    assert cliff_delta(a, b) == pytest.approx(-cliff_delta(b, a))


# --- tendencia ordinal ----------------------------------------------------

def test_tendencia_detecta_gradiente_monotonico():
    nivel, desfecho = [], []
    for k, p in enumerate([0.05, 0.10, 0.20, 0.40], start=1):
        n = 1000
        nivel += [k] * n
        desfecho += [1] * int(n * p) + [0] * (n - int(n * p))
    t = tendencia_ordinal(pd.Series(nivel), pd.Series(desfecho))
    assert t["monotonica"] is True
    assert t["r_tendencia"] > 0.2
    assert t["razao_extremos"] == pytest.approx(8.0, rel=0.05)


def test_tendencia_marca_nao_monotonica():
    """Padrao do gradiente etario real: sobe e cai no ultimo nivel (80+)."""
    nivel, desfecho = [], []
    for k, p in enumerate([0.05, 0.20, 0.40, 0.25], start=1):
        n = 1000
        nivel += [k] * n
        desfecho += [1] * int(n * p) + [0] * (n - int(n * p))
    assert tendencia_ordinal(pd.Series(nivel), pd.Series(desfecho))["monotonica"] is False


def test_tendencia_ponderada_usa_n_efetivo():
    nivel = pd.Series([1] * 500 + [2] * 500)
    desfecho = pd.Series([0] * 400 + [1] * 100 + [0] * 200 + [1] * 300)
    peso = pd.Series([1.0] * 500 + [9.0] * 500)
    t = tendencia_ordinal(nivel, desfecho, peso)
    assert t["n_efetivo"] < 1000
    assert abs(t["z_tendencia"]) < abs(
        tendencia_ordinal(nivel, desfecho)["z_tendencia"]
    ), "peso desigual tem de reduzir a estatistica, nao aumentar"
