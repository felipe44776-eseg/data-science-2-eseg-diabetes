"""Testes das camadas de contrato, limpeza e particionamento.

O teste mais importante do arquivo e `test_particao_nao_vaza_duplicata`: cobre o erro
que este dataset convida a cometer (ADR 0002).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from diabetes.clean.pipeline import limpar
from diabetes.features.split import auditar_vazamento, particionar
from diabetes.schema import ESQUEMA, PTBR_TO_SNAKE, TARGET

SILVER = Path("data/processed/diabetes_silver.parquet")


def _frame_sintetico(n: int = 400, seed: int = 0) -> pd.DataFrame:
    """Gera um frame com nomes pt-BR e valores dentro do dominio declarado."""
    rng = np.random.default_rng(seed)
    dados = {}
    for ptbr, snake in PTBR_TO_SNAKE.items():
        meta = ESQUEMA[snake]
        if meta.dominio is not None:
            dados[ptbr] = rng.choice(meta.dominio, n).astype(float)
        else:
            dados[ptbr] = rng.integers(meta.minimo, meta.maximo + 1, n).astype(float)
    return pd.DataFrame(dados)


# --- contrato -------------------------------------------------------------

def test_esquema_cobre_22_colunas():
    assert len(ESQUEMA) == 22
    assert set(PTBR_TO_SNAKE.values()) == set(ESQUEMA)


def test_dominios_sao_consistentes():
    for nome, meta in ESQUEMA.items():
        if meta.dominio is None:
            assert meta.minimo is not None and meta.maximo is not None, nome
            assert meta.minimo < meta.maximo, nome
        else:
            assert len(meta.dominio) == len(set(meta.dominio)), nome


# --- limpeza --------------------------------------------------------------

def test_limpeza_renomeia_e_reduz_tipo():
    df, _, rel = limpar(_frame_sintetico())
    assert set(ESQUEMA).issubset(df.columns)
    for col in ESQUEMA:
        assert df[col].dtype == "uint8", col
    assert rel["linhas_quarentena"] == 0


def test_limpeza_manda_valor_fora_do_dominio_para_quarentena():
    bruto = _frame_sintetico(100)
    bruto.loc[0, "Saude_Geral"] = 9.0        # dominio e 1..5
    bruto.loc[1, "IMC"] = 500.0              # acima do maximo
    df, quarentena, rel = limpar(bruto)
    assert len(quarentena) == 2
    assert rel["linhas_quarentena"] == 2
    assert len(df) == 98


def test_limpeza_marca_duplicata_sem_remover():
    bruto = _frame_sintetico(50)
    bruto = pd.concat([bruto, bruto.iloc[:10]], ignore_index=True)
    df, _, rel = limpar(bruto)
    assert len(df) == 60, "duplicata nao pode ser removida na limpeza (ADR 0002)"
    assert rel["duplicatas_exatas"] == 10
    assert df["flag_duplicata_exata"].sum() == 10


def test_limpeza_detecta_alvo_conflitante():
    bruto = _frame_sintetico(30)
    gemea = bruto.iloc[[0]].copy()
    gemea[TARGET.capitalize()] = (bruto.loc[0, "Diabetes"] + 1) % 3  # mesmo perfil, alvo outro
    bruto = pd.concat([bruto, gemea], ignore_index=True)
    _, _, rel = limpar(bruto)
    assert rel["grupos_alvo_conflitante"] >= 1


def test_limpeza_e_idempotente():
    bruto = _frame_sintetico(200, seed=7)
    a, _, _ = limpar(bruto.copy())
    b, _, _ = limpar(bruto.copy())
    pd.testing.assert_frame_equal(a, b)


# --- particionamento (o teste que importa) --------------------------------

def test_particao_nao_vaza_duplicata():
    """Nenhum grupo de linhas identicas pode cruzar holdout ou folds."""
    bruto = _frame_sintetico(300, seed=1)
    bruto = pd.concat([bruto, bruto.iloc[:80]], ignore_index=True)  # forca duplicatas
    df, _, _ = limpar(bruto)
    part = particionar(df, n_folds=3)
    auditoria = auditar_vazamento(part)
    assert auditoria["grupos_cruzando_holdout"] == 0
    assert auditoria["grupos_cruzando_folds"] == 0


def test_holdout_tem_tamanho_esperado():
    df, _, _ = limpar(_frame_sintetico(500, seed=3))
    part = particionar(df, n_folds=3, frac_holdout=0.2)
    frac = part["holdout"].mean()
    assert 0.10 < frac < 0.32, f"holdout com fracao inesperada: {frac:.3f}"
    assert (part.loc[part["holdout"], "fold"] == -1).all()


# --- dado real (roda so se a silver existir) ------------------------------

@pytest.mark.skipif(not SILVER.exists(), reason="silver ainda nao gerada")
def test_silver_real_bate_com_o_enunciado():
    df = pd.read_parquet(SILVER)
    assert len(df) == 253_680
    assert df[TARGET].isin([0, 1, 2]).all()
    assert df[list(ESQUEMA)].isna().sum().sum() == 0


# --- integridade da fonte ---------------------------------------------------

def test_conferir_fonte_detecta_pdf_trocado(tmp_path):
    """Gravar o hash da fonte sem comparar prova nada.

    Se o PDF mudar — corrigido pelo professor, download truncado, arquivo trocado —
    a ingestao reprocessava em silencio e sobrescrevia o manifesto com o hash NOVO.
    Todo numero a jusante mudaria e nada avisaria. Este teste trava o detector.
    """
    import json

    from diabetes.ingest.pdf_to_csv import _hash_file, conferir_fonte

    fonte = tmp_path / "fonte.pdf"
    fonte.write_bytes(b"conteudo original")
    manifesto = tmp_path / "_manifest.json"

    # sem manifesto anterior nao ha o que comparar — e isso tem de ser dito
    assert conferir_fonte(fonte, manifesto)["estado"] == "sem-referencia"
    assert conferir_fonte(fonte, None)["estado"] == "sem-referencia"

    manifesto.write_text(json.dumps(
        {"manifest": {"sha256_pdf": _hash_file(fonte), "n_linhas": 10}}),
        encoding="utf-8")
    assert conferir_fonte(fonte, manifesto)["estado"] == "identica"

    fonte.write_bytes(b"conteudo TROCADO")
    r = conferir_fonte(fonte, manifesto)
    assert r["estado"] == "MUDOU"
    assert r["sha256_atual"] != r["sha256_anterior"]

    # manifesto corrompido nao pode ser lido como "identica"
    manifesto.write_text("{ nao e json", encoding="utf-8")
    assert conferir_fonte(fonte, manifesto)["estado"] == "manifesto-ilegivel"


def test_extract_para_se_a_fonte_mudou(tmp_path, monkeypatch):
    """A ingestao tem de FALHAR alto, nao reprocessar em silencio."""
    import json

    from diabetes.ingest import pdf_to_csv

    fonte = tmp_path / "fonte.pdf"
    fonte.write_bytes(b"outro conteudo")
    manifesto = tmp_path / "_manifest.json"
    manifesto.write_text(json.dumps(
        {"manifest": {"sha256_pdf": "0" * 64, "n_linhas": 10}}), encoding="utf-8")

    # nao chega a abrir o PDF: a conferencia vem antes
    with pytest.raises(SystemExit, match="A FONTE MUDOU"):
        pdf_to_csv.extract(fonte, tmp_path / "saida.csv", manifesto)


def test_manifesto_do_repositorio_registra_o_hash_da_fonte():
    """Sem `sha256_pdf` gravado, nao existe referencia contra a qual comparar."""
    import json

    caminho = Path("data/raw/_manifest_ingestao.json")
    if not caminho.exists():
        pytest.skip("ingestao nao executada")
    m = json.loads(caminho.read_text(encoding="utf-8"))["manifest"]
    assert len(m.get("sha256_pdf", "")) == 64, "manifesto sem hash da fonte"
    assert m["n_linhas"] == 253_680
    assert m["paginas"] == 4374


# --- reprodutibilidade ----------------------------------------------------

#: Nome do modulo importado -> nome da distribuicao no PyPI, quando diferem.
DISTRIBUICAO = {
    "fitz": "pymupdf", "sklearn": "scikit-learn", "dice_ml": "dice-ml",
    "imblearn": "imbalanced-learn", "yaml": "pyyaml", "cv2": "opencv-python",
    "PIL": "pillow", "dateutil": "python-dateutil",
}


def _imports_de_terceiros() -> set[str]:
    """Modulos de terceiros importados em `src/`, por AST — nao por regex."""
    import ast
    import sys

    achados: set[str] = set()
    for arquivo in Path("src").rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), str(arquivo))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                achados |= {a.name.split(".")[0] for a in no.names}
            elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
                achados.add(no.module.split(".")[0])
    return {m for m in achados
            if m not in sys.stdlib_module_names and m != "diabetes"}


def test_requirements_declara_tudo_que_o_codigo_importa():
    """Import nao declarado quebra o clone limpo, nunca a maquina de quem escreveu.

    Ja aconteceu com quatro pacotes de uma vez — `interpret` (o modelo do
    produto), `prince`, `nbformat` e `nbclient`. Em todos, `tasks.ps1` falhava
    so na maquina de outra pessoa, que e o pior lugar para descobrir.
    """
    req = Path("requirements.txt").read_text(encoding="utf-8").lower()
    declarados = {linha.split("==")[0].split(">=")[0].strip()
                  for linha in req.splitlines()
                  if linha.strip() and not linha.startswith("#")}

    faltando = sorted(
        DISTRIBUICAO.get(m, m) for m in _imports_de_terceiros()
        if DISTRIBUICAO.get(m, m).lower().replace("_", "-") not in
        {d.replace("_", "-") for d in declarados})
    assert not faltando, f"importado mas nao declarado em requirements.txt: {faltando}"
