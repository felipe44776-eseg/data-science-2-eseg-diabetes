"""Testes das cinco frentes de expansao (docs/10 a docs/14).

As invariantes cobertas aqui sao as que, se quebrarem, produzem numero errado
sem erro visivel:
  * vazamento no conjunto expandido (variavel derivada do proprio diagnostico)
  * raking que nao casa a margem
  * Elkan-Noto que devolve probabilidade fora de [0,1]
  * conforme que nao entrega a cobertura prometida
  * DiD que estima o coeficiente errado num experimento sintetico
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from diabetes.external.medicaid import (
    CONTROLES,
    ESCALONADOS,
    TRATADOS,
    poder_do_desenho,
)
from diabetes.external.pesos import _ee_taylor, raking
from diabetes.features.expandido import (
    ACESSO_E_DETECCAO,
    BLOCOS,
    DETECCAO,
    ORIGINAIS,
    RISCO,
    SENSIVEIS,
    TODAS,
    VAZAMENTO,
    _limpar_codigos,
)
from diabetes.models.glassbox import EBM_VARS, MONOTONICAS, conforme_mondrian
from diabetes.models.pu import estimar_c_bbe, scar, scar_ponderado

GOLD = Path("data/processed/gold")


# --- frente 1: conjunto expandido -----------------------------------------

def test_nenhuma_variavel_de_vazamento_no_conjunto():
    """A protecao mais importante: nada derivado do proprio diagnostico."""
    for c in TODAS + ORIGINAIS:
        assert not VAZAMENTO.match(c), c


def test_blocos_nao_se_sobrepoem():
    vistos: set[str] = set()
    for nome, d in BLOCOS.items():
        assert not (vistos & set(d)), f"{nome} repete variavel de outro bloco"
        vistos |= set(d)


def test_risco_e_deteccao_sao_disjuntos():
    assert not set(RISCO) & set(DETECCAO)
    assert set(DETECCAO) == set(ACESSO_E_DETECCAO)
    assert set(RISCO) | set(DETECCAO) == set(TODAS)


def test_raca_esta_no_conjunto_e_nos_sensiveis():
    """A omissao que `docs/10` corrigiu nao pode voltar."""
    assert "_RACEGR3" in RISCO
    assert "_RACEGR3" in SENSIVEIS


def test_codigo_de_nao_resposta_vira_nan():
    s = pd.Series([1.0, 2.0, 7.0, 9.0])
    assert _limpar_codigos(s, "SMOKE100").isna().sum() == 2


def test_dias_ruins_recodifica_88_para_zero():
    s = pd.Series([5.0, 88.0, 77.0, 99.0])
    r = _limpar_codigos(s, "MENTHLTH")
    assert r.iloc[1] == 0 and r.isna().sum() == 2


def test_continua_nao_perde_valor_valido():
    """`_AGE80` = 9 e nove anos de idade seria invalido, mas 79 nao pode virar NaN."""
    s = pd.Series([25.0, 79.0, 80.0])
    assert _limpar_codigos(s, "_AGE80").notna().all()


# --- frente 5: raking e variancia -----------------------------------------

def test_raking_casa_a_margem():
    rng = np.random.default_rng(0)
    n = 4000
    cats = pd.DataFrame({"a": rng.integers(1, 4, n).astype(float),
                         "b": rng.integers(1, 3, n).astype(float)})
    alvo = {"a": pd.Series({1.0: 0.5, 2.0: 0.3, 3.0: 0.2}),
            "b": pd.Series({1.0: 0.7, 2.0: 0.3})}
    w, hist = raking(cats, alvo, ["a", "b"])
    for v in ("a", "b"):
        obt = pd.Series(w).groupby(cats[v]).sum()
        obt /= obt.sum()
        assert (obt - alvo[v].reindex(obt.index)).abs().max() < 1e-4, v
    assert hist[-1] < hist[0]


def test_raking_com_alvo_igual_ao_observado_nao_move_peso():
    rng = np.random.default_rng(1)
    c = pd.DataFrame({"a": rng.integers(1, 4, 3000).astype(float)})
    alvo = {"a": c["a"].value_counts(normalize=True)}
    w, _ = raking(c, alvo, ["a"])
    assert np.allclose(w, 1.0, atol=1e-6)


def test_taylor_bate_o_ep_binomial_sem_estrato():
    """Com um estrato, um PSU por linha e peso uniforme, Taylor = binomial."""
    rng = np.random.default_rng(2)
    n = 5000
    y = rng.integers(0, 2, n).astype(float)
    w = np.ones(n)
    ee_t = _ee_taylor(y, w, np.ones(n), np.arange(n))
    p = y.mean()
    ee_b = np.sqrt(p * (1 - p) / n)
    assert ee_t == pytest.approx(ee_b, rel=0.02)


def test_taylor_cresce_com_agrupamento():
    """Correlacao dentro do PSU tem de aumentar o erro-padrao."""
    rng = np.random.default_rng(3)
    psu = np.repeat(np.arange(200), 25)
    base = rng.integers(0, 2, 200)
    y = np.repeat(base, 25).astype(float)           # correlacao perfeita no PSU
    w = np.ones(len(y))
    agrupado = _ee_taylor(y, w, np.ones(len(y)), psu)
    independente = _ee_taylor(y, w, np.ones(len(y)), np.arange(len(y)))
    assert agrupado > 3 * independente


# --- frente 2: PU ---------------------------------------------------------

def test_scar_reescala_e_limita_em_um():
    p = np.array([0.1, 0.5, 0.9])
    r = scar(p, 0.724)
    assert (r >= p).all() and r.max() <= 1.0


def test_scar_com_c_igual_a_um_nao_muda_nada():
    p = np.array([0.1, 0.4, 0.8])
    assert np.allclose(scar(p, 1.0), p)


def test_peso_de_elkan_noto_e_um_nos_rotulados():
    p = np.array([0.2, 0.6])
    s = np.array([1, 0])
    w = scar_ponderado(p, s, 0.724)
    assert w[0] == 1.0 and 0.0 <= w[1] <= 1.0


def test_bbe_recupera_c_em_dado_sintetico():
    """Constroi um PU com c conhecido e verifica se o BBE o encontra."""
    rng = np.random.default_rng(4)
    n, c = 40_000, 0.70
    y = rng.random(n) < 0.15
    p_s = np.where(y, rng.beta(8, 2, n), rng.beta(2, 8, n))  # escore separa bem
    s = y & (rng.random(n) < c)
    est = estimar_c_bbe(p_s, s.astype(int))["c_estimado_bbe"]
    assert abs(est - c) < 0.12, est


# --- frente 3: conforme e monotonicidade ----------------------------------

def test_conforme_entrega_a_cobertura_prometida():
    rng = np.random.default_rng(5)
    n = 30_000
    y = (rng.random(n) < 0.2).astype(int)
    p = np.clip(y * 0.45 + rng.normal(0.25, 0.15, n), 0.001, 0.999)
    meio = n // 2
    for alfa in (0.05, 0.10, 0.20):
        cj = conforme_mondrian(p[:meio], y[:meio], p[meio:], alfa)
        for cls, inc in ((0, cj["inclui0"]), (1, cj["inclui1"])):
            m = y[meio:] == cls
            assert inc[m].mean() >= 1 - alfa - 0.02, (alfa, cls, inc[m].mean())


def test_conforme_mais_exigente_gera_conjunto_maior():
    rng = np.random.default_rng(6)
    n = 20_000
    y = (rng.random(n) < 0.2).astype(int)
    p = np.clip(y * 0.4 + rng.normal(0.3, 0.2, n), 0.001, 0.999)
    meio = n // 2
    t = [conforme_mondrian(p[:meio], y[:meio], p[meio:], a)["tamanho"].mean()
         for a in (0.05, 0.20)]
    assert t[0] > t[1]


def test_idade_nao_tem_restricao_de_monotonicidade():
    """`docs/06` mediu queda em 80+ — impor monotonicidade seria impor erro."""
    assert "_AGE80" not in MONOTONICAS
    assert MONOTONICAS["_BMI5"] == 1


def test_ebm_usa_subconjunto_legivel():
    assert len(EBM_VARS) <= 15
    assert set(EBM_VARS) <= set(TODAS)


# --- frente 4: DiD --------------------------------------------------------

def test_grupos_do_medicaid_sao_disjuntos():
    assert not TRATADOS & CONTROLES
    assert not TRATADOS & ESCALONADOS
    assert not CONTROLES & ESCALONADOS
    assert "WI" in ESCALONADOS, "Wisconsin nao e controle limpo (waiver de 2014)"


def test_poder_detecta_desenho_subdimensionado():
    r = [{"desfecho": "cobertura", "efeito_pp": 3.11},
         {"desfecho": "diabetes", "efeito_pp": -0.4, "ee": 0.32,
          "media_pre_tratados": 13.48}]
    p = poder_do_desenho(r)
    assert p["diferenca_minima_detectavel_pp"] > p["efeito_MAXIMO_esperado_sobre_diagnostico_pp"]
    assert "NAO tem poder" in p["veredito"]


def test_poder_reconhece_desenho_adequado():
    r = [{"desfecho": "cobertura", "efeito_pp": 40.0},
         {"desfecho": "diabetes", "efeito_pp": 1.0, "ee": 0.02,
          "media_pre_tratados": 13.48}]
    assert "tem poder" in poder_do_desenho(r)["veredito"]


# --- resultados reais (pulados se ausentes) -------------------------------

@pytest.mark.skipif(not (GOLD / "_frente1_expandido.json").exists(),
                    reason="frente 1 nao executada")
def test_frente1_ganho_e_o_documentado():
    d = json.loads((GOLD / "_frente1_expandido.json").read_text(encoding="utf-8"))
    assert d["comparacao"]["ganho_pr_auc_%"] > 5
    aud = {a["grupo"]: a for a in d["auditoria_raca"]}
    # o achado central: o ganho e das minorias
    assert aud["negro nao-hispanico"]["ganho_recall"] > 0.05
    assert aud["branco nao-hispanico"]["ganho_recall"] < 0.02


@pytest.mark.skipif(not (GOLD / "_frente2_pu.json").exists(),
                    reason="frente 2 nao executada")
def test_bbe_concorda_com_o_nhanes():
    d = json.loads((GOLD / "_frente2_pu.json").read_text(encoding="utf-8"))
    assert abs(d["bbe"]["c_estimado_bbe"] - d["premissa"]["c_nhanes"]) < 0.05


@pytest.mark.skipif(not (GOLD / "_frente3_glassbox.json").exists(),
                    reason="frente 3 nao executada")
def test_monotonicidade_custa_pouco():
    d = json.loads((GOLD / "_frente3_glassbox.json").read_text(encoding="utf-8"))
    assert d["monotonicidade"]["custo_pr_auc_%"] < 2.0


@pytest.mark.skipif(not (GOLD / "_frente5_pesos.json").exists(),
                    reason="frente 5 nao executada")
def test_pesos_removem_a_maior_parte_do_vies():
    d = json.loads((GOLD / "_frente5_pesos.json").read_text(encoding="utf-8"))
    assert d["correcao_de_vies"]["vies_removido_%"] > 60
    assert d["variante_com_acesso"]["vies_removido_%"] > 90
