"""Executa os notebooks e grava as saidas — parte do build, nao passo manual.

Motivo: notebook versionado **sem saida** obriga cada pessoa do grupo a rodar
tudo antes de ler, e notebook com saida **de outra execucao** mostra numero que
nao corresponde ao pipeline atual. Executar no build resolve os dois: o que esta
no git e o que o pipeline calculou.

Falha se qualquer celula levantar excecao — um notebook quebrado nao entra no
repositorio.

Uso:
    python -m diabetes.produto.executar_notebooks
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

SAIDA = Path("notebooks")
TEMPO_LIMITE = 900


def executar(caminho: Path, timeout: int = TEMPO_LIMITE) -> tuple[bool, str]:
    """Executa o notebook no lugar, regrava com as saidas e devolve (ok, motivo).

    Duas formas de falha, e as duas contam: excecao levantada pelo `NotebookClient`
    e celula que terminou com output do tipo `error`. A segunda **nao** levanta
    nada — sem a varredura de `outputs`, um notebook quebrado seria gravado no repo
    com o traceback como saida oficial.

    So regrava se passar nas duas: notebook que falha mantem no disco a ultima
    versao boa, em vez de ficar com saida parcial.
    """
    import nbformat
    from nbclient import NotebookClient

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        nb = nbformat.read(caminho, as_version=4)
        try:
            NotebookClient(nb, timeout=timeout, kernel_name="python3").execute()
        except Exception as e:  # noqa: BLE001 — queremos o motivo, qualquer que seja
            return False, str(e)[:200]
        erros = [o for c in nb.cells for o in c.get("outputs", [])
                 if o.get("output_type") == "error"]
        if erros:
            e = erros[0]
            return False, f"{e.get('ename')}: {str(e.get('evalue'))[:160]}"
        nbformat.write(nb, caminho)
    return True, ""


def main() -> None:
    """Executa todos os notebooks da pasta e falha o build se algum quebrar."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pasta", type=Path, default=SAIDA)
    args = ap.parse_args()

    cadernos = sorted(args.pasta.glob("*.ipynb"))
    if not cadernos:
        raise SystemExit(f"nenhum notebook em {args.pasta}")

    falhas = []
    for nb in cadernos:
        ok, motivo = executar(nb)
        print(f"  {nb.name:46} {'OK' if ok else 'FALHOU — ' + motivo}")
        if not ok:
            falhas.append(nb.name)
    if falhas:
        raise SystemExit(f"notebooks com erro: {', '.join(falhas)}")
    print(f"  {len(cadernos)} notebooks executados e gravados com as saidas")


if __name__ == "__main__":
    main()
