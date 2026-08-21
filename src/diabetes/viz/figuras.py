"""Figuras do relatorio.

Le os artefatos ja gerados (`_eda_comparativa.json`, `_modelo_explicativo.json`,
`_cascata_exclusoes.json`) e emite:

  * um `.svg` por figura, autocontido e sensivel ao tema — para colar no relatorio
  * `reports/figures/index.html` — pagina unica, com tooltip e tabela de dados
    ao lado de cada grafico (a "table view" exigida pela regra de acessibilidade)

Nenhuma figura usa dois eixos y. Legenda presente sempre que ha 2+ series.
Texto sempre em tinta, nunca na cor da serie.

Uso:
    python -m diabetes.viz.figuras
"""

from __future__ import annotations

import argparse
import json
import math
from html import escape
from pathlib import Path

from diabetes.viz.tema import (
    CLARO,
    Escala,
    barra_h,
    barra_v,
    legenda,
    linha,
    ponto,
    svg,
    txt,
)

GOLD = Path("data/processed/gold")
EXT = Path("data/external/brfss2015")
SAIDA = Path("reports/figures")

S1, S2, S3 = "var(--s1)", "var(--s2)", "var(--s3)"
QUEDA = "var(--queda)"

ROTULO_A = "arquivo entregue (sem peso)"
ROTULO_B = "BRFSS completo (ponderado)"

NOMES = {
    "hipertensao": "hipertensão", "colesterol_alto": "colesterol alto",
    "exame_colesterol": "exame de colesterol", "imc": "IMC", "fumante": "fumante",
    "avc": "AVC", "doenca_cardiaca": "doença cardíaca",
    "atividade_fisica": "atividade física", "frutas": "frutas", "vegetais": "vegetais",
    "alcool_excessivo": "álcool excessivo", "acesso_saude": "acesso à saúde",
    "sem_consulta_por_custo": "sem consulta por custo", "saude_geral": "saúde geral",
    "saude_mental_dias": "dias de saúde mental", "saude_fisica_dias": "dias de saúde física",
    "dificuldade_caminhar": "dificuldade p/ caminhar", "sexo": "sexo (masculino)",
    "idade_faixa": "idade", "escolaridade": "escolaridade", "renda_faixa": "renda",
}


def nome(k: str) -> str:
    return NOMES.get(k, k.replace("_", " "))


def _dados(**kw) -> str:
    """Atributos data-* consumidos pelo tooltip da pagina."""
    return " ".join(f'data-{k}="{escape(str(v))}"' for k, v in kw.items()) + ' class="hv"'


# ==========================================================================
# 1 — cascata de exclusoes
# ==========================================================================

def fig_cascata(cascata: dict) -> tuple[str, list[list]]:
    etapas = [e for e in cascata["cascata"]
              if e["etapa"] != "final" and e["excluidos"] > 0]
    etapas.sort(key=lambda e: -e["excluidos"])
    n0 = cascata["n_original"]

    W, H = 860, 60 + len(etapas) * 26 + 70
    ml, mr = 210, 90
    xmax = max(e["excluidos"] for e in etapas)
    x = Escala(0, xmax, ml, W - mr)

    p = [txt(20, 30, "Quem foi descartado do BRFSS 2015", "titulo"),
         txt(20, 50, f"{n0:,}".replace(",", ".") + " respondentes → 253.680 · "
             "187.776 exclusões (42,5%)", "sub")]

    def rotular(e: dict) -> str:
        if e["etapa"] == 0:
            return "valores ausentes"
        return nome(e["regra"])  # nome do projeto, nao o codigo BRFSS

    y = 74
    for e in etapas:
        rot = rotular(e)
        p.append(txt(ml - 10, y + 14, rot, "rot", "end"))
        p.append(barra_h(ml, y, x(e["excluidos"]) - ml, 18, S1,
                         dados=_dados(t=f"{rot}: {e['excluidos']:,} excluídos "
                                        f"({e['excluidos'] / n0 * 100:.1f}% da amostra)"
                                      .replace(",", "."))))
        p.append(txt(x(e["excluidos"]) + 8, y + 14,
                     f"{e['excluidos']:,}".replace(",", "."), "val"))
        y += 26  # 18px de barra + 8px de folga (> 2px exigidos)

    p.append(txt(20, H - 34,
                 "As duas maiores: valores ausentes (52,1%) e renda não declarada (18,2%).",
                 "rot"))
    p.append(txt(20, H - 16,
                 "84% dos nulos em TOLDHI2 são salto de questionário — quem nunca fez "
                 "exame de colesterol.", "rot"))
    tabela = [["exclusão", "variável BRFSS", "registros", "% da amostra"]] + [
        [rotular(e), "—" if e["etapa"] == 0 else e["variavel"],
         f"{e['excluidos']:,}".replace(",", "."),
         f"{e['excluidos'] / n0 * 100:.1f}%"] for e in etapas]
    return svg(W, H, "".join(p), "Cascata de exclusões"), tabela


