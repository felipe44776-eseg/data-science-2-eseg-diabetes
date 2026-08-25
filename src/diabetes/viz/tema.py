"""Tokens de cor e primitivos SVG.

A paleta e a instancia de referencia do metodo de dataviz, **validada** nos dois
modos com `validate_palette.js` (3 slots, `--pairs all`):

    claro  #2a78d6 #eb6834 #1baf7a   CVD dE 9,2 · normal 24,0 · PASS
    escuro #3987e5 #d95926 #199e70   CVD dE 9,4 · normal 20,9 · PASS

Ressalva registrada pelo validador: no modo claro o aqua (#1baf7a) fica em
2,74:1 contra a superficie — abaixo de 3:1. A regra de alivio se aplica: onde
ele aparece, o grafico traz **rotulo direto visivel**. Por isso o aqua so entra
em series rotuladas.

Regras de marca seguidas (marks-and-anatomy):
  * linha 2px, marcador >= 8px
  * ponta de barra arredondada 4px, ancorada na linha de base
  * folga de 2px da cor de superficie entre barras adjacentes
  * grade e eixos recessivos; texto sempre em tinta, nunca na cor da serie
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

# --- tokens ---------------------------------------------------------------

CLARO = {
    "superficie": "#fcfcfb",
    "plano": "#f9f9f7",
    "tinta": "#0b0b0b",
    "tinta2": "#52514e",
    # #898781 dava 3,50:1 sobre a superficie clara — abaixo do minimo de 4,5:1 do
    # WCAG AA para texto normal, e `tinta3` e a cor de TODO rotulo de eixo. Medido
    # com Puppeteer: 58 rotulos por pagina reprovavam. #706e68 da 4,97:1.
    "tinta3": "#706e68",
    "grade": "#e1e0d9",
    "eixo": "#c3c2b7",
    "s1": "#2a78d6",
    "s2": "#eb6834",
    "s3": "#1baf7a",
    "neutro": "#f0efec",
    "queda": "#d03b3b",
    "borda": "rgba(11,11,11,0.10)",
}

ESCURO = {
    "superficie": "#1a1a19",
    "plano": "#0d0d0d",
    "tinta": "#ffffff",
    "tinta2": "#c3c2b7",
    "tinta3": "#898781",
    "grade": "#2c2c2a",
    "eixo": "#383835",
    "s1": "#3987e5",
    "s2": "#d95926",
    "s3": "#199e70",
    "neutro": "#383835",
    "queda": "#e66767",
    "borda": "rgba(255,255,255,0.10)",
}

FONTE = 'system-ui, -apple-system, "Segoe UI", sans-serif'

#: Bloco de estilo embutido em cada SVG, para que o arquivo `.svg` aberto sozinho
#: continue respeitando o tema do visualizador.
#:
#: Os tokens vao em `svg{{}}`, NAO em `:root{{}}`. Parece detalhe e nao e: quando o
#: SVG e embutido numa pagina HTML — que e o caso do deck, da pagina do metodo e da
#: de figuras — um `:root` dentro do `<style>` do SVG casa com o `<html>` do
#: documento e **sobrescreve os tokens da pagina inteira**. Em modo escuro isso
#: trocava `--tinta` por uma cor clara enquanto o fundo do slide continuava claro:
#: contraste de 1,03:1, texto invisivel em todos os slides. Em `svg{{}}` as
#: variaveis cascateiam para os filhos do proprio grafico e param ali; no arquivo
#: isolado o elemento raiz E o `<svg>`, entao nada se perde.
ESTILO_SVG = """
svg{{{claro}}}
@media (prefers-color-scheme: dark){{svg{{{escuro}}}}}
text{{font-family:{fonte};fill:var(--tinta)}}
.rot{{fill:var(--tinta2);font-size:{r}px}}
.eixo{{fill:var(--tinta3);font-size:{e}px}}
.titulo{{fill:var(--tinta);font-size:{t}px;font-weight:600}}
.sub{{fill:var(--tinta2);font-size:{r}px}}
.grade{{stroke:var(--grade);stroke-width:1}}
.base{{stroke:var(--eixo);stroke-width:1}}
.val{{fill:var(--tinta);font-size:{e}px;font-variant-numeric:tabular-nums}}
"""


def _vars(d: dict) -> str:
    return "".join(f"--{k}:{v};" for k, v in d.items())


def estilo(escala: float = 1.0) -> str:
    """Bloco `<style>` com os tokens dos dois modos, para embutir em cada SVG.

    Os tokens entram em `svg{}` mais um `prefers-color-scheme`, entao o `.svg`
    aberto sozinho continua respeitando o tema do sistema — e, embutido em HTML, nao
    vaza para a pagina. Ver a nota em `ESTILO_SVG`.

    `escala` multiplica os corpos de texto. Existe porque o mesmo grafico serve a
    dois contextos com distancias de leitura diferentes: numa pagina de relatorio,
    11px lidos a 50 cm; num slide projetado, o SVG e reduzido para caber na coluna e
    o mesmo 11px vira ~9px vistos de longe. Medido com Puppeteer.
    """
    return ESTILO_SVG.format(claro=_vars(CLARO), escuro=_vars(ESCURO), fonte=FONTE,
                             r=round(12 * escala, 1), e=round(11 * escala, 1),
                             t=round(15 * escala, 1))


# --- primitivos -----------------------------------------------------------

@dataclass
class Escala:
    """Mapeia dominio -> pixels. Linear."""

    d0: float
    d1: float
    p0: float
    p1: float

    def __call__(self, v: float) -> float:
        if self.d1 == self.d0:
            return self.p0
        return self.p0 + (v - self.d0) / (self.d1 - self.d0) * (self.p1 - self.p0)


def txt(x: float, y: float, s: str, classe: str = "rot", anchor: str = "start",
        extra: str = "") -> str:
    """Elemento `<text>` com conteudo escapado; a classe define cor e tamanho.

    A cor vem sempre da classe (`rot`, `eixo`, `val`, `titulo`, `sub`) e nunca da
    cor da serie — texto em tinta e regra de marca do projeto. O conteudo passa por
    `escape`, entao rotulo com `&`, `<` ou aspas nao quebra o SVG.
    """
    return (f'<text x="{x:.1f}" y="{y:.1f}" class="{classe}" '
            f'text-anchor="{anchor}" {extra}>{escape(str(s))}</text>')


def barra_h(x: float, y: float, larg: float, alt: float, cor: str,
            raio: float = 4, dados: str = "") -> str:
    """Barra horizontal com a ponta arredondada e a base reta (ancorada no eixo)."""
    larg = max(larg, 0.5)
    r = min(raio, larg, alt / 2)
    d = (f"M{x:.1f},{y:.1f} H{x + larg - r:.1f} Q{x + larg:.1f},{y:.1f} "
         f"{x + larg:.1f},{y + r:.1f} V{y + alt - r:.1f} "
         f"Q{x + larg:.1f},{y + alt:.1f} {x + larg - r:.1f},{y + alt:.1f} "
         f"H{x:.1f} Z")
    return f'<path d="{d}" fill="{cor}" {dados}/>'


def barra_v(x: float, y: float, larg: float, alt: float, cor: str,
            raio: float = 4, dados: str = "") -> str:
    """Barra vertical; topo arredondado, base reta."""
    alt = max(alt, 0.5)
    r = min(raio, alt, larg / 2)
    d = (f"M{x:.1f},{y + alt:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
         f"H{x + larg - r:.1f} Q{x + larg:.1f},{y:.1f} {x + larg:.1f},{y + r:.1f} "
         f"V{y + alt:.1f} Z")
    return f'<path d="{d}" fill="{cor}" {dados}/>'


def linha(pontos: list[tuple[float, float]], cor: str, largura: float = 2) -> str:
    """Polilinha de serie, 2px, com junta e ponta arredondadas.

    `fill="none"` e explicito: sem ele o SVG fecharia o caminho e pintaria a area
    sob a curva, transformando um grafico de linha num de area por acidente.
    """
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pontos)
    return (f'<path d="{d}" fill="none" stroke="{cor}" stroke-width="{largura}" '
            f'stroke-linejoin="round" stroke-linecap="round"/>')


def ponto(x: float, y: float, cor: str, r: float = 4.5, dados: str = "") -> str:
    """Marcador com anel de 2px na cor da superficie, para sobreposicao legivel."""
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{cor}" '
            f'stroke="var(--superficie)" stroke-width="2" {dados}/>')


def legenda(x: float, y: float, itens: list[tuple[str, str]]) -> str:
    """Legenda sempre presente quando ha 2+ series (identidade nunca so por cor)."""
    partes, dx = [], 0.0
    for rotulo, cor in itens:
        partes.append(f'<circle cx="{x + dx + 5:.1f}" cy="{y - 4:.1f}" r="5" fill="{cor}"/>')
        partes.append(txt(x + dx + 15, y, rotulo, "rot"))
        dx += 15 + len(rotulo) * 6.6 + 20
    return "".join(partes)


def svg(largura: int, altura: int, corpo: str, titulo: str = "",
        escala: float = 1.0) -> str:
    """Envelope do SVG: viewBox, estilo embutido, fundo de superficie e rotulo ARIA.

    `role="img"` com `aria-label` e o que da nome acessivel a figura. `viewBox` ao
    lado de `width`/`height` mantem o arquivo escalavel e ainda assim com tamanho
    natural ao ser colado no relatorio.

    O retangulo de fundo em `var(--superficie)` nao e decoracao: SVG e transparente
    por padrao, e sem ele o texto em tinta ficaria sobre o fundo de quem embute — o
    que inverte a legibilidade quando os temas divergem.
    """
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura} {altura}" '
        f'width="{largura}" height="{altura}" role="img" '
        f'aria-label="{escape(titulo)}">'
        f"<style>{estilo(escala)}</style>"
        f'<rect width="{largura}" height="{altura}" fill="var(--superficie)"/>'
        f"{corpo}</svg>"
    )
