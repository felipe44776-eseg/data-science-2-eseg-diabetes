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


# --- publicacao (site + GitHub Pages) ---------------------------------------

SITE = Path("reports/site/index.html")
ESCORE = Path("data/processed/gold/_trilhaC_escore.json")
WORKFLOW_PAGES = Path(".github/workflows/pages.yml")


def test_toda_funcao_publica_tem_docstring():
    """Regressao: 52% das funcoes publicas estavam sem docstring.

    Nao e estetica. Modulo sem docstring obriga quem for continuar o trabalho a
    reconstruir a intencao a partir do codigo — e foi assim que a formulacao SAR
    passou a medir 'nao foi testado' em vez de 'alto risco e nao testado'.
    """
    import ast

    sem = [f"{p}:{n.name}"
           for p in Path("src").rglob("*.py")
           for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
           and not n.name.startswith("_")
           and not ast.get_docstring(n)]
    assert not sem, f"sem docstring: {sem}"


def test_workflow_de_pages_publica_o_que_o_pipeline_produz():
    """O que o workflow copia tem de ser saida declarada de alguma etapa.

    Se o caminho no YAML e o caminho em `ETAPAS` divergirem, o deploy publica
    silenciosamente a versao antiga — ou quebra so no CI.
    """
    from diabetes.pipeline.estado import ETAPAS

    yml = WORKFLOW_PAGES.read_text(encoding="utf-8")
    produzidas = {s for e in ETAPAS for s in e.saidas}
    for caminho in ("reports/site/index.html", "reports/produto/index.html",
                    "reports/deck/apresentacao.html"):
        assert caminho in yml, f"{caminho} nao e publicado pelo workflow"
        assert caminho in produzidas, f"{caminho} nao e saida de nenhuma etapa"


def test_etapa_site_existe_e_depende_do_produto():
    """A pagina de entrada cita metricas do escore e do produto — se nao
    depender deles, `status` nao a marca OBSOLETA quando eles mudarem."""
    from diabetes.pipeline.estado import ETAPAS

    site = next(e for e in ETAPAS if e.chave == "site")
    assert "reports/produto/modelo.json" in site.entradas
    assert "data/processed/gold/_trilhaC_escore.json" in site.entradas
    assert site.saidas == ("reports/site/index.html",)


@pytest.mark.skipif(not SITE.exists(), reason="site nao gerado")
def test_site_liga_para_os_tres_entregaveis():
    html = SITE.read_text(encoding="utf-8")
    for destino in ('href="calculadora/"', 'href="deck/"', 'href="figuras/"'):
        assert destino in html, destino
    assert "não é orientação clínica" in html, "falta o aviso de escopo"


@pytest.mark.skipif(not SITE.exists() or not ESCORE.exists(),
                    reason="site ou trilha C nao executados")
def test_site_publica_os_numeros_do_artefato():
    """Numero na pagina tem de vir do JSON, nao da memoria de quem escreveu.

    A versao anterior deste teste fixava "0,804" e "0,7663" — ou seja, cometia
    exatamente o erro que deveria impedir, e quebrou assim que a auditoria mudou os
    numeros. Agora ele le o artefato e confere que a pagina o reflete.
    """
    html = SITE.read_text(encoding="utf-8")
    esc = json.loads(ESCORE.read_text(encoding="utf-8"))
    b = esc["escores"]["B_sem_proxy_acesso"]["metricas"]
    vs = esc["comparacao"]["vs_findrisc"]

    def ptbr(x: float, casas: int) -> str:
        return f"{x:.{casas}f}".replace(".", ",")

    # o valor de manchete e o da amostra propria, nao o da amostra comum
    assert ptbr(b["roc_auc_amostra_propria"], 3) in html
    assert ptbr(vs["findrisc_roc"], 4) in html
    assert ptbr(vs["ganho_milesimos"], 1) in html
    # e a ressalva de que o FINDRISC comparado nao e o completo
    assert f"{esc['findrisc']['itens_disponiveis']} dos" in html
    assert str(esc["findrisc"]["itens_originais"]) in html


def test_escore_de_papel_recusa_formulario_em_branco():
    """Sem guarda, o escore de papel MENTE para quem nao preencheu nada.

    Em JS, `null < 35` e verdadeiro (null vira 0), `null/100` da 0 e `null == 2` da
    false — entao um formulario vazio somava 0 pontos e a pagina exibia a faixa de
    MENOR risco como se fosse resposta. O Python nunca teve o problema porque
    `eval/escore.py` exige `notna()`; a pagina e o que o usuario ve.

    Achado da auditoria adversarial, camada trilhac/produto.
    """
    assert "if (l._AGE80   == null) faltando.push" in JS
    for var in ("_BMI5", "GENHLTH", "_RFHYPE5", "SEX"):
        assert f"l.{var}" in JS and "faltando.push" in JS, var
    assert "if (faltando.length) return {pontos: null, faixa: null, faltando};" in JS
    # o render tem de tratar o caso, nao so a funcao
    assert 'const completo = e.faixa != null;' in JS
    assert '$("#pontos").textContent = completo ? e.pontos : "—";' in JS