# ==========================================================================
# 2 — decomposicao do vies
# ==========================================================================

def fig_vies() -> tuple[str, list[list]]:
    passos = [
        ("arquivo entregue\nsem peso", 13.933, None),
        ("descarte de\n42,5% da amostra", -0.940, "queda"),
        ("BRFSS completo\nsem peso", 12.993, None),
        ("peso _LLCPWT\ndescartado", -2.493, "queda"),
        ("estimativa\npopulacional", 10.500, None),
    ]
    W, H = 860, 400
    mt, mb, ml, mr = 78, 96, 60, 30
    y = Escala(0, 15, H - mb, mt)
    larg = (W - ml - mr) / len(passos) - 26

    p = [txt(20, 30, "De onde vem o viés de prevalência", "titulo"),
         txt(20, 50, "Prevalência de diabetes (%) — 73% do viés vem do peso amostral "
             "descartado, não do descarte de linhas", "sub")]

    for v in (0, 5, 10, 15):
        p.append(f'<line x1="{ml}" y1="{y(v):.1f}" x2="{W - mr}" y2="{y(v):.1f}" class="grade"/>')
        p.append(txt(ml - 8, y(v) + 4, f"{v}", "eixo", "end"))

    base = 13.933
    for i, (rot, val, tipo) in enumerate(passos):
        rot1 = rot.replace("\n", " ")
        cx = ml + i * ((W - ml - mr) / len(passos)) + 13
        if tipo is None:
            p.append(barra_v(cx, y(val), larg, (H - mb) - y(val), S1,
                             dados=_dados(t=f"{rot1}: {val:.3f}%")))
            p.append(txt(cx + larg / 2, y(val) - 9, f"{val:.2f}%".replace(".", ","),
                         "val", "middle"))
            base = val
        else:
            topo, fundo = y(base), y(base + val)
            marca = _dados(t=f"{rot1}: {val:+.2f} p.p.")
            p.append(f'<rect x="{cx:.1f}" y="{topo:.1f}" width="{larg:.1f}" '
                     f'height="{fundo - topo:.1f}" fill="{QUEDA}" rx="4" {marca}/>')
            p.append(txt(cx + larg / 2, topo - 9, f"{val:+.2f}".replace(".", ",") + " p.p.",
                         "val", "middle"))
            base = base + val
        for j, ln in enumerate(rot.split("\n")):
            p.append(txt(cx + larg / 2, H - mb + 20 + j * 14, ln, "eixo", "middle"))

    p.append(f'<line x1="{ml}" y1="{H - mb}" x2="{W - mr}" y2="{H - mb}" class="base"/>')
    p.append(txt(20, H - 30, "Viés total: +3,43 pontos percentuais — superestimação de 32,7%.",
                 "rot"))
    tabela = [["etapa", "valor"]] + [
        [r.replace("\n", " "), (f"{v:+.2f} p.p." if t else f"{v:.3f}%").replace(".", ",")]
        for r, v, t in passos]
    return svg(W, H, "".join(p), "Decomposição do viés"), tabela


# ==========================================================================
# 3 — forest plot M1
# ==========================================================================

