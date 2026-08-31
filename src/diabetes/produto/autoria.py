"""Autoria do trabalho — fonte unica dos nomes que aparecem nas superficies.

Existe pelo mesmo motivo de `schema.py`: nome escrito a mao em cinco arquivos
diverge no dia em que um deles muda. A capa do deck tecnico, a capa do
executivo, o cabecalho do site, o rodape da calculadora e o rodape da pagina
do metodo leem daqui — e `tests/test_produto.py` confere que todas as cinco
carregam todos os integrantes.

RA ausente e representado por `None` e renderizado como "RA a confirmar", nao
omitido: um integrante sem numero tem de aparecer como pendencia visivel, nao
sumir da lista.

Uso:
    from diabetes.produto.autoria import GRUPO, autores, CREDITO
"""

from __future__ import annotations

from dataclasses import dataclass

#: Cabecalho academico, identico nas cinco superficies.
DISCIPLINA = "Data Science 2 · Projeto 1"
INSTITUICAO = "ESEG"
PROFESSOR = "Prof. Marino Catarino"

#: Linha de credito curta, para rodape e capa.
CREDITO = f"{DISCIPLINA} · {INSTITUICAO} · {PROFESSOR}"


@dataclass(frozen=True)
class Autor:
    """Um integrante do grupo. `ra` e None enquanto o numero nao foi informado."""

    nome: str
    ra: str | None = None

    def rotulo(self) -> str:
        """Nome com RA, ou com a pendencia explicita quando o RA falta."""
        return f"{self.nome} (RA {self.ra})" if self.ra else f"{self.nome} (RA a confirmar)"


#: Ordem alfabetica pelo primeiro nome, de proposito: o trabalho nao tem primeiro
#: autor e a ordem de listagem nao deve sugerir hierarquia de contribuicao.
GRUPO: tuple[Autor, ...] = (
    Autor("Felipe Marins", "44776"),
    Autor("Otavio Bonfochi"),
    Autor("Phelipe Torres Pamponet da França", "46643"),
    Autor("Tadeu Radovan Graça", "46305"),
)


def autores(com_ra: bool = True, separador: str = " · ") -> str:
    """Os integrantes numa linha. `com_ra=False` onde o espaco nao cabe o numero."""
    if not com_ra:
        return separador.join(a.nome for a in GRUPO)
    return separador.join(a.rotulo() for a in GRUPO)


def creditos_html(com_ra: bool = True) -> str:
    """Bloco de credito de duas linhas: disciplina e professor, depois o grupo."""
    return f"{CREDITO}<br>{autores(com_ra)}"


def lista_markdown() -> str:
    """Tabela dos integrantes para o README — mesma fonte que as superficies HTML."""
    linhas = ["| integrante | RA |", "|---|---|"]
    linhas += [f"| {a.nome} | **{a.ra}** |" if a.ra else f"| {a.nome} | *a confirmar* |"
               for a in GRUPO]
    return "\n".join(linhas)


if __name__ == "__main__":  # pragma: no cover - conferencia manual
    print(CREDITO)
    print(autores())
    print()
    print(lista_markdown())