# --- pagina do metodo -------------------------------------------------------

METODO = Path("reports/metodo/index.html")


def test_matriz_de_confusao_e_coerente():
    """As quatro celulas tem de fechar, e o limiar NAO pode ser 0,5.

    Com 14% de prevalencia, cortar em 0,5 joga quase todo mundo na coluna negativa
    e a acuracia fica otima — exatamente o que o ADR 0005 proibe. O limiar sai da
    especificidade, e este teste trava isso.
    """
    import numpy as np

    from diabetes.produto.metodo import ESPECIFICIDADE, matriz_de_confusao

    rng = np.random.default_rng(3)
    n = 40_000
    y = (rng.uniform(size=n) < 0.14).astype(int)
    p = np.clip(rng.normal(0.3 + 0.25 * y, 0.15), 0, 1)
    m = matriz_de_confusao(y, p)

    assert m["vp"] + m["fp"] + m["fn"] + m["vn"] == n
    assert m["vp"] + m["fn"] == int(y.sum())
    assert abs(m["especificidade"] - ESPECIFICIDADE) < 0.01
    assert m["recall"] == pytest.approx(m["vp"] / (m["vp"] + m["fn"]), abs=1e-4)
    assert m["precisao"] == pytest.approx(m["vp"] / (m["vp"] + m["fp"]), abs=1e-4)
    # com prevalencia baixa o limiar operacional fica bem abaixo de 0,5
    assert m["limiar"] < 0.5


@pytest.mark.skipif(not METODO.exists(), reason="pagina do metodo nao gerada")
def test_pagina_do_metodo_tem_as_etapas_e_os_graficos():
    """Cada etapa precisa do grafico que sustenta a decisao — nao e ilustracao."""
    html = METODO.read_text(encoding="utf-8")
    # 15 etapas do metodo + a secao de referencia (glossario)
    assert html.count('<section class="etapa"') == 16
    assert html.count("<figure>") >= 8
    for termo in ("Matriz de confusão", "precision-recall", "Calibração",
                  "Curva de decisão", "parcimônia", "Equidade"):
        assert termo in html, termo
    # toda figura vem legendada com a decisao que embasa
    assert html.count("A decisão que este gráfico sustenta") >= 8
    assert 'href="../"' in html, "falta o caminho de volta"


@pytest.mark.skipif(not METODO.exists(), reason="pagina do metodo nao gerada")
def test_svgs_do_metodo_sao_bem_formados():
    """SVG quebrado nao aparece como erro: aparece como espaco em branco."""
    import re
    import xml.etree.ElementTree as ET

    html = METODO.read_text(encoding="utf-8")
    svgs = re.findall(r"<svg.*?</svg>", html, re.S)
    assert len(svgs) >= 8
    for s in svgs:
        ET.fromstring(s)  # levanta se mal formado


def test_grafico_nao_desenha_serie_toda_zerada():
    """Chave errada num artefato produz gráfico plausível e vazio, sem erro nenhum.

    Aconteceu: `g_equidade` lia "tpr"/"ppv" enquanto o artefato grava
    "recall_tpr"/"precisao_ppv", e o `.get(k) or 0` desenhava cinco barras zeradas.
    O SVG era válido, a página abria, e todos os grupos apareciam com 0,0%.
    """
    import json
    import re

    from diabetes.produto.metodo import g_equidade

    caminho = Path("data/processed/gold/_trilhaC_equidade.json")
    if not caminho.exists():
        pytest.skip("trilha C nao executada")
    grupos = json.loads(caminho.read_text(encoding="utf-8"))["observado"]["raca"]["por_grupo"]
    svg = g_equidade(grupos)
    valores = re.findall(r">(\d+,\d)%<", svg)
    assert valores, "nenhum valor rotulado no gráfico"
    assert any(v != "0,0" for v in valores), f"série inteira zerada: {valores}"

    # e chave ausente tem de FALHAR, nao virar zero
    with pytest.raises(KeyError):
        g_equidade([{"grupo": "x", "n": 1000}])


EXECUTIVO = Path("reports/executivo/index.html")