def fig_forest(modelo: dict) -> tuple[str, list[list]]:
    b = modelo["base_B_ponderada"]["M1_risco_puro"]["coeficientes"]
    a = modelo["base_A_sem_peso"]["M1_risco_puro"]["coeficientes"]
    itens = sorted(b.items(), key=lambda kv: -kv[1]["or"])

    W, H = 880, 90 + len(itens) * 28 + 78
    ml, mr = 200, 130
    lo = min(min(v["or_ic_baixo"] for v in b.values()),
             min(v["or"] for v in a.values())) * 0.9
    hi = max(max(v["or_ic_alto"] for v in b.values()),
             max(v["or"] for v in a.values())) * 1.1
    x = Escala(math.log(lo), math.log(hi), ml, W - mr)
    lx = lambda v: x(math.log(v))  # noqa: E731

    p = [txt(20, 30, "Fatores de risco ajustados (M1)", "titulo"),
         txt(20, 50, "Odds ratio com IC 95%. Variáveis contínuas por desvio-padrão. "
             "OR = 1 significa ausência de associação.", "sub"),
         legenda(20, 72, [(ROTULO_B, CLARO["s1"]), (ROTULO_A, CLARO["s2"])])]

    for t in (0.5, 1, 2, 4):
        if lo < t < hi:
            p.append(f'<line x1="{lx(t):.1f}" y1="88" x2="{lx(t):.1f}" '
                     f'y2="{H - 78:.1f}" class="grade"/>')
            p.append(txt(lx(t), H - 60, str(t).replace(".", ","), "eixo", "middle"))
    p.append(f'<line x1="{lx(1):.1f}" y1="88" x2="{lx(1):.1f}" y2="{H - 78:.1f}" '
             f'stroke="var(--eixo)" stroke-width="1.5" stroke-dasharray="3 3"/>')

    y = 104
    for k, v in itens:
        av = a[k]["or"]
        p.append(txt(ml - 12, y + 4, nome(k), "rot", "end"))
        p.append(f'<line x1="{lx(v["or_ic_baixo"]):.1f}" y1="{y:.1f}" '
                 f'x2="{lx(v["or_ic_alto"]):.1f}" y2="{y:.1f}" '
                 f'stroke="{S1}" stroke-width="2" stroke-linecap="round"/>')
        p.append(ponto(lx(av), y, S2, 4.5,
                       _dados(t=f"{nome(k)} — arquivo entregue: OR {av:.2f}".replace(".", ","))))
        p.append(ponto(lx(v["or"]), y, S1, 5.5,
                       _dados(t=f"{nome(k)} — populacional: OR {v['or']:.2f} "
                                f"[{v['or_ic_baixo']:.2f}; {v['or_ic_alto']:.2f}]".replace(".", ","))))
        p.append(txt(W - mr + 14, y + 4,
                     f"{v['or']:.2f}".replace(".", ",") +
                     f"  [{v['or_ic_baixo']:.2f}; {v['or_ic_alto']:.2f}]".replace(".", ","),
                     "val"))
        y += 28

    p.append(txt(20, H - 34, "Escala logarítmica. Cinco efeitos sobrevivem a todas as "
                 "especificações: hipertensão, colesterol, idade, IMC e renda.", "rot"))
    tabela = [["variável", "OR populacional", "IC 95%", "OR arquivo"]] + [
        [nome(k), f"{v['or']:.2f}".replace(".", ","),
         f"[{v['or_ic_baixo']:.2f}; {v['or_ic_alto']:.2f}]".replace(".", ","),
         f"{a[k]['or']:.2f}".replace(".", ",")] for k, v in itens]
    return svg(W, H, "".join(p), "Forest plot M1"), tabela


# ==========================================================================
# 4 — gradientes ordinais (small multiples)
# ==========================================================================

EIXOS = {
    "idade_faixa": ("Idade", ["18-24", "", "", "35-39", "", "", "50-54", "", "",
                              "65-69", "", "", "80+"]),
    "renda_faixa": ("Renda anual (USD)", ["<10k", "", "15-20k", "", "25-35k", "",
                                          "50-75k", "≥75k"]),
    "escolaridade": ("Escolaridade", ["nenhuma", "fund.", "médio inc.", "médio",
                                      "sup. inc.", "superior"]),
    "saude_geral": ("Saúde autoavaliada", ["excelente", "muito boa", "boa",
                                           "regular", "ruim"]),
}


