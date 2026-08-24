"""Pagina didatica do metodo — a decisao de cada etapa, e o grafico que a sustenta.

Os 25 documentos de `docs/` contam o que foi feito, mas cada um de um angulo e em
ordem de descoberta. Falta uma superficie que responda, para quem esta chegando:
**em cada etapa, qual era a pergunta, o que se decidiu, por que, e qual numero
sustenta a decisao.**

E o que esta pagina faz. Regra de construcao: **nenhum grafico decorativo.** Todo
grafico existe para sustentar uma decisao especifica, e vem legendado com a decisao
que ele embasa.

A matriz de confusao, a ROC e a PR sao calculadas aqui a partir do **modelo que o
usuario recebe** — as tabelas de consulta exportadas em `reports/produto/modelo.json`,
avaliadas pela mesma `prever_do_json` que a paridade Python<->JS verifica. Nao e o
modelo interno de `escada.py`: e o que esta servido na calculadora, que e sobre o
que faz sentido mostrar matriz de confusao a um leitor.

Uso:
    python -m diabetes.produto.metodo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from diabetes.models.expandido import particionar
from diabetes.produto.exportar import prever_do_json
from diabetes.viz.tema import Escala, barra_h, barra_v, legenda, linha, ponto, svg, txt

RAIZ = Path(".")
GOLD = RAIZ / "data" / "processed" / "gold"
EXT = RAIZ / "data" / "external"
PRODUTO = RAIZ / "reports" / "produto"
SAIDA = RAIZ / "reports" / "metodo"

S1, S2, S3 = "var(--s1)", "var(--s2)", "var(--s3)"
QUEDA = "var(--queda)"

#: especificidade em que o limiar operacional e fixado. 90% e o ponto em que a
#: curva de decisao de `docs/16` ainda supera "rastrear todos" com folga.
ESPECIFICIDADE = 0.90


def _guia(pontos: list[tuple[float, float]]) -> str:
    """Linha de referencia tracejada e recessiva — nunca compete com a serie."""
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pontos)
    return ('<path d="' + d + '" fill="none" stroke="var(--linha)" '
            'stroke-width="1.5" stroke-dasharray="5 4"/>')


def ler(nome: str, base: Path = GOLD) -> dict:
    """Le um artefato do pipeline. Falha alto: pagina sem numero nao avisa ninguem."""
    return json.loads((base / nome).read_text(encoding="utf-8"))


# ==========================================================================
# predicoes do modelo SERVIDO (tabelas de consulta), no holdout
# ==========================================================================

def prever_holdout(amostra: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Roda o modelo exportado sobre o holdout e devolve (y, p).

    Usa `prever_do_json`, a mesma funcao que a suite compara contra o JavaScript.
    Assim a matriz de confusao mostrada e a do modelo que as pessoas realmente
    usam, nao a de um modelo interno que ninguem recebe.
    """
    modelo = json.loads((PRODUTO / "modelo.json").read_text(encoding="utf-8"))
    variaveis = modelo["ebm"]["variaveis"]
    df = pd.read_parquet(GOLD / "brfss_expandido.parquet")
    d = df[particionar(df)]
    if amostra and amostra < len(d):
        d = d.sample(amostra, random_state=42)
    y = d["diabetes"].astype(int).to_numpy()
    p = np.array([prever_do_json(modelo["ebm"], r)[0]
                  for r in d[variaveis].to_dict("records")])
    return y, p


def matriz_de_confusao(y: np.ndarray, p: np.ndarray,
                       especificidade: float = ESPECIFICIDADE) -> dict:
    """Matriz 2x2 no limiar que atinge a especificidade pedida.

    O limiar NAO e 0,5. Com 14% de prevalencia, 0,5 classifica quase todo mundo
    como negativo e a matriz vira uma coluna — o que reproduz exatamente o problema
    que o ADR 0005 descreve ao banir a acuracia. O limiar sai da especificidade
    porque e assim que um programa de rastreamento e dimensionado: primeiro se
    decide quantos falsos positivos o orcamento aguenta, depois se le o recall.
    """
    limiar = float(np.quantile(p[y == 0], especificidade))
    pred = p >= limiar
    vp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    vn = int(((pred == 0) & (y == 0)).sum())
    return {
        "limiar": round(limiar, 4), "vp": vp, "fp": fp, "fn": fn, "vn": vn,
        "n": vp + fp + fn + vn,
        "recall": round(vp / max(vp + fn, 1), 4),
        "precisao": round(vp / max(vp + fp, 1), 4),
        "especificidade": round(vn / max(vn + fp, 1), 4),
        "prevalencia": round((vp + fn) / max(vp + fp + fn + vn, 1), 4),
    }


def _curva(y: np.ndarray, p: np.ndarray, pontos: int = 60) -> dict:
    """ROC e precision-recall em `pontos` limiares, por quantil do escore."""
    qs = np.linspace(0, 1, pontos)
    roc, pr = [], []
    n_pos, n_neg = int((y == 1).sum()), int((y == 0).sum())
    for q in qs:
        t = float(np.quantile(p, q))
        pred = p >= t
        vp = int((pred & (y == 1)).sum())
        fp = int((pred & (y == 0)).sum())
        roc.append({"fpr": fp / max(n_neg, 1), "tpr": vp / max(n_pos, 1)})
        if vp + fp:
            pr.append({"recall": vp / max(n_pos, 1), "precisao": vp / (vp + fp)})
    return {"roc": roc, "pr": pr, "prevalencia": n_pos / max(n_pos + n_neg, 1)}


# ==========================================================================
# graficos
# ==========================================================================