@pytest.mark.skipif(not EXECUTIVO.exists(), reason="executivo nao gerado")
def test_apresentacao_executiva_segue_o_arco_combinado():
    """base -> gradientes -> matriz de confusão -> parcimônia -> calculadora."""
    html = EXECUTIVO.read_text(encoding="utf-8")
    assert 10 <= html.count('class="slide') <= 13, "cerca de 11 slides"
    for marco in ("achamos a base de verdade", "Onde a prevalência dispara",
                  "Matriz de confusão", "parcimônia", "calculadora"):
        assert marco in html, marco
    # a ordem importa: e o arco que o publico executivo segue
    pos = [html.find(m) for m in ("achamos a base de verdade",
                                  "Onde a prevalência dispara",
                                  "Matriz de confusão",
                                  "Curva de parcimônia",
                                  "calculadora que qualquer um abre")]
    assert pos == sorted(pos), f"slides fora de ordem: {pos}"


@pytest.mark.skipif(not EXECUTIVO.exists(), reason="executivo nao gerado")
def test_executiva_nao_apresenta_marcador_de_acesso_como_fator_de_risco():
    """Invariante 8, na superfície de maior risco de ser mal lida.

    "Já fez exame de colesterol" tem o maior OR da base (7,11) e NAO e fator de
    risco — e marcador de quem foi ao medico. Num slide executivo, mostrar o
    ranking sem esse contraste inverteria a conclusao do trabalho.
    """
    html = EXECUTIVO.read_text(encoding="utf-8")
    assert "marcador de acesso ao médico" in html, "falta a legenda que separa os dois"
    assert "não é um fator de risco" in html
    assert "aparece como saudável" in html


@pytest.mark.skipif(not EXECUTIVO.exists(), reason="executivo nao gerado")
def test_faixas_de_idade_do_brfss_estao_certas():
    """`_AGEG5YR` nivel 1 = 18-24, depois 5 em 5 a partir de 25.

    A formula ingenua `18 + 5*(k-1)` erra a partir do nivel 3 e rotulava a faixa
    30-34 como "28+". Rotulo de eixo errado num slide executivo e numero errado.
    """
    html = EXECUTIVO.read_text(encoding="utf-8")
    for faixa in ("18+", "30+", "40+", "50+", "60+", "70+"):
        assert f">{faixa}<" in html, faixa
    assert ">28+<" not in html and ">38+<" not in html


def test_tabela_2x2_do_glossario_fecha():
    """A aritmética do OR tem de bater com a tabela que a página mostra.

    O glossário existe para quem quiser conferir a conta. Se as células e o OR
    publicado divergirem, a página ensina errado — pior que não ensinar.
    """
    from diabetes.produto.metodo import tabela_2x2

    if not Path("data/processed/gold/brfss_expandido.parquet").exists():
        pytest.skip("parquet expandido ausente")
    t = tabela_2x2()

    # OR = (a·d)/(b·c), e tambem a razao entre as duas chances
    assert t["or"] == pytest.approx(t["a"] * t["d"] / (t["b"] * t["c"]), rel=1e-9)
    assert t["or"] == pytest.approx(t["chance1"] / t["chance0"], rel=1e-9)
    # RR e razao de PROBABILIDADES, e com desfecho comum fica abaixo do OR
    assert t["rr"] == pytest.approx((t["p1"] / 100) / (t["p0"] / 100), rel=1e-9)
    assert t["rr"] < t["or"], "com desfecho comum o OR exagera em relação ao RR"
    assert 6.0 < t["or"] < 8.0, t["or"]


@pytest.mark.skipif(not METODO.exists(), reason="pagina do metodo nao gerada")
def test_glossario_publica_formula_e_numero():
    """Cada verbete precisa da fórmula E do valor real — um sem o outro não ensina."""
    html = METODO.read_text(encoding="utf-8")
    assert 'id="glossario"' in html
    for termo in ("Razão de chances", "Risco relativo", "Regressão logística",
                  "PR-AUC", "ECE", "DEFF", "E-value", "Lift"):
        assert termo in html, termo
    # MathML nativo, sem biblioteca externa (a pagina tem de ser autocontida)
    assert html.count("<math") >= 10
    assert "<mfrac>" in html and "MathJax" not in html and "katex" not in html.lower()
    # todo verbete traz o numero medido, nao so a formula
    assert html.count("No projeto:") >= 8


@pytest.mark.skipif(not METODO.exists(), reason="pagina do metodo nao gerada")
def test_glossario_usa_separador_ptbr():
    """`.replace(",", ".")` global no milhar come a vírgula decimal.

    Foi assim que o OR saiu como "6.9998" em vez de "6,9998" — o mesmo defeito que
    `deck.num` já documenta desde a primeira vez que aconteceu.
    """
    import re

    html = METODO.read_text(encoding="utf-8")
    trecho = html[html.find('id="glossario"'):]
    texto = re.sub(r"<[^>]+>", " ", trecho)
    # decimal com ponto e 1-2 casas nao existe em pt-BR; milhar tem sempre 3
    suspeitos = [x for x in re.findall(r"\d+\.\d+", texto)
                 if len(x.split(".")[1]) != 3]
    assert not suspeitos, f"decimal com ponto: {suspeitos[:5]}"
