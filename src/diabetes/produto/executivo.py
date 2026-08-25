"""Apresentacao executiva — 11 slides, para quem decide e nao vai ler os 25 documentos.

Convive com `deck.py`, que passou a se chamar **apresentacao tecnica**: aquela tem 26
slides e percorre o metodo, as refutacoes e as limitacoes. Esta tem outro publico e
outro contrato: **o que encontramos, quanto vale, e o que da para usar amanha**.

O arco, decidido com o usuario:

    achamos a base  ->  gradientes  ->  matriz de confusao  ->  parcimonia  ->  calculadora

Cada slide responde uma pergunta de quem decide, nao de quem audita. O que nao cabe
aqui — DAG, E-value, retratacoes, invariantes — esta na tecnica, e esta apontada.

Reaproveita o cromo de slide (`CSS`/`JS`) e os graficos ja existentes em vez de
duplicar: mesma geometria de 1280x720, mesma navegacao, mesmo export em PDF.

Uso:
    python -m diabetes.produto.executivo
    # depois: abrir no navegador e Ctrl+P -> "Salvar como PDF" (paisagem, sem margens)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from diabetes.produto.deck import CSS, JS, ler, num, slide, tabela
from diabetes.produto.metodo import (
    g_cobertura,
    g_confusao,
    g_parcimonia,
    matriz_de_confusao,
    prever_holdout,
)
from diabetes.viz.tema import Escala, barra_h, barra_v, legenda, svg, txt

RAIZ = Path(".")
GOLD = RAIZ / "data" / "processed" / "gold"
EXT = RAIZ / "data" / "external"
SAIDA = RAIZ / "reports" / "executivo"

SITE = "felipe44776-eseg.github.io/data-science-2-eseg-diabetes"

S1, S2, S3 = "var(--s1)", "var(--s2)", "var(--s3)"
ALERTA = "var(--queda)"

#: nomes legiveis para o publico executivo — nada de codigo de variavel no slide
NOME = {
    "hipertensao": "pressão alta", "doenca_cardiaca": "doença cardíaca",
    "dificuldade_caminhar": "dificuldade para caminhar", "avc": "AVC",
    "colesterol_alto": "colesterol alto", "fumante": "fumante",
    "exame_colesterol": "já fez exame de colesterol",
    "acesso_saude": "tem plano de saúde",
    "sem_consulta_por_custo": "deixou de consultar por custo",
    "atividade_fisica": "faz atividade física", "frutas": "come frutas",
    "vegetais": "come vegetais", "alcool_excessivo": "bebe em excesso",
}

#: marcadores de deteccao — nao sao fator de risco (invariante 8). Aparecem no
#: grafico com cor de alerta, porque o contraste E o achado do trabalho.
DETECCAO = {"exame_colesterol", "acesso_saude", "sem_consulta_por_custo"}

#: faixas da OMS abreviadas — "obesidade_I/II/III" truncava tudo em "obesidade"
FAIXA_IMC = {
    "baixo_peso": "abaixo", "eutrofico": "normal", "sobrepeso": "sobrepeso",
    "obesidade_I": "obes. I", "obesidade_II": "obes. II", "obesidade_III": "obes. III",
}

#: nomes curtos para o eixo da curva de parcimonia — cabem em 13 caracteres
ROTULO_CURTO = {
    "saude_geral": "saúde", "imc": "IMC", "hipertensao": "pressão alta",
    "colesterol_alto": "colesterol", "idade_faixa": "idade", "sexo": "sexo",
    "alcool_excessivo": "álcool", "doenca_cardiaca": "cardíaca",
    "dificuldade_caminhar": "caminhar", "renda_faixa": "renda",
    "escolaridade": "escolaridade", "fumante": "fumante", "avc": "AVC",
    "atividade_fisica": "atividade", "saude_fisica_dias": "dias ruins",
}


def g_odds(binarias: list[dict], n: int = 8) -> str:
    """Ranking de razao de chances, com os marcadores de deteccao destacados.

    O grafico existe para um contraste especifico: o maior OR da base **nao e** um
    fator de risco, e "ja fez exame de colesterol". Pintar os dois grupos com cores
    diferentes e o que transforma uma tabela de OR no argumento do trabalho.
    """
    itens = sorted(binarias, key=lambda b: -b["B_OR"])[:n]
    W = 900
    H = 104 + len(itens) * 34 + 56
    ml, mr = 300, 130
    mx = max(b["B_OR"] for b in itens)
    x = Escala(0, mx, ml, W - mr)
    p = [txt(20, 32, "O que multiplica a chance de ter diabetes", "titulo"),
         txt(20, 54, "razão de chances na população dos EUA, ponderada · "
                     "1,0 = não muda nada", "sub"),
         legenda(ml, 84, [("fator de risco", S1),
                          ("marcador de acesso ao médico", ALERTA)])]
    yy = 104
    for b in itens:
        det = b["variavel"] in DETECCAO
        rot = NOME.get(b["variavel"], b["variavel"].replace("_", " "))
        p.append(txt(ml - 12, yy + 15, rot, "rot", "end"))
        p.append(barra_h(ml, yy, x(b["B_OR"]) - ml, 20, ALERTA if det else S1))
        p.append(txt(x(b["B_OR"]) + 10, yy + 15,
                     f"{b['B_OR']:.2f}×".replace(".", ","), "val"))
        yy += 34
    p.append(txt(20, H - 30,
                 "O maior valor da tabela não é um fator de risco: é ter ido ao "
                 "médico.", "rot"))
    p.append(txt(20, H - 12,
                 "Quem nunca fez exame não aparece como diabético — aparece como "
                 "saudável.", "rot"))
    return svg(W, H, "".join(p), "Fatores associados a diabetes", escala=1.45)


def g_gradientes(ordinais: list[dict], imc: dict) -> str:
    """Prevalencia por faixa em quatro variaveis — o gradiente que o leigo entende.

    Escolhidas por razao entre extremos: idade (30x), saude autoavaliada (18x), IMC
    (6,3x) e renda (2,7x). Sao as quatro perguntas do escore final que tem gradiente
    visivel, e por isso este grafico e o que justifica o proximo bloco.
    """
    por_nome = {o["variavel"]: o for o in ordinais}
    series = [
        # `_AGEG5YR`: nivel 1 = 18-24, depois faixas de 5 anos a partir de 25.
        # A formula ingenua (18 + 5*(k-1)) erra a partir do nivel 3.
        ("idade", [(f"{18 if int(k) == 1 else 25 + 5 * (int(k) - 2)}+", v)
                   for k, v in list(
                       por_nome["idade_faixa"]["B_prev_por_nivel"].items())[:12:2]]),
        ("saúde autoavaliada", [(r, v) for r, v in zip(
            ["excelente", "muito boa", "boa", "regular", "ruim"],
            por_nome["saude_geral"]["B_prev_por_nivel"].values(), strict=False)]),
        ("IMC", [(FAIXA_IMC.get(r, r), v)
                 for r, v in imc["B_prev_por_faixa_oms"].items()]),
    ]
    W, H = 940, 380
    mt, mb = 96, 92
    larg_bloco = (W - 60) / len(series)
    mx = max(v for _, pares in series for _, v in pares)
    ey = Escala(0, mx, H - mb, mt)
    cores = [S1, S2, S3]
    p = [txt(20, 32, "Onde a prevalência dispara", "titulo"),
         txt(20, 54, "% com diagnóstico de diabetes, por faixa · população dos EUA, "
                     "ponderada", "sub")]
    for v in (0, mx / 2, mx):
        p.append(f'<line x1="40" y1="{ey(v):.1f}" x2="{W - 20}" y2="{ey(v):.1f}" '
                 f'class="grade"/>')
        p.append(txt(34, ey(v) + 4, f"{v:.0f}%", "eixo", "end"))
    for i, (nome, pares) in enumerate(series):
        x0 = 50 + i * larg_bloco
        larg = (larg_bloco - 46) / len(pares) - 6
        p.append(txt(x0, mt - 22, nome, "rot"))
        for j, (rot, v) in enumerate(pares):
            cx = x0 + j * ((larg_bloco - 46) / len(pares))
            p.append(barra_v(cx, ey(v), larg, (H - mb) - ey(v), cores[i]))
            p.append(txt(cx + larg / 2, ey(v) - 8,
                         f"{v:.0f}".replace(".", ","), "val", "middle"))
            p.append(txt(cx + larg / 2, H - mb + 18, str(rot)[:9], "eixo", "middle"))
    p.append(txt(20, H - 42,
                 "Da faixa mais jovem à mais velha, a prevalência multiplica por "
                 "30. Da saúde “excelente” à “ruim”, por 18.", "rot"))
    p.append(txt(20, H - 22,
                 "São gradientes fortes o bastante para caber em cinco perguntas — "
                 "e é isso que o escore explora.", "rot"))
    return svg(W, H, "".join(p), "Gradientes de prevalência", escala=1.3)


def g_bases(bi: dict) -> str:
    """Brasil x EUA nos fatores comuns — a prova de que o achado nao e do arquivo."""
    o = bi["odds_ratio"]
    vs = [v for v in ("hipertensao", "idade_faixa", "imc5", "escolaridade3",
                      "atividade_fisica") if v in o]
    W = 900
    H = 100 + len(vs) * 40 + 50
    ml, mr = 250, 150
    mx = max(max(o[v]["OR_Brasil"], o[v]["OR_EUA"]) for v in vs)
    x = Escala(0, mx, ml, W - mr)
    p = [txt(20, 32, "As duas populações concordam", "titulo"),
         txt(20, 54, "razão de chances no Vigitel (Brasil) e no BRFSS (EUA), "
                     "medidas de forma independente", "sub"),
         legenda(ml, 84, [("Brasil · Vigitel", S3), ("EUA · BRFSS", S1)])]
    yy = 104
    rot = {"hipertensao": "pressão alta", "idade_faixa": "idade (por faixa)",
           "imc5": "IMC (por 5 kg/m²)", "escolaridade3": "escolaridade alta",
           "atividade_fisica": "atividade física"}
    for v in vs:
        p.append(txt(ml - 12, yy + 22, rot.get(v, v), "rot", "end"))
        for k, cor, dy in (("OR_Brasil", S3, 0), ("OR_EUA", S1, 17)):
            p.append(barra_h(ml, yy + dy, x(o[v][k]) - ml, 14, cor))
            p.append(txt(x(o[v][k]) + 8, yy + dy + 12,
                         f"{o[v][k]:.3f}".replace(".", ","), "val"))
        yy += 40
    p.append(txt(20, H - 28,
                 "Pressão alta: 3,136 no Brasil, 3,146 nos EUA. Coincidem na "
                 "terceira casa decimal.", "rot"))
    p.append(txt(20, H - 10,
                 "Duas pesquisas independentes, dois países — o mesmo número.", "rot"))
    return svg(W, H, "".join(p), "Comparação Brasil x EUA", escala=1.45)


def montar() -> str:
    """Monta os 11 slides executivos a partir dos artefatos do pipeline."""
    man = ler("_manifest_ingestao.json", RAIZ / "data" / "raw")["manifest"]
    eda = ler("_eda_comparativa.json")
    esc = ler("_escada_modelos.json")
    tc = ler("_trilhaC_escore.json")
    td = ler("_trilhaC_decisao.json")
    bi = ler("_comparacao_binacional.json", EXT / "vigitel")
    prod = json.loads((RAIZ / "reports" / "produto" / "modelo.json")
                      .read_text(encoding="utf-8"))

    y, p_holdout = prever_holdout()
    mconf = matriz_de_confusao(y, p_holdout)
    cob = td["candidatos"]["escore_5_perguntas"]["cobertura"]
    dez = next((c for c in cob if c["%_testado"] == 10.0), cob[0])
    b = tc["escores"]["B_sem_proxy_acesso"]
    vs = tc["comparacao"]["vs_findrisc"]

    S = []

    # 1 · capa
    S.append(slide("", """
      <h1>Quem os dados de saúde<br>deixam de fora</h1>
      <p class="sub">253.680 respostas · seis bases comparadas · uma calculadora de
      risco que roda em qualquer navegador.</p>
      <div class="rodape-capa">Apresentação executiva · Data Science 2 · Projeto 1 ·
      ESEG<br>Prof. Marino Catarino · a versão técnica tem 26 slides</div>""", "capa"))

    # 2 · o resumo em tres numeros
    S.append(slide("resumo", f"""
      <h2>Em três números</h2>
      <div class="tres">
        <div class="cartao"><h3>Reconstruímos a base original</h3>
          <div class="numerao" style="font-size:44px">100<small>%</small></div>
          <p>de igualdade célula a célula com a pesquisa do CDC — o que nos deixou
          medir o que o arquivo entregue tinha perdido</p></div>
        <div class="cartao"><h3>Encontramos quem falta</h3>
          <div class="numerao" style="font-size:44px">14,3<small>%</small></div>
          <p>é a prevalência real, contra <b>10,7%</b> que aparece como diagnosticada.
          Um em cada quatro diabéticos não sabe</p></div>
        <div class="cartao"><h3>Bastam cinco perguntas</h3>
          <div class="numerao" style="font-size:44px">
            {num(b['metricas']['roc_auc_amostra_propria'], 3)}</div>
          <p>de capacidade de ordenar risco — acima do padrão internacional, e
          nenhuma delas exige ter visto um médico</p></div>
      </div>
      <div class="citacao" style="margin-top:32px">
        Os dados não medem quem <b>tem</b> diabetes.<br>
        Medem quem foi <b>diagnosticado</b>.
      </div>"""))

    # 3 · achamos a base geral
    S.append(slide("a base", f"""
      <h2>Primeiro achamos a base de verdade</h2>
      <div class="duas">
        <div>
          <p>O arquivo do trabalho chegou como um <b>PDF de 4.374 páginas</b> com
          {num(man['n_linhas'])} linhas. Não dava para saber o que ele representava.</p>
          <p style="margin-top:14px">Localizamos a pesquisa original — o
          <b>BRFSS 2015 do CDC</b>, com 441.456 respostas — e reconstruímos as 22
          colunas a partir dela.</p>
          <div class="numerao" style="margin-top:20px">100,000000<small>%</small></div>
          <p class="legenda">das células idênticas. É a mesma base — e agora dá para
          medir o que foi removido dela.</p>
        </div>
        <div class="cartao">
          <h3>O que a comparação revelou</h3>
          <p><b>187.776 pessoas</b> haviam sido descartadas, e as três colunas de peso
          amostral jogadas fora.</p>
          <p style="margin-top:12px">Resultado: o arquivo <b>superestima a
          prevalência em um terço</b> — 13,9% contra 10,7% reais.</p>
          <p style="margin-top:12px"><b>96,3%</b> das pessoas no arquivo já haviam
          feito exame de colesterol, contra <b>77,9%</b> da população. O arquivo é
          uma amostra de quem tem acesso ao sistema de saúde.</p>
        </div>
      </div>"""))

    # 4 · as outras bases concordam
    S.append(slide("as outras bases", f"""
      <h2>E confirmamos em outras cinco</h2>
      <p class="sub">Um achado que aparece em uma base só pode ser defeito da base.
      Buscamos as mesmas perguntas em pesquisas independentes.</p>
      {g_bases(bi)}"""))

    # 5 · gradientes: o que multiplica
    S.append(slide("gradientes", f"""
      <h2>O que aumenta a chance — e a surpresa da lista</h2>
      {g_odds(eda['binarias'])}"""))

    # 6 · gradientes por faixa
    S.append(slide("gradientes", f"""
      {g_gradientes(eda['ordinais'], eda['imc'])}
      <p style="margin-top:10px">Idade e saúde autoavaliada sozinhas já separam
      grupos com <b>30×</b> e <b>18×</b> de diferença. Nenhuma das duas exige
      exame.</p>"""))

    # 7 · matriz de confusao
    S.append(slide("acertamos quanto?", f"""
      <h2>De cada 100 diabéticos, quantos encontramos?</h2>
      <div class="duas">
        <div>{g_confusao(mconf, compacto=True)}</div>
        <div>
          <p>Ajustamos o modelo para <b>errar pouco em quem não tem</b>: de cada 10
          pessoas saudáveis, 9 são corretamente deixadas de fora.</p>
          <p style="margin-top:14px">Com esse ajuste, encontramos
          <b>{num(mconf['recall'] * 100, 1)}%</b> de quem tem diagnóstico. E de cada
          100 pessoas que mandamos testar, <b>{num(mconf['precisao'] * 100, 0)}</b>
          são de fato casos.</p>
          <p style="margin-top:14px">A caixa vermelha —
          <b>{num(mconf['fn'])} pessoas</b> — é quem o modelo deixa passar. Ela nunca
          fica vazia, e é o custo honesto de qualquer limiar.</p>
          <p style="margin-top:14px;font-size:16px">Calculado com a <b>mesma tabela
          que a calculadora usa</b>, não com um modelo interno.</p>
        </div>
      </div>"""))

    # 8 · quantos testes
    S.append(slide("orçamento", f"""
      <h2>Quantos exames comprar</h2>
      <div class="duas">
        <div>{g_cobertura(cob, compacto=True)}</div>
        <div>
          <div class="numerao">{num(dez['%_casos_encontrados'], 1)}<small>%</small></div>
          <p class="legenda">dos diabéticos encontrados testando apenas <b>10%</b>
          da população</p>
          <div class="numerao" style="margin-top:18px;font-size:44px">
            R$ {num(dez['custo_por_caso_R$'][1])}</div>
          <p class="legenda">por caso identificado</p>
          <p style="margin-top:18px">Rastrear às cegas encontraria 10% dos casos ao
          testar 10% da população. O modelo encontra
          <b>{num(dez['%_casos_encontrados'] / 10, 1)}× mais</b> com o mesmo
          orçamento.</p>
        </div>
      </div>"""))

    # 9 · parcimonia
    S.append(slide("quantas perguntas", f"""
      <h2>Não precisa de 60 perguntas</h2>
      {g_parcimonia(esc['parcimonia']['curva'],
                    esc['parcimonia']['teto_referencia'], ROTULO_CURTO,
                    compacto=True)}
      <p style="margin-top:14px">A curva satura cedo: as primeiras perguntas carregam
      quase tudo. Foi o que permitiu reduzir a <b>cinco</b> — e o que separa um
      instrumento aplicável de um modelo que só roda em computador.</p>"""))

    # 10 · as cinco perguntas
    faixas = prod["escore_papel"]["calibracao"]["faixas"]
    S.append(slide("o instrumento", f"""
      <h2>As cinco perguntas</h2>
      <div class="duas">
        <div>
          {tabela(["pergunta", "por que entra"], [
              ["Idade", "prevalência multiplica por 30 entre extremos"],
              ["Peso e altura (IMC)", "gradiente de 6× entre eutrófico e obesidade"],
              ["Como avalia sua saúde", "gradiente de 18× — a mais forte das cinco"],
              ["Tem pressão alta", "razão de chances de 6,8×"],
              ["Sexo", "ajuste fino, 1 ponto"],
          ])}
          <p style="margin-top:16px"><b>Nenhuma exige exame, consulta ou plano de
          saúde.</b> Foi decisão de projeto: incluir “já fez exame de colesterol”
          melhoraria o número no papel e excluiria justamente quem nunca foi
          rastreado.</p>
        </div>
        <div>
          {tabela(["pontos", "risco"], [
              [f"{f['pontos_min']}–{f['pontos_max']}", f"{num(f['risco_%'], 2)}%"]
              for f in faixas], destaque=len(faixas) - 1)}
          <p style="margin-top:14px;font-size:17px">Soma-se de cabeça e lê-se a faixa.
          Capacidade de ordenar risco: <b>{num(vs['escore_B_roc'], 4)}</b> contra
          <b>{num(vs['findrisc_roc'], 4)}</b> do FINDRISC, padrão internacional
          desde 2003 — medido nas mesmas pessoas.</p>
        </div>
      </div>"""))

    # 11 · a calculadora
    S.append(slide("o produto", f"""
      <h2>E uma calculadora que qualquer um abre</h2>
      <div class="duas">
        <div>
          <p><b>{SITE}/calculadora</b></p>
          <p style="margin-top:14px">12 perguntas, resposta imediata: risco estimado,
          posição na população, comparação com três bases e o que mudaria se a
          pessoa mudasse de hábito.</p>
          <p style="margin-top:14px"><b>Roda offline.</b> Não envia dado nenhum para
          lugar nenhum — o modelo inteiro cabe no arquivo, e ele funciona com duplo
          clique, sem internet.</p>
        </div>
        <div class="cartao">
          <h3>Por que este modelo, e não outro</h3>
          <p>Testamos seis, do mais simples ao mais complexo. O escolhido é o que
          <b>explica cada resposta</b>: dá para ver quanto cada pergunta somou no
          risco final.</p>
          <p style="margin-top:12px">Modelos mais opacos não ganharam o suficiente
          para justificar a perda de transparência — e num instrumento de saúde,
          poder explicar o resultado é requisito, não luxo.</p>
          <p style="margin-top:12px">A conta que aparece na tela é <b>a mesma</b> que
          o modelo original faz: verificamos {num(prod['paridade_export']['n'])} casos,
          e a maior diferença foi de 0,00000000000001%.</p>
        </div>
      </div>"""))

    # 12 · fecho
    S.append(slide("o que fica", f"""
      <h2>O que fica</h2>
      <div class="duas">
        <div>
          <h3>O achado</h3>
          <p>O fator com maior razão de chances da base <b>não é um fator de
          risco</b> — é ter feito exame de colesterol. Quem nunca foi ao médico não
          consta como diabético: consta como saudável.</p>
          <p style="margin-top:14px">Um instrumento de rastreamento que exige exame
          prévio <b>exclui exatamente quem mais precisa dele</b>.</p>
        </div>
        <div>
          <h3>O entregável</h3>
          <p>Cinco perguntas que qualquer agente de saúde aplica, sem computador e
          sem exame — e que encontram
          <b>{num(dez['%_casos_encontrados'], 0)}% dos casos</b> testando 10% das
          pessoas.</p>
          <p style="margin-top:14px">Mais a calculadora, os pesos que corrigem o
          arquivo público e 25 documentos abertos.</p>
        </div>
      </div>
      <div class="citacao" style="margin-top:28px">
        Comece por <b>{SITE}</b>
      </div>"""))

    corpo = "".join(
        s.replace('class="slide ', f'data-n="{i + 1}/{len(S)}" class="slide ')
        for i, s in enumerate(S))

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=1280">
<title>Quem os dados de saúde deixam de fora · apresentação executiva · ESEG</title>
<style>{CSS}
/* Os graficos foram desenhados para pagina de relatorio (900px, leitura de mesa).
   Num slide de 1280x720 projetado eles ficavam com texto de 11px ao lado de corpo
   de 19px, e sobrava um terco de slide vazio. `width:100%` sobre o viewBox escala
   tudo junto — a tipografia do grafico cresce na mesma proporcao. */
.slide svg{{width:100%;height:auto;display:block}}
.slide .duas svg{{max-height:430px}}
</style></head><body>
<div class="prog"></div>{corpo}
<div class="ajuda">← → navega · Ctrl+P exporta em PDF (paisagem, sem margens)</div>
<script>{JS}</script></body></html>"""


def main() -> None:
    """Grava `reports/executivo/index.html`, publicado em /executivo/ no Pages."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=SAIDA / "index.html")
    args = ap.parse_args()
    html = montar()
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(html, encoding="utf-8")
    n = html.count('class="slide')
    print(f"  {args.saida}  ({len(html) / 1024:.0f} KB, {n} slides)")
    print("  exportar em PDF: abrir no navegador, Ctrl+P, paisagem, sem margens")


if __name__ == "__main__":
    main()