def g_confusao(m: dict) -> str:
    """Matriz de confusao como quatro blocos proporcionais, com taxa e contagem."""
    W, H = 620, 340
    ml, mt, cel = 150, 74, 190
    total = m["n"]
    blocos = [
        (0, 0, "Verdadeiro positivo", m["vp"], S3, "achado"),
        (1, 0, "Falso positivo", m["fp"], S2, "testado a toa"),
        (0, 1, "Falso negativo", m["fn"], QUEDA, "perdido"),
        (1, 1, "Verdadeiro negativo", m["vn"], "var(--tinta3)", "poupado"),
    ]
    p = [txt(20, 30, "Matriz de confusão do modelo servido", "titulo"),
         txt(20, 50, f"limiar em especificidade de {ESPECIFICIDADE:.0%} · "
                     f"holdout de {total:,} pessoas".replace(",", "."), "sub"),
         txt(ml + cel, mt - 14, "PREVISTO", "eixo", "middle"),
         txt(ml - 118, mt + cel, "OBSERVADO", "eixo")]
    for col, rot in ((0, "risco alto"), (1, "risco baixo")):
        p.append(txt(ml + col * cel + cel / 2, mt - 32, rot, "rot", "middle"))
    for lin, rot in ((0, "tem diagnóstico"), (1, "sem diagnóstico")):
        p.append(txt(ml - 10, mt + lin * (cel / 2) + 34, rot, "rot", "end"))

    for col, lin, nome, v, cor, papel in blocos:
        x, yy = ml + col * cel, mt + lin * (cel / 2)
        pct = v / total * 100
        p.append(f'<rect x="{x}" y="{yy}" width="{cel - 6}" height="{cel / 2 - 6}" '
                 f'rx="8" fill="{cor}" opacity="0.16"/>')
        p.append(txt(x + 14, yy + 34, f"{v:,}".replace(",", "."), "val"))
        p.append(txt(x + 14, yy + 54, f"{pct:.1f}% do total".replace(".", ","), "rot"))
        p.append(txt(x + 14, yy + 74, f"{nome} · {papel}", "rot"))

    p.append(txt(20, H - 30,
                 f"recall {m['recall']:.1%} · precisão {m['precisao']:.1%} · "
                 f"especificidade {m['especificidade']:.1%}".replace(".", ","), "rot"))
    return svg(W, H, "".join(p), "Matriz de confusão")


def g_roc_pr(c: dict) -> str:
    """ROC e precision-recall lado a lado, com as duas linhas de referencia."""
    W, H = 860, 330
    lado, mt, mb, ml = 300, 70, 58, 66
    p = [txt(20, 30, "ROC e precision-recall — por que a PR é a métrica primária",
             "titulo"),
         txt(20, 50, f"prevalência de {c['prevalencia']:.1%}: a linha de base da PR "
                     f"é {c['prevalencia']:.1%}, a da ROC é 50%".replace(".", ","), "sub")]

    # --- ROC
    ex = Escala(0, 1, ml, ml + lado)
    ey = Escala(0, 1, H - mb, mt)
    p.append(_guia([(ex(0), ey(0)), (ex(1), ey(1))]))
    p.append(linha([(ex(r["fpr"]), ey(r["tpr"])) for r in c["roc"]], S1))
    p.append(txt(ml, mt - 16, "ROC", "rot"))
    p.append(txt(ml + lado / 2, H - mb + 34, "falsos positivos", "eixo", "middle"))

    # --- PR
    ml2 = ml + lado + 96
    ex2 = Escala(0, 1, ml2, ml2 + lado)
    base = c["prevalencia"]
    p.append(_guia([(ex2(0), ey(base)), (ex2(1), ey(base))]))
    p.append(linha([(ex2(r["recall"]), ey(r["precisao"])) for r in c["pr"]], S2))
    p.append(txt(ml2, mt - 16, "precision-recall", "rot"))
    p.append(txt(ml2 + lado / 2, H - mb + 34, "recall", "eixo", "middle"))

    for x0 in (ml, ml2):
        for v in (0, 0.5, 1.0):
            p.append(txt(x0 - 8, ey(v) + 4, f"{v:.0%}", "eixo", "end"))
            p.append(f'<line x1="{x0}" y1="{ey(v):.1f}" x2="{x0 + lado}" '
                     f'y2="{ey(v):.1f}" class="grade"/>')
    return svg(W, H, "".join(p), "Curvas ROC e precision-recall")


def g_calibracao(sem: list[dict], com: list[dict]) -> str:
    """Diagrama de confiabilidade: previsto x observado, antes e depois de calibrar."""
    W, H = 620, 400
    ml, mt, mb = 66, 76, 62
    lado = W - ml - 40
    mx = max(max(f["previsto"] for f in sem + com),
             max(f["observado"] for f in sem + com))
    ex, ey = Escala(0, mx, ml, ml + lado), Escala(0, mx, H - mb, mt)
    p = [txt(20, 30, "Calibração: por que ela é requisito, não refinamento", "titulo"),
         txt(20, 50, "a diagonal é a perfeição — o modelo cru ordena igual e "
                     "mente no nível", "sub"),
         _guia([(ex(0), ey(0)), (ex(mx), ey(mx))])]
    for serie, cor in ((sem, S2), (com, S3)):
        pts = [(ex(f["previsto"]), ey(f["observado"])) for f in serie]
        p.append(linha(pts, cor))
        for x, yy in pts:
            p.append(ponto(x, yy, cor, 4))
    for v in (0, mx / 2, mx):
        p.append(txt(ml - 8, ey(v) + 4, f"{v:.0%}", "eixo", "end"))
        p.append(txt(ex(v), H - mb + 20, f"{v:.0%}", "eixo", "middle"))
        p.append(f'<line x1="{ml}" y1="{ey(v):.1f}" x2="{ml + lado}" '
                 f'y2="{ey(v):.1f}" class="grade"/>')
    p.append(txt(ml + lado / 2, H - mb + 44, "risco previsto", "eixo", "middle"))
    p.append(legenda(ml, mt - 26, [("sem calibrar", S2), ("calibrado (isotônica)", S3)]))
    return svg(W, H, "".join(p), "Diagrama de confiabilidade")


def g_escada(modelos: dict) -> str:
    """PR-AUC por degrau da escada — o argumento de que o algoritmo nao e o gargalo."""
    rot = {"0_prevalencia": "prevalência (chute)", "1_regra_clinica": "regra clínica",
           "2_logistica_l2": "logística L2", "3_spline": "spline",
           "4_gradient_boosting": "gradient boosting", "5_gb_calibrado": "GB calibrado"}
    itens = [(rot.get(k, k), m["holdout"]["pr_auc"],
              S3 if k == "5_gb_calibrado" else S1)
             for k, m in modelos.items()]
    W = 780
    H = 92 + len(itens) * 30 + 46
    ml, mr = 210, 80
    mx = max(v for _, v, _ in itens)
    x = Escala(0, mx, ml, W - mr)
    p = [txt(20, 30, "Escada de modelos — o algoritmo não é o gargalo", "titulo"),
         txt(20, 50, "PR-AUC no holdout · da regra mais burra ao melhor modelo",
             "sub")]
    yy = 84
    for nome, v, cor in itens:
        p.append(txt(ml - 10, yy + 14, nome, "rot", "end"))
        p.append(barra_h(ml, yy, x(v) - ml, 18, cor))
        p.append(txt(x(v) + 8, yy + 14, f"{v:.4f}".replace(".", ","), "val"))
        yy += 30
    p.append(txt(20, H - 20,
                 "Da logística ao boosting calibrado, o ganho é pequeno perto do "
                 "salto que veio de recuperar variáveis (docs/10).", "rot"))
    return svg(W, H, "".join(p), "Escada de modelos")


