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
def test_bbe_declara_se_c_e_identificavel():
    """O teste antigo travava a COINCIDENCIA com o NHANES em vez de valida-la.

    Ele exigia |c_bbe - c_nhanes| < 0,05 sobre um estimador que era `max` de uma
    curva monotonica decrescente — ou seja, a fracao rotulada no topo 100/quantis %,
    funcao crescente e ilimitada de um parametro nao declarado (q=25 da 0,656,
    q=100 da 0,779). O teste passava por causa do default, nao por concordancia.

    O que se exige agora e o que importa: o artefato tem de DIZER se `c` foi
    identificado, e so publicar numero quando houver plato.
    """
    d = json.loads((GOLD / "_frente2_pu.json").read_text(encoding="utf-8"))
    bbe = d["bbe"]
    assert "identificado" in bbe and "sensibilidade" in bbe
    if bbe["identificado"]:
        assert bbe["c_estimado_bbe"] is not None
        assert bbe["espalhamento_na_grade"] <= bbe["tolerancia_plato"]
    else:
        assert bbe["c_estimado_bbe"] is None
        assert bbe["motivo"]


def test_bbe_nao_devolve_numero_sem_plato():
    """Estimativa que depende da resolucao do grid nao e estimativa.

    Caso A — rotulagem concentrada no topo extremo (0,5% das linhas): a fracao no
    topo muda muito conforme o bin, porque o bin maior dilui a regiao rotulada. Nao
    ha plato, e o estimador tem de recusar.
    Caso B — regiao pura larga (10% do topo, c=0,70): ha plato de verdade.
    """
    rng = np.random.default_rng(11)
    n = 400_000
    p = np.linspace(0, 1, n)

    concentrado = np.where(p > 0.995, rng.uniform(size=n) < 0.9,
                           rng.uniform(size=n) < 0.02).astype(int)
    a = estimar_c_bbe(p, concentrado)
    assert a["identificado"] is False, a["sensibilidade"]
    assert a["c_estimado_bbe"] is None and a["motivo"]

    puro = np.where(p > 0.90, rng.uniform(size=n) < 0.70,
                    rng.uniform(size=n) < 0.10).astype(int)
    b = estimar_c_bbe(p, puro)
    assert b["identificado"] is True, b["sensibilidade"]
    assert abs(b["c_estimado_bbe"] - 0.70) < 0.02

def test_monotonicidade_custa_pouco():
    d = json.loads((GOLD / "_frente3_glassbox.json").read_text(encoding="utf-8"))
    assert d["monotonicidade"]["custo_pr_auc_%"] < 2.0


@pytest.mark.skipif(not (GOLD / "_frente5_pesos.json").exists(),
                    reason="frente 5 nao executada")
def test_pesos_removem_a_maior_parte_do_vies():
    d = json.loads((GOLD / "_frente5_pesos.json").read_text(encoding="utf-8"))
    assert d["correcao_de_vies"]["vies_removido_%"] > 60
    assert d["variante_com_acesso"]["vies_removido_%"] > 90


# --- codigos de nao-resposta: o achado #1 da auditoria -----------------------

def test_codigo_7_valido_sobrevive_a_limpeza():
    """`_AGEG5YR` 7/9, `EMPLOY1` 7 e `INCOME2` 7 sao CATEGORIA, nao nao-resposta.

    A mascara generica `{7, 9, 77, 99}` apagava 87.806 pessoas de 50-64 anos,
    129.290 aposentados e 57.166 da faixa de renda 50-75k — em silencio, violando o
    invariante 2. O efeito preditivo era desprezivel; o causal nao: o `dropna()` do
    backdoor passou a excluir os aposentados e o OR de `docs/21` saiu errado.
    """
    from diabetes.features.expandido import NAO_RESPOSTA_PROPRIA, _limpar_codigos

    casos = {
        "_AGEG5YR": ([1, 7, 9, 13, 14], [1, 7, 9, 13]),   # invalido e o 14
        "EMPLOY1":  ([1, 7, 8, 9], [1, 7, 8]),            # 7 = aposentado
        "INCOME2":  ([1, 7, 8, 77, 99], [1, 7, 8]),       # 7 = 50-75k
    }
    for nome, (entrada, sobrevivem) in casos.items():
        out = _limpar_codigos(pd.Series(entrada, dtype="float64"), nome)
        assert sorted(out.dropna().tolist()) == sorted(sobrevivem), nome

    # controle: onde 7/9 sao mesmo nao-resposta, o comportamento nao muda
    assert _limpar_codigos(pd.Series([1.0, 7.0, 9.0]), "EDUCA").dropna().tolist() == [1.0]
    assert set(NAO_RESPOSTA_PROPRIA) == {"_AGEG5YR", "EMPLOY1", "INCOME2"}


def test_regra_de_nao_resposta_nao_e_redigitada():
    """Invariante 1: a regra de `_AGEG5YR` e `INCOME2` vem de `REGRAS`, nao de copia.

    Os dois trilhos do projeto se contradiziam sobre a mesma coluna do mesmo XPT:
    `external/brfss2015.py` escrevia `descartar=(14,)` e `features/expandido.py`
    apagava 7 e 9. Amarrar um ao outro impede que divirjam de novo.
    """
    from diabetes.external.brfss2015 import REGRAS
    from diabetes.features.expandido import NAO_RESPOSTA_PROPRIA

    for r in REGRAS:
        if r.origem in NAO_RESPOSTA_PROPRIA:
            assert set(r.descartar) == NAO_RESPOSTA_PROPRIA[r.origem], r.origem


def test_raking_falha_alto_se_faltar_alvo_para_uma_categoria():
    """`.fillna(1.0)` deixava 17% da amostra sem calibracao, e o IPF nunca convergia.

    `docs/11` chegou a testar a hipotese "convergencia insuficiente" e a declarou
    falsa — era verdadeira, e a causa estava duas camadas acima.
    """
    cats = pd.DataFrame({"g": [1.0, 1.0, 2.0, 3.0]})
    alvo = {"g": pd.Series({1.0: 0.5, 2.0: 0.5})}      # falta a categoria 3
    with pytest.raises(ValueError, match="ausente na margem-alvo"):
        raking(cats, alvo, ["g"], iteracoes=5)
