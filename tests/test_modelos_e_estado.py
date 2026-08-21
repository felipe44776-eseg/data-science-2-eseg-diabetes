"""Testes das metricas de avaliacao, do estado do pipeline e das figuras.

Foco nas invariantes que, se quebrarem, produzem resultado errado em silencio:
  * `recall_em_especificidade` tem de ser monotona no limiar
  * o ECE tem de detectar descalibracao (foi ele que provou o ADR 0004)
  * o `status` do pipeline tem de marcar OBSOLETO quando a entrada e mais nova
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from diabetes.models.escada import (
    REGRA_CLINICA,
    SEM_ACESSO,
    avaliar,
    curva_calibracao,
    erro_calibracao,
    recall_em_especificidade,
    teto_de_bayes,
)
from diabetes.pipeline.estado import ETAPAS, inspecionar, proxima_etapa, status
from diabetes.schema import PROXIES_DE_ACESSO, TARGET
from diabetes.viz.tema import Escala, barra_h, barra_v, legenda, svg

ESCADA_JSON = Path("data/processed/gold/_escada_modelos.json")
BINACIONAL = Path("data/external/vigitel/_comparacao_binacional.json")


# --- metricas -------------------------------------------------------------

def test_recall_e_um_com_separacao_perfeita():
    y = np.array([0] * 100 + [1] * 100)
    p = np.concatenate([np.linspace(0, 0.4, 100), np.linspace(0.6, 1, 100)])
    assert recall_em_especificidade(y, p, 0.90) == pytest.approx(1.0)


def test_recall_cai_quando_a_especificidade_sobe():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 4000)
    p = np.clip(y * 0.3 + rng.normal(0.4, 0.2, 4000), 0, 1)
    assert (recall_em_especificidade(y, p, 0.80)
            >= recall_em_especificidade(y, p, 0.95))


def test_ece_zero_para_modelo_calibrado():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.05, 0.95, 60_000)
    y = (rng.uniform(size=60_000) < p).astype(int)  # calibrado por construcao
    assert erro_calibracao(y, p) < 0.02


def test_ece_detecta_descalibracao():
    """O que separou o modelo com class_weight do calibrado (`docs/08` §3)."""
    rng = np.random.default_rng(2)
    p = rng.uniform(0.05, 0.95, 60_000)
    y = (rng.uniform(size=60_000) < p).astype(int)
    inflado = np.clip(p * 2.5, 0, 1)  # ordena igual, probabilidade errada
    assert erro_calibracao(y, inflado) > 10 * erro_calibracao(y, p)


def test_curva_calibracao_soma_o_total():
    rng = np.random.default_rng(3)
    p = rng.uniform(0, 1, 5000)
    y = (rng.uniform(size=5000) < p).astype(int)
    assert sum(f["n"] for f in curva_calibracao(y, p)) == 5000


def test_avaliar_devolve_as_metricas_do_adr_0005():
    rng = np.random.default_rng(4)
    y = rng.integers(0, 2, 2000)
    p = rng.uniform(0, 1, 2000)
    m = avaliar(y, p)
    for k in ("pr_auc", "roc_auc", "recall_esp90", "brier", "ece"):
        assert k in m
    assert "acuracia" not in m, "acuracia nao e reportada (ADR 0005)"


def test_teto_de_bayes_e_um_sem_conflito():
    df = pd.DataFrame({"a": [0, 1, 0, 1], "b": [0, 0, 1, 1], TARGET: [0, 2, 0, 2]})
    assert teto_de_bayes(df, ["a", "b"])["acerto_maximo_ponderado"] == pytest.approx(1.0)


def test_teto_de_bayes_cai_com_rotulo_conflitante():
    df = pd.DataFrame({"a": [0, 0, 0, 0], "b": [0, 0, 0, 0], TARGET: [0, 0, 2, 2]})
    t = teto_de_bayes(df, ["a", "b"])
    assert t["acerto_maximo_ponderado"] == pytest.approx(0.5)
    assert t["linhas_em_grupo_conflitante"] == 4


def test_bloco_sem_acesso_exclui_os_proxies():
    assert not set(SEM_ACESSO) & set(PROXIES_DE_ACESSO)
    assert len(REGRA_CLINICA) == 3


# --- estado do pipeline ---------------------------------------------------

def test_etapas_tem_chave_unica():
    chaves = [e.chave for e in ETAPAS]
    assert len(chaves) == len(set(chaves))


def test_toda_etapa_declara_entrada_e_saida():
    for e in ETAPAS:
        assert e.entradas and e.saidas, e.chave
        assert e.comando, e.chave


def test_saida_de_uma_etapa_alimenta_a_seguinte():
    """O DAG tem de ser conexo: nenhuma etapa orfa depois da ingestao."""
    produzidas = set()
    for e in ETAPAS:
        if e.chave != "ingest" and not e.opcional:
            externas = {c for c in e.entradas if not c.startswith("src/")}
            assert externas & produzidas or e.chave == "external", e.chave
        produzidas |= set(e.saidas)


def test_status_marca_ausente(tmp_path: Path):
    linhas = status(raiz=tmp_path)
    assert {ln["estado"] for ln in linhas} == {"ausente"}
    assert proxima_etapa(linhas) is None, "sem entradas, nada e acionavel"


def test_status_marca_obsoleto_quando_a_entrada_e_mais_nova(tmp_path: Path):
    e = ETAPAS[0]
    for c in (*e.entradas, *e.saidas):
        p = tmp_path / c
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    time.sleep(0.02)
    (tmp_path / e.entradas[0]).write_text("y")  # entrada tocada depois da saida
    ln = next(x for x in status(raiz=tmp_path) if x["chave"] == e.chave)
    assert ln["estado"] == "obsoleto"


def test_inspecionar_devolve_hash_estavel(tmp_path: Path):
    p = tmp_path / "a.txt"
    p.write_text("conteudo")
    a = inspecionar("a.txt", tmp_path)
    assert a["existe"] and a["hash"].startswith("sha256:")
    assert inspecionar("a.txt", tmp_path)["hash"] == a["hash"]
    p.write_text("outro")
    assert inspecionar("a.txt", tmp_path)["hash"] != a["hash"]


# --- figuras --------------------------------------------------------------

def test_escala_mapeia_dominio_em_pixels():
    s = Escala(0, 10, 100, 200)
    assert s(0) == 100 and s(10) == 200 and s(5) == 150


def test_escala_degenerada_nao_divide_por_zero():
    assert Escala(5, 5, 0, 100)(5) == 0


def test_barras_ancoram_na_base():
    """Ponta arredondada, base reta — a barra nunca 'flutua' (marks-and-anatomy)."""
    assert barra_h(10, 20, 50, 18, "#000").startswith('<path d="M10.0,20.0')
    assert 'fill="#000"' in barra_v(10, 20, 30, 40, "#000")


def test_legenda_existe_para_duas_series():
    saida = legenda(0, 0, [("a", "#111"), ("b", "#222")])
    assert saida.count("<circle") == 2 and ">a<" in saida and ">b<" in saida


def test_svg_tem_tema_e_rotulo_acessivel():
    s = svg(100, 50, "", "titulo do grafico")
    assert 'role="img"' in s and 'aria-label="titulo do grafico"' in s
    assert "prefers-color-scheme: dark" in s
    assert 'fill="var(--superficie)"' in s


# --- resultados reais (pulados se ausentes) -------------------------------

@pytest.mark.skipif(not ESCADA_JSON.exists(), reason="escada nao executada")
def test_gradient_boosting_bate_a_regra_clinica():
    """Criterio minimo de `docs/02` B1 — sem isto, nao ha projeto."""
    r = json.loads(ESCADA_JSON.read_text(encoding="utf-8"))
    m = r["sem_proxies_de_acesso"]["modelos"]
    assert (m["5_gb_calibrado"]["holdout"]["pr_auc"]
            > m["1_regra_clinica"]["holdout"]["pr_auc"])
    assert m["1_regra_clinica"]["holdout"]["pr_auc"] > m["0_prevalencia"]["holdout"]["pr_auc"]


@pytest.mark.skipif(not ESCADA_JSON.exists(), reason="escada nao executada")
def test_calibracao_reduz_o_ece_em_ordem_de_grandeza():
    """Regressao do achado que sustenta o ADR 0004."""
    m = json.loads(ESCADA_JSON.read_text(encoding="utf-8"))["sem_proxies_de_acesso"]["modelos"]
    assert (m["4_gradient_boosting"]["holdout"]["ece"]
            > 10 * m["5_gb_calibrado"]["holdout"]["ece"])


@pytest.mark.skipif(not BINACIONAL.exists(), reason="comparacao binacional nao executada")
def test_hipertensao_e_idade_replicam_entre_paises():
    """Achado central de `docs/09`: os fatores robustos transferem."""
    o = json.loads(BINACIONAL.read_text(encoding="utf-8"))["odds_ratio"]
    for v in ("hipertensao", "idade_faixa"):
        assert o[v]["mesma_direcao"] and o[v]["ic_sobrepoe"], v
        assert 0.9 <= o[v]["razao_BR_EUA"] <= 1.1, v