def g_parcimonia(curva: list[dict], teto: float) -> str:
    """% do teto por numero de variaveis — sustenta o escore de 5 perguntas."""
    W, H = 780, 340
    ml, mt, mb = 66, 76, 66
    lado = W - ml - 60
    ex = Escala(1, max(c["n_variaveis"] for c in curva), ml, ml + lado)
    ey = Escala(0, 100, H - mb, mt)
    p = [txt(20, 30, "Curva de parcimônia — quantas perguntas bastam?", "titulo"),
         txt(20, 50, "% do PR-AUC do modelo completo, por nº de variáveis "
                     "(seleção gulosa)", "sub")]
    for v in (0, 50, 100):
        p.append(txt(ml - 8, ey(v) + 4, f"{v}%", "eixo", "end"))
        p.append(f'<line x1="{ml}" y1="{ey(v):.1f}" x2="{ml + lado}" '
                 f'y2="{ey(v):.1f}" class="grade"/>')
    pts = [(ex(c["n_variaveis"]), ey(c["%_do_teto"])) for c in curva]
    p.append(linha(pts, S1))
    for (x, yy), c in zip(pts, curva, strict=True):
        p.append(ponto(x, yy, S1, 5))
        p.append(txt(x, yy - 14, f"{c['%_do_teto']:.0f}%", "val", "middle"))
        p.append(txt(x, H - mb + 20, str(c["n_variaveis"]), "eixo", "middle"))
        p.append(txt(x, H - mb + 38, c["adicionada"][:11], "eixo", "middle"))
    p.append(txt(20, H - 14,
                 f"Teto de referência: PR-AUC {teto:.4f}. ".replace(".", ",")
                 + "A curva satura cedo — é o que justifica um escore de papel.",
                 "rot"))
    return svg(W, H, "".join(p), "Curva de parcimônia")


def g_decisao(curva: list[dict]) -> str:
    """Net benefit contra as duas estrategias triviais (Vickers & Elkin)."""
    W, H = 780, 350
    ml, mt, mb = 74, 78, 62
    lado = W - ml - 46
    lim = [c["limiar"] for c in curva]
    ex = Escala(min(lim), max(lim), ml, ml + lado)
    mx = max(max(c["nb_modelo"] for c in curva),
             max(c["nb_rastrear_todos"] for c in curva))
    ey = Escala(0, mx, H - mb, mt)
    p = [txt(20, 30, "Curva de decisão — vale usar o modelo?", "titulo"),
         txt(20, 50, "benefício líquido (Vickers & Elkin, 2006) contra rastrear "
                     "todos e rastrear ninguém", "sub"),
         _guia([(ex(min(lim)), ey(0)), (ex(max(lim)), ey(0))])]
    p.append(linha([(ex(c["limiar"]), ey(max(c["nb_rastrear_todos"], 0)))
                    for c in curva], S2))
    p.append(linha([(ex(c["limiar"]), ey(c["nb_modelo"])) for c in curva], S1))
    for v in (0, mx / 2, mx):
        p.append(txt(ml - 8, ey(v) + 4, f"{v:.3f}".replace(".", ","), "eixo", "end"))
    for t in (0.05, 0.2, 0.4):
        if min(lim) <= t <= max(lim):
            p.append(txt(ex(t), H - mb + 20, f"{t:.0%}", "eixo", "middle"))
    p.append(txt(ml + lado / 2, H - mb + 42, "limiar de risco adotado",
                 "eixo", "middle"))
    p.append(legenda(ml, mt - 26, [("modelo", S1), ("rastrear todos", S2),
                                   ("rastrear ninguém = 0", "var(--tinta3)")]))
    return svg(W, H, "".join(p), "Curva de decisão")


def g_cobertura(cob: list[dict]) -> str:
    """% de casos encontrados por % da populacao testada — traduz metrica em orcamento."""
    W, H = 780, 330
    ml, mt, mb = 66, 76, 62
    lado = W - ml - 46
    ex = Escala(0, max(c["%_testado"] for c in cob), ml, ml + lado)
    ey = Escala(0, 100, H - mb, mt)
    p = [txt(20, 30, "Quantos testar, quantos achar", "titulo"),
         txt(20, 50, "% dos casos encontrados por % da população rastreada", "sub"),
         _guia([(ex(0), ey(0)), (ex(100), ey(100))])]
    for v in (0, 50, 100):
        p.append(txt(ml - 8, ey(v) + 4, f"{v}%", "eixo", "end"))
        p.append(f'<line x1="{ml}" y1="{ey(v):.1f}" x2="{ml + lado}" '
                 f'y2="{ey(v):.1f}" class="grade"/>')
    pts = [(ex(c["%_testado"]), ey(c["%_casos_encontrados"])) for c in cob]
    p.append(linha(pts, S3))
    for (x, yy), c in zip(pts, cob, strict=True):
        p.append(ponto(x, yy, S3, 4))
        p.append(txt(x, H - mb + 20, f"{c['%_testado']:.0f}%", "eixo", "middle"))
    dez = next((c for c in cob if c["%_testado"] == 10.0), cob[0])
    p.append(txt(20, H - 16,
                 f"Testando 10% acha {dez['%_casos_encontrados']:.1f}% dos casos, "
                 f"a R$ {dez['custo_por_caso_R$'][1]:.0f} por caso."
                 .replace(".", ","), "rot"))
    return svg(W, H, "".join(p), "Curva de cobertura")


