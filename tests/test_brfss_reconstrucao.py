"""Congela a prova da Etapa 4 de `docs/05-comparacao-brfss-original.md`.

A reconstrucao das 22 colunas a partir do BRFSS 2015 original reproduz o arquivo
entregue pelo professor **celula a celula**. Se este teste quebrar, uma das tres
coisas mudou: as regras de derivacao, a extracao do PDF, ou o arquivo baixado.

Requer o XPT de 1,17 GB, que nao esta no git -- os testes sao pulados sem ele.
As regras em si sao testadas sem o arquivo, com frame sintetico.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from diabetes.external.brfss2015 import COLUNAS_BRFSS, DESENHO, REGRAS, reconstruir
from diabetes.schema import ESQUEMA

XPT = Path("data/external/brfss2015/LLCP2015.XPT")
SILVER = Path("data/processed/diabetes_silver.parquet")
RECONSTRUIDO = Path("data/external/brfss2015/brfss2015_reconstruido.parquet")

N_ORIGINAL = 441_456
N_ANALITICO = 253_680


# --- regras (rodam sempre, sem o XPT) -------------------------------------

def test_regras_cobrem_as_22_colunas():
    assert len(REGRAS) == 22
    assert {r.destino for r in REGRAS} == set(ESQUEMA)


def test_nenhuma_variavel_brfss_repetida():
    assert len(COLUNAS_BRFSS) == len(set(COLUNAS_BRFSS))


def test_recodificacao_nao_colide_com_descarte():
    """Um codigo nao pode ser recodificado e descartado ao mesmo tempo."""
    for r in REGRAS:
        assert not (set(r.recodificar) & set(r.descartar)), r.destino


def test_cascata_registra_toda_exclusao():
    """A soma das exclusoes por etapa tem de fechar com o total."""
    rng = np.random.default_rng(0)
    n = 2_000
    bruto = pd.DataFrame({c: rng.integers(1, 4, n).astype(float) for c in COLUNAS_BRFSS})
    bruto["_BMI5"] = rng.integers(1500, 4000, n).astype(float)
    bruto["_AGEG5YR"] = rng.integers(1, 14, n).astype(float)
    bruto["INCOME2"] = rng.choice([1, 2, 3, 77, 99], n).astype(float)
    bruto["MENTHLTH"] = rng.choice([1, 5, 88, 77], n).astype(float)
    bruto["PHYSHLTH"] = rng.choice([1, 5, 88, 99], n).astype(float)
    for c in DESENHO:
        bruto[c] = 1.0
    bruto.loc[0, "GENHLTH"] = np.nan  # forca uma exclusao por nulo

    out, excluidos, cascata = reconstruir(bruto)
    assert len(out) + len(excluidos) == n
    etapas = [e for e in cascata if e["etapa"] != "final"]
    assert sum(e["excluidos"] for e in etapas) == len(excluidos)
    assert cascata[-1]["restantes"] == len(out)
    assert (excluidos["motivo_exclusao"] != "").all()


# --- dado real (pulado sem o XPT) -----------------------------------------

@pytest.mark.skipif(not RECONSTRUIDO.exists(), reason="BRFSS reconstruido ausente")
def test_reconstrucao_tem_o_tamanho_do_arquivo_entregue():
    rec = pd.read_parquet(RECONSTRUIDO)
    assert len(rec) == N_ANALITICO


@pytest.mark.skipif(
    not (RECONSTRUIDO.exists() and SILVER.exists()),
    reason="requer silver e BRFSS reconstruido",
)
def test_reconstrucao_e_identica_ao_arquivo_do_professor():
    """A prova central: 100% das celulas iguais, na mesma ordem."""
    cols = list(ESQUEMA)
    prof = pd.read_parquet(SILVER)[cols].reset_index(drop=True)
    rec = pd.read_parquet(RECONSTRUIDO)[cols].reset_index(drop=True)
    assert prof.shape == rec.shape == (N_ANALITICO, 22)
    pd.testing.assert_frame_equal(prof, rec, check_dtype=False)


@pytest.mark.skipif(not RECONSTRUIDO.exists(), reason="BRFSS reconstruido ausente")
def test_desenho_amostral_foi_preservado_na_reconstrucao():
    """O que o pre-processamento original jogou fora, nos mantemos."""
    rec = pd.read_parquet(RECONSTRUIDO)
    for c in ["_LLCPWT", "_STSTR", "_PSU"]:
        assert c in rec.columns, c
    assert rec["_LLCPWT"].gt(0).all()


@pytest.mark.skipif(not RECONSTRUIDO.exists(), reason="BRFSS reconstruido ausente")
def test_prevalencia_ponderada_diverge_da_nao_ponderada():
    """Regressao do achado da Etapa 5: o peso muda a prevalencia em ~2,5 p.p."""
    rec = pd.read_parquet(RECONSTRUIDO)
    sem_peso = (rec["diabetes"] == 2).mean() * 100
    com_peso = np.average(rec["diabetes"] == 2, weights=rec["_LLCPWT"]) * 100
    assert abs(sem_peso - 13.933) < 0.01, sem_peso
    assert com_peso < sem_peso - 1.0, (sem_peso, com_peso)
