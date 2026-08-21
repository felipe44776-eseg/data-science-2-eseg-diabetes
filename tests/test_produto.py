"""Testes do produto — o entregavel da apresentacao.

O teste central delega para `tests/paridade_js.mjs`: e o **mesmo JavaScript**
que roda na pagina, conferido contra 500 predicoes do sklearn. Se divergir, o
numero mostrado ao vivo nao e o numero do modelo validado — e nada no HTML
denuncia isso.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from diabetes.produto.exportar import (
    LIMITE_FINITO,
    PERGUNTAS,
    _finitizar,
    _indice,
    prever_do_json,
)
from diabetes.produto.pagina import JS, verificar_js

PRODUTO = Path("reports/produto")
MODELO = PRODUTO / "modelo.json"
CASOS = PRODUTO / "_casos_paridade.json"
PAGINA = PRODUTO / "index.html"


# --- serializacao ---------------------------------------------------------

def test_finitizar_troca_infinito():
    r = _finitizar({"a": float("inf"), "b": float("-inf"), "c": [1.0, float("nan")]})
    assert r["a"] == LIMITE_FINITO and r["b"] == -LIMITE_FINITO
    assert r["c"][1] is None


def test_json_do_modelo_e_estrito():
    """`JSON.parse` do navegador rejeita Infinity e NaN — o build tem de rejeitar antes."""
    with pytest.raises(ValueError):
        json.dumps({"x": float("inf")}, allow_nan=False)


# --- indexacao de faixa ---------------------------------------------------

def test_indice_de_ausente_e_zero():
    assert _indice(None, [1.0, 2.0]) == 0
    assert _indice(float("nan"), [1.0, 2.0]) == 0


def test_indice_respeita_os_cortes():
    cortes = [10.0, 20.0, 30.0]
    assert _indice(5, cortes) == 1
    assert _indice(10, cortes) == 2      # o corte pertence a faixa de cima
    assert _indice(25, cortes) == 3
    assert _indice(99, cortes) == 4


# --- formulario -----------------------------------------------------------

def test_toda_pergunta_tem_rotulo_em_portugues():
    for q in PERGUNTAS:
        assert q["rotulo"] and q["var"]
        assert q["tipo"] in ("numero", "opcoes", "imc")


def test_colesterol_aceita_nao_sei():
    """A pergunta que exige exame previo precisa de saida para quem nunca fez."""
    q = next(x for x in PERGUNTAS if x["var"] == "TOLDHI2")
    assert any(v is None for v, _ in q["opcoes"])


def test_raca_e_renda_sao_opcionais():
    for var in ("_RACEGR3", "INCOME2"):
        q = next(x for x in PERGUNTAS if x["var"] == var)
        assert any(v is None for v, _ in q["opcoes"]), var


# --- javascript -----------------------------------------------------------

def test_javascript_tem_sintaxe_valida():
    verificar_js(JS)


@pytest.mark.skipif(not (MODELO.exists() and CASOS.exists()),
                    reason="produto nao exportado")
@pytest.mark.skipif(shutil.which("node") is None, reason="node ausente")
def test_paridade_python_javascript():
    """O JavaScript da pagina calcula o mesmo que o sklearn."""
    r = subprocess.run(["node", "tests/paridade_js.mjs"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "APROVADO" in r.stdout


# --- modelo exportado -----------------------------------------------------

@pytest.mark.skipif(not MODELO.exists(), reason="produto nao exportado")
def test_modelo_reproduz_predicao_conhecida():
    modelo = json.loads(MODELO.read_text(encoding="utf-8"))
    casos = json.loads(CASOS.read_text(encoding="utf-8"))["casos"]
    for caso in casos[:50]:
        p, _ = prever_do_json(modelo["ebm"], caso["entrada"])
        assert abs(p - caso["p_python"]) < 1e-12


@pytest.mark.skipif(not MODELO.exists(), reason="produto nao exportado")
def test_modelo_registra_a_paridade_do_export():
    m = json.loads(MODELO.read_text(encoding="utf-8"))
    assert m["paridade_export"]["aprovado"]
    assert m["paridade_export"]["erro_max"] < 1e-9


@pytest.mark.skipif(not PAGINA.exists(), reason="pagina nao construida")
def test_pagina_e_autocontida():
    """Sem requisicao externa: tem de abrir por duplo clique, offline."""
    html = PAGINA.read_text(encoding="utf-8")
    assert "src=" not in html.replace('src="data:', ""), "script externo na pagina"
    assert "https://" not in html.split("<footer>")[0], "recurso remoto no corpo"
    assert "const MODELO=" in html, "modelo nao embutido"
    assert "não é um diagnóstico" in html, "aviso clinico ausente"


# --- notebooks ------------------------------------------------------------

NOTEBOOKS_DIR = Path("notebooks")


def test_notebooks_sao_gerados_de_src():
    """Regra 7: notebook mostra resultado, nao contem logica."""
    from diabetes.produto.notebooks import NOTEBOOKS

    assert len(NOTEBOOKS) >= 6
    for nome, celulas in NOTEBOOKS.items():
        codigo = "\n".join("".join(c["source"]) for c in celulas
                           if c["cell_type"] == "code")
        # o notebook nao pode reimplementar analise: nada de treinar modelo,
        # particionar ou definir classe. Ler artefato e importar de src/, sim.
        for proibido in (".fit(", "train_test_split", "sklearn", "\nclass "):
            assert proibido not in codigo, f"{nome} contem logica: {proibido!r}"
        assert celulas[0]["cell_type"] == "markdown", f"{nome} nao abre com contexto"


def test_linhas_do_notebook_terminam_com_quebra():
    """Sem o \n cada linha, o codigo vira uma linha so ao carregar."""
    from diabetes.produto.notebooks import _linhas

    ls = _linhas("import os\nimport sys")
    assert ls[0].endswith("\n")
    assert "".join(ls) == "import os\nimport sys\n"


@pytest.mark.skipif(not NOTEBOOKS_DIR.exists() or
                    not list(NOTEBOOKS_DIR.glob("*.ipynb")),
                    reason="notebooks nao gerados")
def test_notebooks_versionados_tem_saida():
    """Notebook sem saida obriga cada pessoa a rodar tudo antes de ler."""
    for nb in sorted(NOTEBOOKS_DIR.glob("*.ipynb")):
        dados = json.loads(nb.read_text(encoding="utf-8"))
        saidas = [o for c in dados["cells"] for o in c.get("outputs", [])]
        assert saidas, f"{nb.name} versionado sem saida"
        erros = [o for o in saidas if o.get("output_type") == "error"]
        assert not erros, f"{nb.name} tem celula com erro: {erros[0].get('ename')}"