def g_equidade(grupos: list[dict]) -> str:
    """Recall e precisao por grupo racial, com o mesmo limiar global."""
    grupos = [g for g in grupos if g.get("n", 0) >= 400]
    W = 800
    H = 96 + len(grupos) * 46 + 40
    ml, mr = 240, 90
    x = Escala(0, 1, ml, W - mr)
    p = [txt(20, 30, "Equidade — mesmo limiar, resultados diferentes", "titulo"),
         txt(20, 50, "recall e precisão por grupo racial, limiar global "
                     "(a impossibilidade de Chouldechova)", "sub"),
         legenda(ml, 68, [("recall", S1), ("precisão", S2)])]
    yy = 96
    for g in grupos:
        p.append(txt(ml - 10, yy + 20, str(g["grupo"])[:26], "rot", "end"))
        # Chave errada com `.get(..., 0)` nao levanta erro: desenha barra zerada e a
        # pagina fica plausivel e vazia. Foi o que aconteceu na primeira versao
        # (usava "tpr"/"ppv"; o artefato grava "recall_tpr"/"precisao_ppv"). Indexar
        # direto faz o build falhar, que e o comportamento correto.
        for k, cor, dy in (("recall_tpr", S1, 0), ("precisao_ppv", S2, 20)):
            v = float(g[k])
            p.append(barra_h(ml, yy + dy, x(v) - ml, 15, cor))
            p.append(txt(x(v) + 8, yy + dy + 12, f"{v:.1%}".replace(".", ","), "val"))
        yy += 46
    p.append(txt(20, H - 18,
                 "Prevalência desigual entre grupos torna impossível igualar "
                 "recall, precisão e calibração ao mesmo tempo.", "rot"))
    return svg(W, H, "".join(p), "Equidade por grupo")


def g_vies(vies: dict) -> str:
    """Tres patamares de prevalencia — a decisao de nunca reportar so a nao ponderada."""
    def _prev(pref: str) -> float:
        """Prevalencia de diabetes da estimativa cujo rotulo comeca com `pref`."""
        return next(e["diabetes_%"] for e in vies["prevalencia"]
                    if e["estimativa"].startswith(pref))

    itens = [("arquivo entregue, sem peso", _prev("a "), QUEDA),
             ("BRFSS completo, sem peso", _prev("b "), S2),
             ("BRFSS ponderado (a referência)", _prev("c "), S3)]
    W, H = 760, 250
    ml, mb = 66, 60
    mx = max(v for _, v, _ in itens) * 1.15
    larg = (W - ml - 60) / len(itens) - 40
    ey = Escala(0, mx, H - mb, 84)
    p = [txt(20, 30, "Por que toda prevalência sai em par", "titulo"),
         txt(20, 50, "a mesma pergunta, três respostas — e só uma é populacional",
             "sub")]
    for i, (rot, v, cor) in enumerate(itens):
        cx = ml + i * ((W - ml - 60) / len(itens)) + 20
        p.append(barra_v(cx, ey(v), larg, (H - mb) - ey(v), cor))
        p.append(txt(cx + larg / 2, ey(v) - 10, f"{v:.3f}%".replace(".", ","),
                     "val", "middle"))
        p.append(txt(cx + larg / 2, H - mb + 20, rot[:26], "eixo", "middle"))
    p.append(txt(20, H - 14, "Diferença de +3,262 p.p. — um terço da prevalência. "
                             "Reportar só a primeira é o erro que o projeto evita.",
                 "rot"))
    return svg(W, H, "".join(p), "Prevalência em três medidas")


# ==========================================================================
# a narrativa: uma etapa por bloco
# ==========================================================================

CSS = """
:root{
  --bg:#fcfcfb; --cartao:#fff; --tinta:#0b0b0b; --tinta2:#52514e; --tinta3:#8a8880;
  --linha:#e4e3dc; --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --alerta:#d03b3b;
  --realce:#f2f1ed; --superficie:#fff; --queda:#d03b3b;
}
@media (prefers-color-scheme:dark){
  :root:not([data-tema="claro"]){
    --bg:#141413; --cartao:#1c1c1a; --tinta:#f2f1ec; --tinta2:#b8b6ae; --tinta3:#807e76;
    --linha:#2e2e2b; --realce:#232320; --superficie:#1c1c1a;
    --s1:#5fa0e8; --s2:#f08b5f; --s3:#3fc994; --queda:#e46a6a;
  }
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--tinta);
  font:17px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:0 24px}
a{color:var(--s1)}
h1{font-size:clamp(32px,5.5vw,48px);line-height:1.07;letter-spacing:-.03em;font-weight:690}
h2{font-size:clamp(21px,3.2vw,27px);line-height:1.22;letter-spacing:-.02em;
  font-weight:665;margin-bottom:6px}
p{color:var(--tinta2);max-width:68ch}
p+p{margin-top:12px}
b,strong{color:var(--tinta);font-weight:640}
.hero{padding:70px 0 44px}
.hero .tese{font-size:19px;line-height:1.5;margin-top:20px;border-left:4px solid var(--s1);
  padding-left:20px;max-width:62ch;color:var(--tinta)}
.voltar{display:inline-block;margin-top:26px;font-size:15px;text-decoration:none}

/* --- sumario --- */
.sumario{background:var(--cartao);border:1px solid var(--linha);border-radius:14px;
  padding:22px 26px;margin:34px 0 10px}
.sumario ol{margin:10px 0 0 20px;columns:2;column-gap:34px}
.sumario li{padding:3px 0;font-size:15.5px;color:var(--tinta2);break-inside:avoid}
.sumario a{text-decoration:none}
.sumario a:hover{text-decoration:underline}

/* --- etapa --- */
.etapa{padding:52px 0;border-top:1px solid var(--linha)}
.n{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.08em;
  color:var(--s1);margin-bottom:8px}
.qa{display:grid;grid-template-columns:118px 1fr;gap:10px 18px;margin-top:20px;
  font-size:16px}
.qa dt{color:var(--tinta3);font-size:12px;text-transform:uppercase;
  letter-spacing:.07em;font-weight:660;padding-top:3px}
.qa dd{color:var(--tinta2)}
.qa dd b{color:var(--tinta)}
.tecnica{display:flex;gap:7px;flex-wrap:wrap;margin-top:4px}
.tecnica span{font-size:12.5px;padding:3px 10px;border-radius:99px;
  background:var(--realce);color:var(--tinta2)}
figure{margin-top:26px;background:var(--cartao);border:1px solid var(--linha);
  border-radius:14px;padding:18px 18px 12px;overflow-x:auto}
figure svg{max-width:100%;height:auto;display:block}
figcaption{font-size:14.5px;color:var(--tinta3);margin-top:12px;padding:0 4px 4px;
  max-width:74ch}
figcaption b{color:var(--tinta2)}
.leia{margin-top:16px;font-size:14.5px;color:var(--tinta3)}
.armadilha{background:color-mix(in srgb,var(--alerta) 8%,transparent);
  border-left:3px solid var(--alerta);border-radius:0 8px 8px 0;padding:14px 18px;
  margin-top:20px}
.armadilha p{color:var(--tinta);font-size:15.5px;max-width:70ch}
.armadilha .rot{font-size:12px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--alerta);font-weight:670;display:block;margin-bottom:5px}
footer{padding:44px 0 64px;border-top:1px solid var(--linha);font-size:14px;
  color:var(--tinta3)}
"""