def fig_gradientes(eda: dict) -> tuple[str, list[list]]:
    ordem = ["idade_faixa", "saude_geral", "renda_faixa", "escolaridade"]
    dados = {o["variavel"]: o for o in eda["ordinais"]}

    pw, ph = 410, 210
    W, H = 2 * pw + 40, 96 + 2 * ph + 56
    p = [txt(20, 30, "Gradientes de prevalência", "titulo"),
         txt(20, 50, "Prevalência de diabetes (%) por nível. O arquivo entregue comprime "
             "o gradiente etário pela metade.", "sub"),
         legenda(20, 74, [(ROTULO_B, CLARO["s1"]), (ROTULO_A, CLARO["s2"])])]
    tabela = [["variável", "nível", "arquivo %", "populacional %"]]

    for i, var in enumerate(ordem):
        d = dados[var]
        A = d["A_prev_por_nivel"] if isinstance(d["A_prev_por_nivel"], dict) else eval(d["A_prev_por_nivel"])
        B = d["B_prev_por_nivel"] if isinstance(d["B_prev_por_nivel"], dict) else eval(d["B_prev_por_nivel"])
        ks = sorted({int(k) for k in A} | {int(k) for k in B})
        titulo, rotulos = EIXOS[var]

        ox = 20 + (i % 2) * pw
        oy = 96 + (i // 2) * ph
        ml, mr, mt, mb = 44, 22, 30, 46
        bruto = max(max(A.values()), max(B.values())) * 1.15
        passo_t = next(s for s in (5, 10, 20, 25) if bruto / s <= 3)
        vmax = math.ceil(bruto / passo_t) * passo_t
        x = Escala(0, len(ks) - 1, ox + ml, ox + pw - mr)
        y = Escala(0, vmax, oy + ph - mb, oy + mt)

        p.append(txt(ox + ml - 8, oy + 18, titulo, "rot"))
        for t in range(0, int(vmax) + 1, passo_t):
            p.append(f'<line x1="{ox + ml}" y1="{y(t):.1f}" x2="{ox + pw - mr}" '
                     f'y2="{y(t):.1f}" class="grade"/>')
            p.append(txt(ox + ml - 6, y(t) + 4, f"{t}%", "eixo", "end"))

        for serie, cor, dic, rot in ((0, S2, A, "arquivo"), (1, S1, B, "populacional")):
            pts = [(x(j), y(dic[str(k)] if str(k) in dic else dic[k])) for j, k in enumerate(ks)]
            p.append(linha(pts, cor, 2))
            for j, k in enumerate(ks):
                v = dic[str(k)] if str(k) in dic else dic[k]
                p.append(ponto(*pts[j], cor, 4,
                               _dados(t=f"{titulo} nível {k} — {rot}: {v:.2f}%".replace(".", ","))))
                if serie == 1:
                    tabela.append([titulo, str(k),
                                   f"{(A[str(k)] if str(k) in A else A[k]):.2f}".replace(".", ","),
                                   f"{v:.2f}".replace(".", ",")])
            del serie

        for j, k in enumerate(ks):
            r = rotulos[j] if j < len(rotulos) else str(k)
            if r:
                p.append(txt(x(j), oy + ph - mb + 18, r, "eixo", "middle"))
        p.append(f'<line x1="{ox + ml}" y1="{y(0):.1f}" x2="{ox + pw - mr}" '
                 f'y2="{y(0):.1f}" class="base"/>')

    p.append(txt(20, H - 30, "Idade cai em 80+ (mortalidade seletiva) e renda inverte na "
                 "faixa mais baixa (subdiagnóstico) — nenhuma das duas é monotônica.", "rot"))
    return svg(W, H, "".join(p), "Gradientes de prevalência"), tabela


# ==========================================================================
# 5 — IMC
# ==========================================================================

def fig_imc(eda: dict) -> tuple[str, list[list]]:
    A = eda["imc"]["A_prev_por_faixa_oms"]
    B = eda["imc"]["B_prev_por_faixa_oms"]
    rot = {"baixo_peso": "baixo peso\n<18,5", "eutrofico": "eutrófico\n18,5–25",
           "sobrepeso": "sobrepeso\n25–30", "obesidade_I": "obesidade I\n30–35",
           "obesidade_II": "obesidade II\n35–40", "obesidade_III": "obesidade III\n≥40"}
    faixas = list(rot)

    W, H = 820, 400
    ml, mr, mt, mb = 54, 24, 96, 82
    vmax = max(max(A.values()), max(B.values())) * 1.15
    y = Escala(0, vmax, H - mb, mt)
    passo = (W - ml - mr) / len(faixas)
    bw = (passo - 46) / 2 - 1  # -1 de cada lado => folga de 2px entre as barras

    p = [txt(20, 30, "Prevalência de diabetes por faixa de IMC (OMS)", "titulo"),
         txt(20, 50, "Gradiente de 6,3× entre eutrófico e obesidade III na população. "
             "δ de Cliff = 0,373 — o maior efeito individual da base.", "sub"),
         legenda(20, 74, [(ROTULO_B, CLARO["s1"]), (ROTULO_A, CLARO["s2"])])]

    for t in (0, 10, 20, 30):
        p.append(f'<line x1="{ml}" y1="{y(t):.1f}" x2="{W - mr}" y2="{y(t):.1f}" class="grade"/>')
        p.append(txt(ml - 8, y(t) + 4, f"{t}%", "eixo", "end"))

    for i, f in enumerate(faixas):
        cx = ml + i * passo + 11
        p.append(barra_v(cx, y(A[f]), bw, (H - mb) - y(A[f]), S2,
                         dados=_dados(t=f"{f} — arquivo: {A[f]:.2f}%".replace(".", ","))))
        p.append(barra_v(cx + bw + 2, y(B[f]), bw, (H - mb) - y(B[f]), S1,
                         dados=_dados(t=f"{f} — populacional: {B[f]:.2f}%".replace(".", ","))))
        # rotulo direto sobre a propria barra da serie populacional
        p.append(txt(cx + bw + 2 + bw / 2, y(B[f]) - 8,
                     f"{B[f]:.1f}".replace(".", ","), "val", "middle"))
        for j, ln in enumerate(rot[f].split("\n")):
            p.append(txt(cx + bw + 1, H - mb + 20 + j * 14, ln, "eixo", "middle"))

    p.append(f'<line x1="{ml}" y1="{H - mb}" x2="{W - mr}" y2="{H - mb}" class="base"/>')
    p.append(txt(20, H - 26, "A curva em J no baixo peso é esperada: inclui diabetes tipo 1 "
                 "e perda de peso por doença.", "rot"))
    tabela = [["faixa OMS", "arquivo %", "populacional %"]] + [
        [rot[f].replace("\n", " "), f"{A[f]:.2f}".replace(".", ","),
         f"{B[f]:.2f}".replace(".", ",")] for f in faixas]
    return svg(W, H, "".join(p), "Prevalência por IMC"), tabela


# ==========================================================================
# 6 — pre-diabetes vs diabetes
# ==========================================================================

def fig_pre_vs_diabetes(modelo: dict) -> tuple[str, list[list]]:
    d = modelo["pre_vs_diabetes"]
    itens = [(k, v) for k, v in d.items() if not v["ic_sobrepoe"]]
    itens.sort(key=lambda kv: -abs(math.log(kv[1]["razao_diab_pre"])))

    W, H = 860, 96 + len(itens) * 30 + 92
    ml, mr = 210, 120
    # dominio das variaveis efetivamente desenhadas, para nao sobrar eixo vazio
    vals = [v[c] for _, v in itens for c in ("or_pre_vs_sem", "or_diab_vs_sem")]
    x = Escala(math.log(min(vals) * 0.9), math.log(max(vals) * 1.1), ml, W - mr)
    lx = lambda v: x(math.log(v))  # noqa: E731

    p = [txt(20, 30, "Pré-diabetes e diabetes não são o mesmo continuum", "titulo"),
         txt(20, 50, "Odds ratio de cada classe contra “sem diabetes”. Mostradas só as "
             "variáveis cujos IC 95% não se sobrepõem.", "sub"),
         legenda(20, 74, [("diabetes vs. sem", CLARO["s1"]),
                          ("pré-diabetes vs. sem", CLARO["s3"])])]

    dlo, dhi = min(vals) * 0.9, max(vals) * 1.1
    for t in (0.5, 0.7, 1, 1.5, 2, 3):
        if not dlo < t < dhi:
            continue
        p.append(f'<line x1="{lx(t):.1f}" y1="92" x2="{lx(t):.1f}" y2="{H - 92:.1f}" class="grade"/>')
        p.append(txt(lx(t), H - 74, str(t).replace(".", ","), "eixo", "middle"))
    p.append(f'<line x1="{lx(1):.1f}" y1="92" x2="{lx(1):.1f}" y2="{H - 92:.1f}" '
             f'stroke="var(--eixo)" stroke-width="1.5" stroke-dasharray="3 3"/>')

    y = 110
    for k, v in itens:
        pre, dia = v["or_pre_vs_sem"], v["or_diab_vs_sem"]
        inverte = (pre - 1) * (dia - 1) < 0
        p.append(txt(ml - 12, y + 4, nome(k) + (" ⟳" if inverte else ""), "rot", "end"))
        p.append(f'<line x1="{lx(pre):.1f}" y1="{y:.1f}" x2="{lx(dia):.1f}" y2="{y:.1f}" '
                 f'stroke="var(--eixo)" stroke-width="2" stroke-linecap="round"/>')
        p.append(ponto(lx(pre), y, S3, 5,
                       _dados(t=f"{nome(k)} — pré-diabetes: OR {pre:.2f} {v['ic_pre']}".replace(".", ","))))
        p.append(ponto(lx(dia), y, S1, 5,
                       _dados(t=f"{nome(k)} — diabetes: OR {dia:.2f} {v['ic_diab']}".replace(".", ","))))
        p.append(txt(W - mr + 14, y + 4,
                     f"{pre:.2f} → {dia:.2f}".replace(".", ","), "val"))
        y += 30

    p.append(txt(20, H - 46, "⟳ = o fator inverte de direção entre as duas classes. "
                 "Sexo tem OR 1,00 no pré-diabetes e 1,26 no diabetes.", "rot"))
    p.append(txt(20, H - 26, "Nove variáveis divergem: a hipótese de odds proporcionais é "
                 "rejeitada e a especificação correta é a multinomial.", "rot"))
    tabela = [["variável", "OR pré-diabetes", "OR diabetes", "inverte"]] + [
        [nome(k), f"{v['or_pre_vs_sem']:.2f}".replace(".", ","),
         f"{v['or_diab_vs_sem']:.2f}".replace(".", ","),
         "sim" if (v["or_pre_vs_sem"] - 1) * (v["or_diab_vs_sem"] - 1) < 0 else "não"]
        for k, v in itens]
    return svg(W, H, "".join(p), "Pré-diabetes vs diabetes"), tabela


# ==========================================================================
# pagina
# ==========================================================================

PAGINA = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Figuras — Diabetes BRFSS 2015</title>
<style>
:root{{color-scheme:light dark;--bg:#f9f9f7;--card:#fcfcfb;--ink:#0b0b0b;
  --ink2:#52514e;--ink3:#898781;--linha:#e1e0d9}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0d0d0d;--card:#1a1a19;--ink:#fff;
  --ink2:#c3c2b7;--ink3:#898781;--linha:#2c2c2a}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1000px;margin:0 auto;padding:40px 20px 80px}}
h1{{font-size:26px;margin:0 0 6px}}
.lead{{color:var(--ink2);margin:0 0 32px}}
figure{{margin:0 0 40px;background:var(--card);border:1px solid var(--linha);
  border-radius:10px;padding:18px;overflow-x:auto}}
figure svg{{max-width:100%;height:auto;display:block}}
details{{margin-top:12px;border-top:1px solid var(--linha);padding-top:10px}}
summary{{cursor:pointer;color:var(--ink2);font-size:13px}}
table{{border-collapse:collapse;margin-top:10px;font-size:13px;width:100%}}
th,td{{text-align:left;padding:4px 10px 4px 0;border-bottom:1px solid var(--linha);
  font-variant-numeric:tabular-nums}}
th{{color:var(--ink2);font-weight:600}}
#tt{{position:fixed;pointer-events:none;opacity:0;transition:opacity .1s;
  background:var(--ink);color:var(--card);padding:6px 10px;border-radius:6px;
  font-size:12px;max-width:300px;z-index:9}}
.hv{{cursor:crosshair}}
footer{{color:var(--ink3);font-size:12px;border-top:1px solid var(--linha);padding-top:16px}}
</style></head><body><main>
<h1>Figuras — Diabetes BRFSS 2015</h1>
<p class="lead">Data Science 2 · ESEG · gerado por <code>.\\tasks.ps1 figuras</code>.
Cada figura traz a tabela de dados; passe o mouse sobre as marcas para os valores.</p>
{figuras}
<footer>Fonte: BRFSS 2015 (CDC), 441.456 respondentes, e o arquivo de 253.680 linhas
entregue no projeto. Metodologia em <code>docs/05</code>, <code>docs/06</code> e
<code>docs/07</code>.</footer>
</main><div id="tt"></div>
<script>
const tt=document.getElementById('tt');
document.addEventListener('mouseover',e=>{{
  const m=e.target.closest('[data-t]'); if(!m)return;
  tt.textContent=m.dataset.t; tt.style.opacity=1;
}});
document.addEventListener('mousemove',e=>{{
  if(tt.style.opacity!=='1')return;
  const r=tt.getBoundingClientRect();
  tt.style.left=Math.min(e.clientX+14,innerWidth-r.width-8)+'px';
  tt.style.top=Math.max(e.clientY-r.height-12,8)+'px';
}});
document.addEventListener('mouseout',e=>{{
  if(e.target.closest('[data-t]'))tt.style.opacity=0;
}});
</script></body></html>"""


def _tabela_html(t: list[list]) -> str:
    cab = "".join(f"<th>{escape(c)}</th>" for c in t[0])
    corpo = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in ln) + "</tr>"
                    for ln in t[1:])
    return f"<table><thead><tr>{cab}</tr></thead><tbody>{corpo}</tbody></table>"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=SAIDA)
    args = ap.parse_args()

    eda = json.loads((GOLD / "_eda_comparativa.json").read_text(encoding="utf-8"))
    modelo = json.loads((GOLD / "_modelo_explicativo.json").read_text(encoding="utf-8"))
    cascata = json.loads((EXT / "_cascata_exclusoes.json").read_text(encoding="utf-8"))

    figuras = [
        ("01-cascata-exclusoes", *fig_cascata(cascata)),
        ("02-decomposicao-vies", *fig_vies()),
        ("03-forest-m1", *fig_forest(modelo)),
        ("04-gradientes", *fig_gradientes(eda)),
        ("05-imc", *fig_imc(eda)),
        ("06-pre-vs-diabetes", *fig_pre_vs_diabetes(modelo)),
    ]

    args.saida.mkdir(parents=True, exist_ok=True)
    blocos = []
    for chave, corpo, tabela in figuras:
        (args.saida / f"{chave}.svg").write_text(corpo, encoding="utf-8")
        blocos.append(
            f"<figure id='{chave}'>{corpo}"
            f"<details><summary>Ver dados ({len(tabela) - 1} linhas)</summary>"
            f"{_tabela_html(tabela)}</details></figure>"
        )
        print(f"  {chave}.svg  ({len(corpo) // 1024} KB, {len(tabela) - 1} linhas de dados)")

    (args.saida / "index.html").write_text(
        PAGINA.format(figuras="\n".join(blocos)), encoding="utf-8")
    print(f"  index.html  ({len(figuras)} figuras)")


if __name__ == "__main__":
    main()
