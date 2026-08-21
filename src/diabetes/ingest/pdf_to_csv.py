"""Camada de ingestao: reconstroi o CSV original a partir do PDF entregue pelo professor.

O arquivo `Diabetes-2026.csv.pdf` e um dump tabular do CSV BRFSS2015 renderizado em
paginas landscape (1748x792pt). Cada coluna ocupa uma faixa horizontal fixa e cada
registro uma linha de baseline constante, o que permite reconstrucao deterministica
por coordenadas (nao por ordem de leitura, que nao e garantida em PDF).

Estrategia:
  1. extrai palavras com bounding box (PyMuPDF `get_text("words")`);
  2. agrupa por baseline (y0 arredondado) -> linha logica;
  3. ordena por x0 dentro da linha -> ordem de coluna;
  4. valida cardinalidade (22 tokens/linha) e parseabilidade numerica;
  5. emite CSV bruto + manifesto de integridade (hash, contagens, rejeitados).

Qualquer linha que nao satisfaca a validacao vai para o quarentena, nunca e
silenciosamente descartada.

Uso:
    python -m diabetes.ingest.pdf_to_csv --pdf data/raw/Diabetes-2026.csv.pdf \
        --out data/raw/diabetes_2026_raw.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import fitz  # PyMuPDF

N_COLS = 22
Y_TOL = 2  # pt: tolerancia de baseline para agrupar palavras na mesma linha


def _hash_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _rows_from_page(page) -> list[list[str]]:
    """Reconstroi linhas logicas de uma pagina a partir das bounding boxes."""
    buckets: dict[int, list[tuple[float, str]]] = defaultdict(list)
    for x0, y0, _x1, _y1, word, *_ in page.get_text("words"):
        buckets[round(y0 / Y_TOL)].append((x0, word))
    rows = []
    for key in sorted(buckets):
        rows.append([w for _x, w in sorted(buckets[key])])
    return rows


def extract(pdf_path: Path, out_csv: Path, manifest_path: Path | None = None) -> dict:
    doc = fitz.open(pdf_path)
    header: list[str] | None = None
    n_rows = 0
    quarantine: list[dict] = []
    t0 = time.time()

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=";")
        for pno, page in enumerate(doc, start=1):
            for lno, row in enumerate(_rows_from_page(page), start=1):
                if not row:
                    continue
                # cabecalho: primeira linha nao numerica encontrada
                if header is None and not row[0].replace(".", "", 1).isdigit():
                    if len(row) != N_COLS:
                        raise ValueError(
                            f"cabecalho com {len(row)} colunas, esperado {N_COLS}: {row}"
                        )
                    header = row
                    writer.writerow(header)
                    continue
                # repeticao de cabecalho em paginas seguintes -> ignora
                if header is not None and row == header:
                    continue
                if len(row) != N_COLS:
                    quarantine.append(
                        {"page": pno, "line": lno, "reason": "cardinalidade", "row": row}
                    )
                    continue
                try:
                    [float(v) for v in row]
                except ValueError:
                    quarantine.append(
                        {"page": pno, "line": lno, "reason": "nao-numerico", "row": row}
                    )
                    continue
                writer.writerow(row)
                n_rows += 1
            if pno % 500 == 0:
                print(f"  pag {pno}/{doc.page_count} · {n_rows} linhas", file=sys.stderr)

    manifest = {
        "fonte_pdf": str(pdf_path),
        "sha256_pdf": _hash_file(pdf_path),
        "paginas": doc.page_count,
        "colunas": header,
        "n_colunas": len(header) if header else 0,
        "n_linhas": n_rows,
        "n_quarentena": len(quarantine),
        "saida_csv": str(out_csv),
        "sha256_csv": _hash_file(out_csv),
        "segundos": round(time.time() - t0, 1),
    }
    if manifest_path:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps({"manifest": manifest, "quarentena": quarantine[:200]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=None)
    args = ap.parse_args()
    m = extract(args.pdf, args.out, args.manifest)
    print(json.dumps(m, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
