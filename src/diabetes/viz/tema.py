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
    "tinta3": "#898781",
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

#: bloco de estilo embutido em cada SVG isolado, para que o arquivo .svg
#: sozinho continue respeitando o tema do visualizador
ESTILO_SVG = """
:root{{{claro}}}
@media (prefers-color-scheme: dark){{:root{{{escuro}}}}}
text{{font-family:{fonte};fill:var(--tinta)}}
.rot{{fill:var(--tinta2);font-size:12px}}
.eixo{{fill:var(--tinta3);font-size:11px}}
.titulo{{fill:var(--tinta);font-size:15px;font-weight:600}}
.sub{{fill:var(--tinta2);font-size:12px}}
.grade{{stroke:var(--grade);stroke-width:1}}
.base{{stroke:var(--eixo);stroke-width:1}}
.val{{fill:var(--tinta);font-size:11px;font-variant-numeric:tabular-nums}}
"""


def _vars(d: dict) -> str:
    return "".join(f"--{k}:{v};" for k, v in d.items())


def estilo() -> str:
    return ESTILO_SVG.format(claro=_vars(CLARO), escuro=_vars(ESCURO), fonte=FONTE)


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


def svg(largura: int, altura: int, corpo: str, titulo: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura} {altura}" '
        f'width="{largura}" height="{altura}" role="img" '
        f'aria-label="{escape(titulo)}">'
        f"<style>{estilo()}</style>"
        f'<rect width="{largura}" height="{altura}" fill="var(--superficie)"/>'
        f"{corpo}</svg>"
    )