def _etapa(n: int, chave: str, titulo: str, pergunta: str, decisao: str,
           tecnicas: list[str], porque: str, figura: str = "", legenda_fig: str = "",
           armadilha: str = "", doc: str = "") -> str:
    """Um bloco de etapa: pergunta, decisao, tecnica, por que, grafico, armadilha."""
    partes = [f'<section class="etapa" id="{chave}">',
              f'<span class="n">ETAPA {n:02d}</span>',
              f"<h2>{titulo}</h2>",
              '<dl class="qa">',
              f"<dt>Pergunta</dt><dd>{pergunta}</dd>",
              f"<dt>Decisão</dt><dd>{decisao}</dd>",
              '<dt>Técnica</dt><dd><div class="tecnica">'
              + "".join(f"<span>{t}</span>" for t in tecnicas) + "</div></dd>",
              f"<dt>Por quê</dt><dd>{porque}</dd>",
              "</dl>"]
    if figura:
        partes.append(f"<figure>{figura}<figcaption>{legenda_fig}</figcaption></figure>")
    if armadilha:
        partes.append('<div class="armadilha"><span class="rot">A armadilha</span>'
                      f"<p>{armadilha}</p></div>")
    if doc:
        partes.append(f'<p class="leia">Detalhe em {doc}.</p>')
    partes.append("</section>")
    return "".join(partes)


def _doc(nome: str, rotulo: str) -> str:
    """Link para um documento do repositorio."""
    base = ("https://github.com/felipe44776-eseg/data-science-2-eseg-diabetes"
            "/blob/main/docs/")
    return f'<a href="{base}{nome}">{rotulo}</a>'


