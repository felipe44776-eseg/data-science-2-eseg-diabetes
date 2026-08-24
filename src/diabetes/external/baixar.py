"""Baixa e verifica os arquivos de dados que ficam fora do git.

O invariante 6 do projeto diz que dado nao e versionado — manifesto com hash e.
Ate aqui isso significava que quem clonava tinha 2,5 GB de arquivo para achar a
mao, seguindo `data/external/FONTES.md`. Este modulo torna o manifesto
**executavel**: uma etapa baixa tudo e prova a integridade byte a byte.

O que nao esta aqui: o PDF de 4.374 paginas (`data/raw/Diabetes-2026.csv.pdf`).
Ele foi entregue pelo professor e nao tem URL publica — e o unico insumo que
precisa ser copiado a mao.

Uso:
    python -m diabetes.external.baixar              # baixa o que falta e verifica
    python -m diabetes.external.baixar --verificar  # so confere o que ja existe
    python -m diabetes.external.baixar --forcar     # rebaixa tudo
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(".")

#: leitura em blocos de 8 MB — 1,2 GB nao cabe na memoria de forma confortavel
BLOCO = 8 << 20


@dataclass(frozen=True)
class Fonte:
    """Um arquivo externo, com o bastante para provar que veio inteiro.

    `bytes_` e `sha256` sao do arquivo **como publicado**; divergencia significa
    download truncado, versao trocada ou espelho adulterado — nos tres casos o
    projeto tem de parar, nao seguir com dado silenciosamente diferente.
    """

    chave: str
    destino: str
    url: str
    bytes_: int
    sha256: str
    nota: str = ""


#: URL do espelho da University of Montana. O nome do arquivo termina em ESPACO
#: (`%20`) — e assim que o CDC o distribui e o espelho preservou; sem isso da 404.
#: `www.cdc.gov` responde 403 a acesso programatico, dai o espelho (ver FONTES.md).
_UMT = ("https://topofire.dbs.umt.edu/public_data/federal_public_datasets/"
        "CDC%20Behavioral%20Risk%20Factor%20Surveillance%20System%20/"
        "{ano}%20Annual%20Survey%20Data/Data%20Files/LLCP{ano}.XPT%20")

_VIGITEL = "https://svs.aids.gov.br/daent/cgdnt/vigitel"

FONTES: list[Fonte] = [
    Fonte(
        "brfss2015", "data/external/brfss2015/LLCP2015.XPT",
        _UMT.format(ano=2015), 1_165_490_800,
        "bfe9e62977cfc5183e51c3e8bdb5193510995cc3c21b225e568f537ad300b1b9",
        "441.456 x 330 — a fonte que prova o vies do arquivo entregue (docs/05)",
    ),
    Fonte(
        "brfss2023", "data/external/brfss2023/LLCP2023.XPT",
        _UMT.format(ano=2023), 1_205_554_400,
        "3d3bf8ef5195bde227828ddc4c90745b76e8b304f8f5b9a043b6d99895fd1615",
        "421.745 x 350 — validacao temporal (docs/22)",
    ),
    Fonte(
        "vigitel2015", "data/external/vigitel/vigitel-2015-peso-rake.zip",
        f"{_VIGITEL}/vigitel-2015-peso-rake.zip", 10_775_599,
        "2e24a11ec1a43d74e4cfe9087ab533f0cbe7a1fe50d902787dc48818dfe4ef95",
        "54.174 x 190, formato OLE2 (exige xlrd) — comparacao binacional (docs/09)",
    ),
    Fonte(
        "vigitel2023", "data/external/vigitel/vigitel-2023-peso-rake.zip",
        f"{_VIGITEL}/vigitel-2023-peso-rake.zip", 15_935_870,
        "566fc89d38cafbf2451ff41cd7796ebfce709eb3ae5305fbf69a20acb43dc3b5",
        "escore recalibrado para o Brasil (docs/18)",
    ),
    Fonte(
        "dicionario-vigitel", "data/external/vigitel/dicionario-vigitel-2006-2024.xlsx",
        f"{_VIGITEL}/dicionario-vigitel-2006-2024.xlsx", 93_263,
        "c67e63f6f10c2aae7694f3f67b5d2c897240ecf7f930fd9a2080404bc8df6c4b",
        "sem ele nao da para saber que q74 e saude autoavaliada",
    ),
]

#: entregue pelo professor, sem URL publica — tem de ser copiado a mao
SEM_URL = {
    "data/raw/Diabetes-2026.csv.pdf":
        "PDF de 4.374 paginas entregue no enunciado. Copie para data/raw/.",
}


def sha256(caminho: Path) -> str:
    """SHA-256 do arquivo inteiro, lido em blocos de 8 MB."""
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        for b in iter(lambda: fh.read(BLOCO), b""):
            h.update(b)
    return h.hexdigest()


def verificar(f: Fonte, raiz: Path = RAIZ) -> dict:
    """Confere existencia, tamanho e hash. Nao baixa nada.

    O tamanho e checado antes do hash de proposito: e instantaneo e pega o caso
    comum (download interrompido) sem ler 1,2 GB.
    """
    p = raiz / f.destino
    if not p.exists():
        return {"chave": f.chave, "estado": "ausente"}
    tam = p.stat().st_size
    if tam != f.bytes_:
        return {"chave": f.chave, "estado": "tamanho-errado",
                "esperado": f.bytes_, "obtido": tam}
    obtido = sha256(p)
    if obtido != f.sha256:
        return {"chave": f.chave, "estado": "hash-errado",
                "esperado": f.sha256, "obtido": obtido}
    return {"chave": f.chave, "estado": "ok", "bytes": tam}


def baixar(f: Fonte, raiz: Path = RAIZ) -> Path:
    """Baixa para um arquivo temporario e so renomeia se o hash bater.

    Escrever direto no destino deixaria um arquivo truncado com o nome certo se a
    conexao caisse — e a proxima execucao o trataria como valido.
    """
    destino = raiz / f.destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".parcial")

    print(f"  baixando {f.chave} ({f.bytes_ / 1e6:,.0f} MB)…")
    req = urllib.request.Request(f.url, headers={"User-Agent": "curl/8"})
    lidos = 0
    with urllib.request.urlopen(req, timeout=180) as r, parcial.open("wb") as fh:
        while bloco := r.read(BLOCO):
            fh.write(bloco)
            lidos += len(bloco)
            if f.bytes_:
                pct = lidos / f.bytes_ * 100
                print(f"\r    {lidos / 1e6:,.0f} / {f.bytes_ / 1e6:,.0f} MB "
                      f"({pct:.0f}%)", end="", flush=True)
    print()

    obtido = sha256(parcial)
    if obtido != f.sha256:
        parcial.unlink(missing_ok=True)
        raise SystemExit(
            f"  {f.chave}: hash divergente — o arquivo NAO e o esperado.\n"
            f"    esperado {f.sha256}\n    obtido   {obtido}\n"
            f"    o download foi descartado. Ver data/external/FONTES.md")
    parcial.replace(destino)
    return destino


def main() -> None:
    """Baixa o que falta, verifica tudo e sai com codigo 1 se algo divergir."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verificar", action="store_true",
                    help="so confere o que ja existe; nao baixa")
    ap.add_argument("--forcar", action="store_true", help="rebaixa mesmo se ja existir")
    ap.add_argument("--apenas", nargs="*", metavar="CHAVE",
                    help=f"limita a {', '.join(f.chave for f in FONTES)}")
    args = ap.parse_args()

    alvos = [f for f in FONTES if not args.apenas or f.chave in args.apenas]
    problemas = []

    for f in alvos:
        r = verificar(f)
        if r["estado"] == "ok" and not args.forcar:
            print(f"  [ok]      {f.chave:20} {r['bytes']:,} bytes · hash confere"
                  .replace(",", "."))
            continue
        if args.verificar:
            print(f"  [{r['estado'].upper()}] {f.chave:20} {f.destino}")
            problemas.append(f.chave)
            continue
        baixar(f)
        print(f"  [ok]      {f.chave:20} baixado e verificado")

    print("\n  --- insumos sem URL publica ---")
    for caminho, nota in SEM_URL.items():
        existe = (RAIZ / caminho).exists()
        print(f"  [{'ok' if existe else 'AUSENTE'}]      {caminho}")
        if not existe:
            print(f"            {nota}")
            problemas.append(caminho)

    if problemas:
        print(f"\n  pendente: {', '.join(problemas)}")
        sys.exit(1)
    print("\n  Todos os insumos presentes e integros.")


if __name__ == "__main__":
    main()