def montar() -> str:
    """Monta a pagina do metodo a partir dos artefatos e do modelo servido."""
    man = ler("_manifest_ingestao.json", RAIZ / "data" / "raw")["manifest"]
    rel = ler("_relatorio_limpeza.json", RAIZ / "data" / "processed")
    vies = ler("_analise_vies.json", EXT / "brfss2015")
    esc = ler("_escada_modelos.json")
    pu = ler("_frente2_pu.json")
    tc = ler("_trilhaC_escore.json")
    td = ler("_trilhaC_decisao.json")
    eq = ler("_trilhaC_equidade.json")
    f1 = ler("_frente1_expandido.json")
    cau = ler("_causal.json")
    tmp = ler("_validacao_temporal.json")
    ebr = ler("_escore_brasil.json")

    bloco = esc["sem_proxies_de_acesso"]["modelos"]
    custo = tc["comparacao"]["custo_de_remover_o_proxy_de_acesso"]
    y, p = prever_holdout()
    mconf = matriz_de_confusao(y, p)
    curvas = _curva(y, p)
    dez = next((c for c in td["candidatos"]["escore_5_perguntas"]["cobertura"]
                if c["%_testado"] == 10.0),
               td["candidatos"]["escore_5_perguntas"]["cobertura"][0])
    razao_br = ebr["escore_eua_aplicado_cru"]["calibracao"]["razao_previsto_observado"]

    e = []

    e.append(_etapa(
        1, "ingestao", "Os dados não vieram como dados",
        "Como transformar um PDF de 4.374 páginas numa tabela confiável?",
        "Reconstruir cada linha pela <b>coordenada da caixa delimitadora</b> de cada "
        "palavra — agrupar por <code>y</code>, ordenar por <code>x</code> — em vez de "
        "confiar na ordem de leitura.",
        ["PyMuPDF get_text(words)", "agrupamento por faixa de y", "hash SHA-256"],
        "A ordem de leitura de um PDF <b>não é garantida pela especificação</b>: o "
        "texto é uma lista de operadores de desenho, não uma tabela. Extração ingênua "
        "embaralha colunas em silêncio. Resultado: <b>"
        + f"{man['n_linhas']:,}".replace(",", ".") + "</b> linhas, <b>0</b> em quarentena.",
        armadilha="Um extrator que parece funcionar no primeiro parágrafo pode trocar "
                  "colunas na página 3.000 sem erro nenhum. Por isso a verificação não "
                  "foi visual: foi igualdade célula a célula contra a fonte original.",
        doc=_doc("01-diagnostico-dos-dados.md", "docs/01") + " e o ADR 0001"))

    e.append(_etapa(
        2, "limpeza", "Nenhuma linha some em silêncio",
        "O que fazer com linha inválida, duplicada ou com rótulo contraditório?",
        "<b>Marcar, nunca apagar.</b> Sete regras rastreadas; toda remoção vai para "
        "quarentena com o motivo e entra na contagem do relatório.",
        ["validação de domínio antes do downcast", "quarentena com motivo",
         "flags em vez de exclusão"],
        "A base tem <b>" + f"{rel['duplicatas_exatas']:,}".replace(",", ".")
        + "</b> duplicatas exatas e <b>"
        + f"{rel['grupos_alvo_conflitante']:,}".replace(",", ".")
        + "</b> grupos com alvo conflitante. Descartá-las silenciosamente mudaria a "
        "prevalência sem que nada avisasse — e foi assim que o arquivo entregue nasceu "
        "enviesado.",
        doc=_doc("01-diagnostico-dos-dados.md", "docs/01")))

    e.append(_etapa(
        3, "vies", "A limpeza que gerou o arquivo já era uma decisão",
        "O arquivo entregue representa a população?",
        "Baixar o BRFSS original, reconstruir as 22 colunas, provar a identidade — e "
        "só então medir o que a limpeza original fez.",
        ["reconstrução do XPT", "igualdade célula a célula", "pesos _LLCPWT"],
        "A reconstrução bate <b>100,000000%</b> célula a célula. Com isso provado, a "
        "medição do viés é confiável: a prevalência do arquivo superestima a "
        "populacional em <b>+3,262 p.p.</b>, e 73% disso vem de terem descartado as "
        "colunas de peso — não das 187.776 pessoas removidas.",
        figura=g_vies(vies),
        legenda_fig="<b>A decisão que este gráfico sustenta:</b> toda prevalência do "
                    "projeto é reportada em par — não ponderada e ponderada. Sozinha, a "
                    "primeira superestima diabetes em 32,7%.",
        doc=_doc("05-comparacao-brfss-original.md", "docs/05")))

    e.append(_etapa(
        4, "particao", "Partição por hash, nunca aleatória",
        "Como dividir treino e teste sem vazar informação?",
        "Agrupar por <b>hash blake2b do vetor de features</b>, de modo que linhas "
        "idênticas caiam sempre do mesmo lado.",
        ["StratifiedGroupKFold", "blake2b das features", "auditoria de vazamento"],
        "Com <b>" + f"{rel['duplicatas_exatas']:,}".replace(",", ".")
        + "</b> duplicatas exatas, um <code>train_test_split</code> aleatório coloca "
        "cópias da mesma pessoa nos dois lados. Medimos a inflação: <b>0,1% a 1,2%</b> "
        "— pequena. A regra ficou porque é gratuita e defensável, não porque o efeito "
        "seja grande.",
        armadilha="Aqui houve honestidade contra nós mesmos: a previsão era de inflação "
                  "grande. Não era. O documento foi corrigido em vez de a regra ser "
                  "vendida com número inflado.",
        doc="o ADR 0002 e " + _doc("08-modelagem-preditiva.md", "docs/08") + " §2.1"))

    e.append(_etapa(
        5, "metricas", "Acurácia não é reportada em lugar nenhum",
        "Qual métrica mede um modelo com 14% de prevalência?",
        "<b>PR-AUC como primária</b>, mais recall a especificidade fixa, Brier e ECE. "
        "Acurácia é proibida por ADR.",
        ["PR-AUC (Saito &amp; Rehmsmeier)", "recall @ especificidade", "Brier", "ECE"],
        "Responder sempre que a pessoa não tem diabetes acerta <b>84,2%</b>. Qualquer "
        "métrica que premie isso está medindo a prevalência, não o modelo. A curva "
        "precision-recall é sensível à classe rara; a ROC não é.",
        figura=g_roc_pr(curvas),
        legenda_fig="<b>A decisão que este gráfico sustenta:</b> a linha de base da PR "
                    "é a prevalência ("
                    + f"{curvas['prevalencia']:.1%}".replace(".", ",")
                    + "), a da ROC é 50%. Um modelo pode ter ROC excelente e PR "
                    "medíocre — e é a PR que diz quantos dos selecionados serão de "
                    "fato casos.",
        doc="o ADR 0005"))

    e.append(_etapa(
        6, "escada", "Uma escada, não um modelo",
        "Quanto do desempenho vem do algoritmo?",
        "Construir seis degraus, do chute pela prevalência ao gradient boosting "
        "calibrado, e medir o ganho de cada um.",
        ["regra clínica", "logística L2", "spline", "gradient boosting", "isotônica"],
        "Sem a escada não dá para saber se um PR-AUC de <b>"
        + f"{bloco['5_gb_calibrado']['holdout']['pr_auc']:.4f}".replace(".", ",")
        + "</b> é bom. Com ela, dá: o salto grande está entre o chute e a regra "
        "clínica; do modelo linear ao boosting o ganho é modesto. <b>O gargalo é "
        "informação, não algoritmo</b> — recuperar variáveis do XPT rendeu +"
        + f"{f1['comparacao']['ganho_pr_auc_%']}".replace(".", ",") + "% de PR-AUC.",
        figura=g_escada(bloco),
        legenda_fig="<b>A decisão que este gráfico sustenta:</b> parar de procurar "
                    "algoritmo melhor e ir buscar variável perdida.",
        doc=_doc("08-modelagem-preditiva.md", "docs/08")))

    e.append(_etapa(
        7, "calibracao", "Calibrar é requisito, não refinamento",
        "A probabilidade que o modelo devolve significa alguma coisa?",
        "Regressão <b>isotônica</b> fora da amostra (<code>cv=3</code>), com o ECE "
        "medido no holdout intocado. E <b>não</b> usar SMOTE.",
        ["isotônica out-of-fold", "ECE por faixa", "cost-sensitive em vez de SMOTE"],
        "Reponderar a classe rara mantém a ordenação e destrói o nível: medimos o ECE "
        "piorar <b>67×</b> sem a ROC-AUC mudar. É o resultado que van den Goorbergh "
        "et al. (2022) documentam para modelos de risco clínico.",
        figura=g_calibracao(bloco["4_gradient_boosting"]["calibracao_holdout"],
                            bloco["5_gb_calibrado"]["calibracao_holdout"]),
        legenda_fig="<b>A decisão que este gráfico sustenta:</b> as duas curvas têm "
                    "praticamente a mesma ROC-AUC. Só o eixo vertical distingue um "
                    "modelo utilizável de um que mente o nível. Foi a primeira aparição "
                    "do padrão que se repetiria em quatro contextos: <b>a ordem "
                    "transfere, o nível não</b>.",
        doc="o ADR 0004"))

    e.append(_etapa(
        8, "confusao", "Do escore à decisão: onde cortar",
        "Que limiar usar, e quem sobra de fora dele?",
        "Fixar o limiar pela <b>especificidade que o orçamento aguenta</b> ("
        + f"{ESPECIFICIDADE:.0%}" + "), não em 0,5, e mostrar a matriz que resulta.",
        ["limiar por especificidade", "matriz de confusão", "recall operacional"],
        "Com 14% de prevalência, um corte em 0,5 classifica quase todo mundo como "
        "negativo — a matriz vira uma coluna e a acurácia fica ótima. É exatamente o "
        "que o ADR 0005 proíbe. Fixando a especificidade primeiro, o recall que sobra "
        "é <b>" + f"{mconf['recall']:.1%}".replace(".", ",") + "</b> e a precisão <b>"
        + f"{mconf['precisao']:.1%}".replace(".", ",") + "</b>.",
        figura=g_confusao(mconf),
        legenda_fig="<b>A decisão que este gráfico sustenta:</b> a caixa dos falsos "
                    "negativos é o custo humano do limiar, e ela nunca fica vazia. "
                    "Calculada com as <b>tabelas de consulta que a calculadora usa</b>, "
                    "não com um modelo interno — é a matriz do que as pessoas recebem.",
        doc=_doc("16-trilhaC-escore-decisao-equidade.md", "docs/16")))

    e.append(_etapa(
        9, "parcimonia", "Cinco perguntas, e nenhuma exige médico",
        "Qual é o menor instrumento que ainda serve?",
        "Seleção gulosa para dimensionar, escore de pontos inteiros para entregar — e "
        "<b>remover o bloco de acesso inteiro</b>, medindo o custo.",
        ["seleção gulosa", "pontos inteiros", "calibração por faixa"],
        "O escore com exame de colesterol chega a "
        + f"{custo['roc_auc_A']:.4f}".replace(".", ",") + "; sem nenhum marcador de "
        "acesso, " + f"{custo['roc_auc_B']:.4f}".replace(".", ",") + ". Custo: <b>"
        + f"{custo['perda_roc_milesimos']}".replace(".", ",") + " milésimos</b>. Um "
        "instrumento que pergunta se a pessoa já fez exame funciona melhor no papel e "
        "pior na vida — exclui exatamente quem nunca foi rastreado.",
        figura=g_parcimonia(esc["parcimonia"]["curva"],
                            esc["parcimonia"]["teto_referencia"]),
        legenda_fig="<b>A decisão que este gráfico sustenta:</b> a curva satura cedo. "
                    "Poucas perguntas capturam a maior parte do sinal — é o que torna "
                    "um escore de papel defensável, e não uma simplificação preguiçosa.",
        armadilha="Esta curva é <b>otimista</b>: a seleção gulosa escolhe variável "
                  "olhando para o mesmo holdout onde reporta a métrica. Ela serve para "
                  "dimensionar <i>quantas</i> perguntas bastam; o número publicado do "
                  "escore vem de variáveis fixadas a priori, com partição própria.",
        doc=_doc("16-trilhaC-escore-decisao-equidade.md", "docs/16")))

    e.append(_etapa(
        10, "decisao", "O modelo é bom. O programa vale a pena?",
        "Rastrear com o modelo é melhor que rastrear todo mundo?",
        "<b>Análise de curva de decisão</b> (Vickers &amp; Elkin, 2006): benefício "
        "líquido contra as duas estratégias triviais, em toda a faixa de limiar.",
        ["net benefit", "NNS", "custo por caso em 3 cenários"],
        "Um modelo com boa métrica pode não valer como política. A curva de decisão é "
        "a ponte: mostra em que faixa de limiar usar o modelo supera rastrear todos e "
        "rastrear ninguém — e onde não supera.",
        figura=g_decisao(td["candidatos"]["escore_5_perguntas"]["curva_decisao"]),
        legenda_fig="<b>A decisão que este gráfico sustenta:</b> o escore supera as "
                    "duas estratégias triviais em toda a faixa clinicamente plausível "
                    "de limiar. Se não superasse, a métrica não salvaria o programa.",
        doc=_doc("16-trilhaC-escore-decisao-equidade.md", "docs/16") + " §4"))

    e.append(_etapa(
        11, "cobertura", "Traduzir métrica em orçamento",
        "Quantos exames comprar, e quantos casos isso encontra?",
        "Converter o ranking em curva de cobertura, com custo de HbA1c em três "
        "cenários em vez de um número falsamente preciso.",
        ["curva de cobertura", "número necessário a rastrear", "faixa de custo"],
        "Um PR-AUC de 0,45 não entra em reunião de orçamento. <b>Testando 10% da "
        "população você encontra "
        + f"{dez['%_casos_encontrados']:.1f}".replace(".", ",")
        + "% dos diabéticos, a R$ "
        + f"{dez['custo_por_caso_R$'][1]:.0f}" + " por caso</b> — isso entra.",
        figura=g_cobertura(td["candidatos"]["escore_5_perguntas"]["cobertura"]),
        legenda_fig="<b>A decisão que este gráfico sustenta:</b> a diagonal tracejada "
                    "é o rastreamento aleatório. A distância entre a curva e ela é "
                    "exatamente o que o modelo compra.",
        doc=_doc("16-trilhaC-escore-decisao-equidade.md", "docs/16") + " §5"))

    e.append(_etapa(
        12, "equidade", "Não dá para ser justo em todos os sentidos ao mesmo tempo",
        "O modelo trata os grupos igualmente?",
        "Auditar recall, precisão e calibração por grupo com <b>limiar global</b>, e "
        "<b>declarar</b> qual critério o projeto prioriza.",
        ["equalized odds", "impossibilidade de Chouldechova", "reponderação PU"],
        "Quando a prevalência difere entre grupos, igualar recall, precisão e "
        "calibração ao mesmo tempo é <b>matematicamente impossível</b> "
        "(Kleinberg–Mullainathan–Raghavan 2017; Chouldechova 2017). Não existe escolha "
        "neutra: existe escolha declarada. O projeto prioriza calibração e precisão "
        "iguais.",
        figura=g_equidade(eq["observado"]["raca"]["por_grupo"]),
        legenda_fig="<b>A decisão que este gráfico sustenta:</b> taxa de seleção "
                    "desigual é <i>apropriada</i> quando a prevalência é desigual. O "
                    "que não pode diferir é a precisão — ninguém deve ser testado à toa "
                    "mais que os outros.",
        armadilha="Há um agravante que a literatura padrão não cobre: <b>o rótulo é "
                  "enviesado</b>. Usar diagnóstico como proxy de doença tem a mesma "
                  "estrutura do caso de Obermeyer et al. (2019). Por isso a auditoria "
                  "roda duas vezes — no rótulo observado e no corrigido por PU.",
        doc=_doc("16-trilhaC-escore-decisao-equidade.md", "docs/16") + " §6"))

    e.append(_etapa(
        13, "rotulo", "O alvo não é diabetes. É diagnóstico de diabetes.",
        "E quem tem a doença e nunca foi testado?",
        "Tratar o problema como <b>Positive-Unlabeled</b>, ancorando a frequência de "
        "rotulagem no NHANES e reportando a faixa de sensibilidade.",
        ["Elkan-Noto (SCAR)", "SAR", "Best Bin Estimation"],
        "Com <code>c = " + str(pu["premissa"]["c_nhanes"]) + "</code>, a prevalência "
        "verdadeira é <b>14,29%</b> contra 10,67% diagnosticada. Tratar não-rotulado "
        "como negativo treina o modelo a reproduzir o processo de diagnóstico — que é "
        "justamente o que o projeto mostrou ser enviesado.",
        armadilha="Tentamos estimar <code>c</code> só com os dados e publicamos que "
                  "batia com o NHANES na terceira decimal. <b>Era artefato</b> de um "
                  "hiperparâmetro não declarado. Corrigido, o estimador se recusa a "
                  "estimar — não existe região pura de positivos no espaço de "
                  "questionário. A retratação está no documento.",
        doc=_doc("12-frente2-positive-unlabeled.md", "docs/12")))

    e.append(_etapa(
        14, "causal", "Declarar as suposições em vez de escondê-las",
        "Atividade física reduz o risco, ou só está associada?",
        "Publicar o <b>DAG</b>, derivar dele o conjunto de ajuste, rodar refutações — "
        "e quantificar a fragilidade com o <b>E-value</b>.",
        ["critério de backdoor", "mediador vs. colisor", "E-value"],
        "A mesma pergunta dá OR de "
        + f"{cau['efeitos_por_conjunto'][0]['or']:.4f}".replace(".", ",") + " a "
        + f"{cau['efeitos_por_conjunto'][-1]['or']:.4f}".replace(".", ",")
        + " conforme o que se ajusta. O DAG é o que diz qual dos quatro é a pergunta "
        "que se quis fazer. A estimativa sob o DAG é <b>"
        + f"{cau['estimativa_causal_efeito_total']['or']:.4f}".replace(".", ",") + "</b>.",
        armadilha="O efeito <b>sobrevive às três refutações</b> e <b>não sobrevive a "
                  "um confundidor plausível</b>: o E-value é "
                  + f"{cau['e_value']['e_value_estimativa']:.2f}".replace(".", ",")
                  + ", e capacidade funcional prévia é candidata óbvia. Refutação testa "
                  "a especificação; o E-value testa o que está fora dela.",
        doc=_doc("21-camada-causal.md", "docs/21")))

    e.append(_etapa(
        15, "transporte", "Funciona fora de onde nasceu?",
        "O modelo vale para o Brasil? E para hoje?",
        "Testar em <b>Vigitel</b> e no <b>BRFSS 2023</b>, e separar deslocamento de "
        "covariáveis, de rótulo e de conceito.",
        ["covariate/label shift", "concept drift", "recalibração de intercepto"],
        "Em 2023 o modelo perde <b>"
        + f"{tmp['veredito']['perda_roc_milesimos']}".replace(".", ",")
        + " milésimos</b> de ROC-AUC e fica a "
        + f"{tmp['veredito']['distancia_para_o_modelo_nativo_milesimos']}".replace(".", ",")
        + " milésimos de um treinado nativamente — <i>concept drift</i> praticamente "
        "ausente. No Brasil a ordem transfere e o nível não: o escore superestima o "
        "risco em <b>" + f"{(razao_br - 1) * 100:.0f}" + "%</b>.",
        armadilha="Em <b>quatro transposições independentes</b> — arquivo→população, "
                  "EUA→Brasil, 2015→2023, reponderado→calibrado — a assinatura é a "
                  "mesma: a discriminação é robusta, a calibração quebra. AUC é a "
                  "métrica que quase todo mundo reporta e a que menos se quebra.",
        doc=_doc("18-escore-recalibrado-brasil.md", "docs/18") + " e "
            + _doc("22-validacao-temporal.md", "docs/22")))

    titulos = [
        ("ingestao", "PDF vira dado"), ("limpeza", "Nada some em silêncio"),
        ("vies", "A limpeza já era decisão"), ("particao", "Partição por hash"),
        ("metricas", "Por que não acurácia"), ("escada", "A escada de modelos"),
        ("calibracao", "Calibrar é requisito"), ("confusao", "Onde cortar"),
        ("parcimonia", "Cinco perguntas"), ("decisao", "Vale a pena?"),
        ("cobertura", "Métrica vira orçamento"), ("equidade", "Justiça declarada"),
        ("rotulo", "O rótulo mente"), ("causal", "Isso é causal?"),
        ("transporte", "Funciona fora daqui?"),
    ]
    sumario = "".join(f'<li><a href="#{c}">{n:02d}. {t}</a></li>'
                      for n, (c, t) in enumerate(titulos, start=1))

    return ("<!doctype html><html lang=\"pt-BR\"><head>\n"
            "<meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
            "<title>O método, passo a passo · Diabetes BRFSS 2015 · ESEG</title>\n"
            "<meta name=\"description\" content=\"As 15 decisões que estruturam a "
            "análise, cada uma com a técnica empregada e o gráfico que a sustenta: "
            "matriz de confusão, calibração, curva de decisão, equidade.\">\n"
            f"<style>{CSS}</style></head><body>\n"
            "<div class=\"wrap\">\n"
            "<header class=\"hero\">\n"
            "  <h1>O método,<br>passo a passo</h1>\n"
            "  <div class=\"tese\">Quinze decisões, em ordem. Para cada uma: a "
            "<b>pergunta</b> que ela responde, a <b>técnica</b> empregada, o "
            "<b>porquê</b> — e o gráfico que a sustenta. Nenhum gráfico aqui é "
            "decorativo.</div>\n"
            "  <a class=\"voltar\" href=\"../\">← voltar para a página principal</a>\n"
            "  <div class=\"sumario\"><b>As quinze etapas</b>\n"
            f"    <ol>{sumario}</ol>\n"
            "  </div>\n"
            "</header>\n"
            + "".join(e) +
            "\n<footer><p>Página gerada pelo pipeline — todo número e todo gráfico vêm "
            "de um artefato versionado. A matriz de confusão, a ROC e a PR são "
            "calculadas com as tabelas de consulta exportadas para a calculadora, pela "
            "mesma função que a suíte de testes compara contra o JavaScript.<br>"
            "Trabalho acadêmico · Data Science 2 · Projeto 1 · ESEG · "
            "Prof. Marino Catarino.</p></footer>\n"
            "</div>\n</body></html>")


def main() -> None:
    """Grava `reports/metodo/index.html`, publicado em /metodo/ no GitHub Pages."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=SAIDA / "index.html")
    args = ap.parse_args()
    html = montar()
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(html, encoding="utf-8")
    print(f"  {args.saida}  ({len(html) / 1024:.0f} KB, "
          f"{html.count('<section class=')} etapas, "
          f"{html.count('<figure>')} graficos)")


if __name__ == "__main__":
    main()
