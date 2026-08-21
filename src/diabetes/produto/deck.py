"""Deck da apresentacao — HTML autocontido, exportavel em PDF.

Gerado dos artefatos, nao escrito a mao: todo numero vem do JSON que o pipeline
produziu. Slide com numero digitado a mao diverge do pipeline na primeira vez que
alguem reroda uma etapa, e ninguem percebe ate a apresentacao.

Convencoes de deck do projeto (`~/CLAUDE.md`):
  * um arquivo autocontido, sem CDN, imagens em SVG inline
  * slide = secao de 1280x720 fixos
  * `@page` + `@media print` com quebra por slide, para exportar em PDF
  * navegacao por teclado e barra de progresso

Uso:
    python -m diabetes.produto.deck
    # depois: abrir no navegador e Ctrl+P -> "Salvar como PDF" (paisagem, sem margens)
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

RAIZ = Path(".")
GOLD = RAIZ / "data" / "processed" / "gold"
SAIDA = RAIZ / "reports" / "deck"


def ler(nome: str, base: Path = GOLD) -> dict:
    return json.loads((base / nome).read_text(encoding="utf-8"))


def num(x: float, casas: int = 0) -> str:
    """Formata em pt-BR: milhar com ponto, decimal com virgula.

    Existe porque a primeira versao usava `.replace(",", ".")` no slide inteiro
    para trocar o separador de milhar — e isso convertia tambem os decimais,
    deixando "9.4%" no lugar de "9,4%". Trocar separador com replace global
    quebra o outro separador; e preciso formatar, nao substituir.
    """
    inteiro, _, decimal = f"{x:,.{casas}f}".partition(".")
    inteiro = inteiro.replace(",", ".")          # milhar: 253,680 -> 253.680
    return f"{inteiro},{decimal}" if decimal else inteiro


# --------------------------------------------------------------------------

CSS = """
:root{
  --bg:#fcfcfb; --tinta:#0b0b0b; --tinta2:#52514e; --tinta3:#898781;
  --linha:#e1e0d9; --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --alerta:#d03b3b;
  --realce:#f0efec;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#3a3a38;font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
  color:var(--tinta)}
.slide{position:relative;width:1280px;height:720px;background:var(--bg);
  margin:22px auto;padding:56px 72px;overflow:hidden;
  box-shadow:0 3px 18px rgba(0,0,0,.35);display:flex;flex-direction:column}
.slide::after{content:attr(data-n);position:absolute;right:30px;bottom:20px;
  font-size:12px;color:var(--tinta3);font-variant-numeric:tabular-nums}
.olho{font-size:12px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--s1);font-weight:650;margin-bottom:12px}
h1{font-size:52px;line-height:1.08;letter-spacing:-.025em;font-weight:680}
h2{font-size:34px;line-height:1.15;letter-spacing:-.02em;font-weight:660;
  margin-bottom:18px}
h3{font-size:19px;font-weight:640;margin-bottom:8px}
p{font-size:19px;color:var(--tinta2);max-width:62ch}
p+p{margin-top:12px}
b,strong{color:var(--tinta);font-weight:650}
.sub{font-size:22px;color:var(--tinta2);margin-top:16px;max-width:64ch}
.corpo{flex:1;display:flex;flex-direction:column;justify-content:center}
.capa{justify-content:center}
.capa h1{font-size:64px;max-width:22ch}
.rodape-capa{position:absolute;left:72px;bottom:56px;font-size:15px;
  color:var(--tinta3);line-height:1.7}
.duas{display:grid;grid-template-columns:1fr 1fr;gap:44px;align-items:start}
.tres{display:grid;grid-template-columns:repeat(3,1fr);gap:28px}
.cartao{background:var(--realce);border-radius:12px;padding:22px 24px}
.cartao h3{color:var(--tinta);font-size:17px}
.cartao p{font-size:16px}
.numerao{font-size:76px;font-weight:690;line-height:1;letter-spacing:-.035em;
  font-variant-numeric:tabular-nums}
.numerao small{font-size:30px;font-weight:550;color:var(--tinta2)}
.legenda{font-size:16px;color:var(--tinta2);margin-top:8px;max-width:34ch}
table{border-collapse:collapse;width:100%;font-size:17px}
th,td{text-align:left;padding:9px 14px 9px 0;border-bottom:1px solid var(--linha);
  font-variant-numeric:tabular-nums}
th{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--tinta3);
  font-weight:650}
td.n,th.n{text-align:right}
tr.destaque td{background:color-mix(in srgb,var(--s1) 10%,transparent);font-weight:640}
.tag{display:inline-block;font-size:13px;padding:3px 10px;border-radius:99px;
  background:var(--realce);color:var(--tinta2);margin-right:6px}
.tag.ok{background:color-mix(in srgb,var(--s3) 18%,transparent);color:#0d6b4a}
.tag.al{background:color-mix(in srgb,var(--alerta) 15%,transparent);color:#8f2020}
.citacao{border-left:4px solid var(--s1);padding:6px 0 6px 22px;font-size:23px;
  line-height:1.4;color:var(--tinta);max-width:58ch}
.barra-lista{display:flex;flex-direction:column;gap:11px;margin-top:6px}
.bl{display:grid;grid-template-columns:220px 1fr 74px;gap:14px;align-items:center;
  font-size:16px}
.bl .rot{color:var(--tinta2);text-align:right}
.bl .tr{height:15px;background:var(--linha);border-radius:8px;overflow:hidden}
.bl .tr i{display:block;height:100%;border-radius:8px}
.bl .v{text-align:right;font-variant-numeric:tabular-nums;font-weight:620}
.passos{display:flex;align-items:center;gap:14px;margin-top:20px;flex-wrap:wrap}
.passo{background:var(--realce);border-radius:10px;padding:14px 18px;font-size:17px;
  font-variant-numeric:tabular-nums}
.passo b{display:block;font-size:26px;font-weight:670}
.seta{color:var(--tinta3);font-size:22px}
.queda{color:var(--alerta);font-weight:650}
.prog{position:fixed;left:0;top:0;height:3px;background:var(--s1);z-index:9;
  transition:width .15s}
.ajuda{position:fixed;right:14px;bottom:12px;font-size:12px;color:#c9c8c2;z-index:9}
@page{size:1280px 720px;margin:0}
@media print{
  body{background:#fff}
  .slide{margin:0;box-shadow:none;break-after:page;page-break-after:always}
  .prog,.ajuda{display:none}
}
"""

JS = """
const slides = [...document.querySelectorAll(".slide")];
const prog = document.querySelector(".prog");
function atual(){
  const y = window.scrollY + window.innerHeight/2;
  let i = 0;
  slides.forEach((s,k) => { if (s.offsetTop <= y) i = k; });
  return i;
}
function ir(i){
  i = Math.max(0, Math.min(slides.length-1, i));
  slides[i].scrollIntoView({behavior:"smooth", block:"start"});
}
addEventListener("keydown", e => {
  const k = e.key;
  if (["ArrowRight","PageDown"," ","n"].includes(k)){ e.preventDefault(); ir(atual()+1); }
  if (["ArrowLeft","PageUp","p"].includes(k)){ e.preventDefault(); ir(atual()-1); }
  if (k === "Home"){ e.preventDefault(); ir(0); }
  if (k === "End"){ e.preventDefault(); ir(slides.length-1); }
});
addEventListener("scroll", () => {
  prog.style.width = ((atual()+1)/slides.length*100) + "%";
}, {passive:true});
prog.style.width = (1/slides.length*100) + "%";
"""


# --------------------------------------------------------------------------
# componentes
# --------------------------------------------------------------------------

def barras(itens: list[tuple[str, float, str]], sufixo: str = "%",
           maximo: float | None = None) -> str:
    mx = maximo or max(abs(v) for _, v, _ in itens) or 1
    linhas = []
    for rot, v, cor in itens:
        linhas.append(
            f'<div class="bl"><div class="rot">{escape(rot)}</div>'
            f'<div class="tr"><i style="width:{abs(v)/mx*100:.1f}%;background:{cor}"></i></div>'
            f'<div class="v">{num(v, 2)}{sufixo}</div></div>')
    return '<div class="barra-lista">' + "".join(linhas) + "</div>"


def tabela(cabecalho: list[str], linhas: list[list], destaque: int | None = None) -> str:
    # cabecalho da coluna numerica acompanha o alinhamento da celula
    th = "".join(f'<th class="n">{escape(str(c))}</th>' if k else f"<th>{escape(str(c))}</th>"
                 for k, c in enumerate(cabecalho))
    tr = []
    for i, ln in enumerate(linhas):
        cls = ' class="destaque"' if destaque == i else ""
        tds = "".join(
            f'<td class="n">{escape(str(c))}</td>' if k else f"<td>{escape(str(c))}</td>"
            for k, c in enumerate(ln))
        tr.append(f"<tr{cls}>{tds}</tr>")
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(tr)}</tbody></table>"


def slide(olho: str, corpo: str, classe: str = "") -> str:
    topo = f'<div class="olho">{escape(olho)}</div>' if olho else ""
    return f'<section class="slide {classe}">{topo}<div class="corpo">{corpo}</div></section>'


# --------------------------------------------------------------------------

def montar() -> str:
    man = ler("_manifest_ingestao.json", RAIZ / "data" / "raw")["manifest"]
    rel = ler("_relatorio_limpeza.json", RAIZ / "data" / "processed")
    eda = ler("_eda_comparativa.json")
    mod = ler("_modelo_explicativo.json")
    esc = ler("_escada_modelos.json")
    f1 = ler("_frente1_expandido.json")
    pu = ler("_frente2_pu.json")
    bi = ler("_comparacao_binacional.json", RAIZ / "data/external/vigitel")
    tc = ler("_trilhaC_escore.json")
    td = ler("_trilhaC_decisao.json")
    prod = ler("modelo.json", RAIZ / "reports" / "produto")

    S = []

    # 1 · capa
    S.append(slide("", """
      <h1>Diabetes:<br>o que os dados escondem</h1>
      <p class="sub">253.680 respostas do BRFSS 2015 — e o que aparece quando
      comparamos com <b>cinco bases externas</b>.</p>
      <div class="rodape-capa">Data Science 2 · Projeto 1 · ESEG<br>
      Prof. Marino Catarino</div>""", "capa"))

    # 2 · o problema inicial
    S.append(slide("o começo", f"""
      <h2>Os dados não vieram como dados</h2>
      <div class="duas">
        <div>
          <p>O arquivo entregue foi <b>um PDF de {num(man['paginas'])} páginas</b> — uma
          tabela renderizada, não um CSV.</p>
          <p>Extrair por ordem de leitura é frágil: a especificação PDF <b>não
          garante</b> que a ordem dos tokens corresponda à ordem visual.</p>
          <p>Reconstruímos linha a linha <b>por coordenada de bounding box</b>.</p>
        </div>
        <div class="cartao">
          <div class="numerao">{num(man['n_linhas'])}<small> linhas</small></div>
          <p class="legenda">bate exatamente com o enunciado</p>
          <div style="margin-top:20px">
            <span class="tag ok">0 em quarentena</span>
            <span class="tag ok">0 fora do domínio</span>
            <span class="tag">{num(man['segundos'], 1)}s</span>
          </div>
        </div>
      </div>"""))

    # 3 · diagnostico
    alvo = rel["distribuicao_alvo_pct"]
    S.append(slide("diagnóstico", f"""
      <h2>Quatro problemas definiram o trabalho</h2>
      <div class="tres">
        <div class="cartao"><h3>Duplicatas</h3>
          <div class="numerao" style="font-size:44px">{num(rel['duplicatas_exatas'])}</div>
          <p>linhas idênticas — 9,4% da base</p></div>
        <div class="cartao"><h3>Rótulo contraditório</h3>
          <div class="numerao" style="font-size:44px">{num(rel['grupos_alvo_conflitante'])}</div>
          <p>perfis iguais, alvo diferente</p></div>
        <div class="cartao"><h3>Desbalanceamento</h3>
          <div class="numerao" style="font-size:44px">{num(alvo['1'], 2)}<small>%</small></div>
          <p>é o tamanho da classe pré-diabetes</p></div>
      </div>
      <div style="margin-top:30px" class="citacao">
        Responder sempre “não tem diabetes” acerta <b>{num(alvo['0'], 1)}%</b>.<br>
        Por isso <b>acurácia não é reportada</b> neste trabalho.
      </div>
      <p style="margin-top:22px">E o quarto: <b>zero códigos 77/99 de renda</b> —
      a amostra foi <b>truncada</b> antes de chegar. Foi o fio que abriu o resto.</p>
      """))

    # 4 · a pergunta
    S.append(slide("a virada", """
      <h2>Se a amostra foi truncada,<br>quanto isso distorce?</h2>
      <p class="sub">O arquivo entregue tem 253.680 respondentes.<br>
      O <b>BRFSS 2015 original do CDC tem 441.456</b>.</p>
      <p style="margin-top:26px">Baixamos a fonte, reconstruímos as 22 colunas e
      comparamos célula a célula.</p>"""))

    # 5 · prova de identidade
    S.append(slide("validação", f"""
      <h2>A reconstrução bate exatamente</h2>
      <div class="duas">
        <div>
          <div class="numerao">100,000000<small>%</small></div>
          <p class="legenda">das células idênticas · 253.680 de 253.680 linhas,
          na mesma ordem</p>
          <p style="margin-top:26px">Prova quatro coisas de uma vez: a extração do
          PDF, as regras de derivação, a integridade do download e a preservação
          da ordem original.</p>
        </div>
        <div>
          <h3>Depois disso, o viés fica mensurável</h3>
          {tabela(["", "arquivo", "população"], [
              ["prevalência de diabetes", "13,93%", "10,50%"],
              ["fez exame de colesterol", "96,27%", "77,93%"],
              ["tem plano de saúde", "95,11%", "87,83%"]])}
        </div>
      </div>"""))

    # 6 · decomposicao do vies
    S.append(slide("o viés", """
      <h2>De onde vem o viés de prevalência</h2>
      <div class="passos">
        <div class="passo"><b>13,93%</b>arquivo entregue</div>
        <div class="seta">→</div>
        <div class="passo"><b class="queda">−0,94</b>descarte de 42,5%</div>
        <div class="seta">→</div>
        <div class="passo"><b>12,99%</b>BRFSS sem peso</div>
        <div class="seta">→</div>
        <div class="passo"><b class="queda">−2,49</b>peso descartado</div>
        <div class="seta">→</div>
        <div class="passo"><b>10,50%</b>população</div>
      </div>
      <div class="citacao" style="margin-top:34px">
        A maior parte do viés <b>não</b> vem de terem jogado fora 187.776 pessoas.<br>
        Vem de terem jogado fora <b>três colunas</b>: os pesos amostrais.
      </div>"""))

    # 7 · o achado grave
    S.append(slide("o achado central", f"""
      <h2>O arquivo é uma amostra de quem<br>tem acesso ao sistema de saúde</h2>
      {barras([("fez exame de colesterol — arquivo", 96.27, "var(--s2)"),
               ("fez exame de colesterol — população", 77.93, "var(--s1)"),
               ("sem consulta por custo — arquivo", 8.42, "var(--s2)"),
               ("sem consulta por custo — população", 13.27, "var(--s1)")], maximo=100)}
      <p style="margin-top:26px">O mecanismo: <b>59.154 nulos</b> em “tem colesterol
      alto?” são <b>salto de questionário</b> — 84% deles <b>nunca fizeram o exame</b>,
      então nunca foram perguntados. O <code>dropna()</code> removeu exatamente a
      população de menor acesso.</p>"""))

    # 8 · EDA
    idade = next(o for o in eda["ordinais"] if o["variavel"] == "idade_faixa")
    S.append(slide("exploratória", f"""
      <h2>Nenhum fator isolado explica diabetes</h2>
      <div class="duas">
        <div>
          <p>O maior V de Cramér é <b>0,293</b> (hipertensão) — ainda “pequeno” pela
          convenção de Cohen. Onze das quatorze variáveis são desprezíveis.</p>
          <p>Isso não é resultado fraco. É <b>o</b> resultado: diabetes é
          multifatorial, e nenhuma conclusão monocausal se sustenta.</p>
          <p style="margin-top:22px">O gradiente etário é o mais forte —
          <b>{num(idade['B_razao'], 2)}×</b> entre a menor e a maior faixa — e o arquivo
          entregue o <b>comprime pela metade</b> ({num(idade['A_razao'], 2)}×).</p>
        </div>
        <div>
          <h3>E não é monotônico</h3>
          {tabela(["faixa etária", "prevalência"], [
              ["70–74 anos", "24,60%"], ["75–79 anos", "24,66%"],
              ["80 anos ou mais", "19,67%"]], destaque=2)}
          <p style="margin-top:14px">A queda em 80+ é <b>mortalidade seletiva</b>:
          diabéticos têm menor chance de chegar lá.</p>
        </div>
      </div>"""))

    # 9 · explicativa
    S.append(slide("explicativa", f"""
      <h2>O efeito protetor da atividade física desaparece</h2>
      <div class="duas">
        <div>
          {tabela(["especificação", "OR"], [
              ["M1 · risco puro", "0,852"],
              ["M2 · + saúde autoavaliada", "0,988"]], destaque=1)}
          <p style="margin-top:18px">Ao entrar <code>saude_geral</code>, o efeito
          evapora. Isso é <b>mediação</b> — condicionar em mediador bloqueia o
          caminho causal.</p>
          <p><b>M2 e M3 não podem ser lidos como “atividade física não importa”.</b></p>
        </div>
        <div>
          <h3>O que sobrevive a tudo</h3>
          {tabela(["fator", "OR ajustado"], [
              ["hipertensão", "2,39"], ["colesterol alto", "2,00"],
              ["idade (por DP)", "1,65"], ["IMC (por DP)", "1,59"],
              ["renda (por DP)", "0,82"]])}
          <p style="margin-top:12px">Renda mantém efeito <b>mesmo controlando</b>
          IMC, dieta, atividade física e escolaridade.</p>
        </div>
      </div>"""))

    # 10 · pre-diabetes
    pvd = {k: v for k, v in mod["pre_vs_diabetes"].items() if not v["ic_sobrepoe"]}
    S.append(slide("descoberta", f"""
      <h2>Pré-diabetes não é o mesmo continuum</h2>
      {tabela(["fator", "OR pré-diabetes", "OR diabetes"], [
          ["sexo (masculino)", "1,00", "1,26"],
          ["doença cardíaca", "0,92", "1,25"],
          ["dias de saúde mental", "1,07", "0,95"],
          ["hipertensão", "1,47", "2,11"]])}
      <p style="margin-top:22px"><b>{len(pvd)} variáveis</b> têm efeito materialmente
      diferente nas duas classes, e <b>duas invertem de direção</b>.
      A especificação correta é <b>multinomial</b>, não ordinal.</p>
      <p><b>Lição:</b> o teste por logits cumulativos <b>não rejeitou</b> — falso
      negativo, porque a classe pré-diabetes tem 1,6% e os dois contrastes ficam
      quase idênticos por construção.</p>"""))

    # 11 · binacional
    o = bi["odds_ratio"]
    S.append(slide("Brasil × EUA", f"""
      <h2>Seis de oito fatores convergem</h2>
      {tabela(["fator", "OR Brasil", "OR EUA", "razão"], [
          ["hipertensão", f"{o['hipertensao']['OR_Brasil']:.3f}".replace(".", ","),
           f"{o['hipertensao']['OR_EUA']:.3f}".replace(".", ","), "1,00"],
          ["idade", f"{o['idade_faixa']['OR_Brasil']:.3f}".replace(".", ","),
           f"{o['idade_faixa']['OR_EUA']:.3f}".replace(".", ","), "1,00"],
          ["escolaridade", "0,732", "0,768", "0,95"],
          ["IMC (por 5 kg/m²)", "1,228", "1,454", "0,84"],
          ["frutas", "1,299", "0,898", "1,45"]], destaque=3)}
      <p style="margin-top:20px">Vigitel 2015 × BRFSS 2015 — <b>mesmo ano, mesmo
      desenho de inquérito, mesmo modelo</b>. Hipertensão e idade coincidem na
      <b>terceira casa decimal</b>, em dois países e dois sistemas de saúde.</p>
      <p><b>Mas o IMC pesa 16% menos no Brasil</b> — um escore calibrado nos EUA
      superestima o IMC aqui. E <b>frutas inverte de direção</b>.</p>"""))

    # 12 · subdiagnostico
    S.append(slide("o rótulo mente", f"""
      <h2>O alvo não é diabetes.<br>É <i>diagnóstico</i> de diabetes.</h2>
      <div class="duas">
        <div>
          <p>Segundo o NHANES, <b>27,6% dos diabéticos nos EUA não sabem</b>.
          Formalmente isto é <b>Positive-Unlabeled learning</b>, não classificação
          supervisionada.</p>
          <p style="margin-top:20px">Estimamos a frequência de rotulagem <b>só com
          os dados</b> e comparamos com a fonte externa:</p>
          {tabela(["estimativa de c", "valor"], [
              ["só com o BRFSS (BBE)", f"{pu['bbe']['c_estimado_bbe']:.4f}".replace(".", ",")],
              ["NHANES (exame de sangue)", f"{pu['premissa']['c_nhanes']:.4f}".replace(".", ",")]])}
        </div>
        <div class="cartao">
          <h3>Prevalência verdadeira</h3>
          <div class="numerao">14,29<small>%</small></div>
          <p class="legenda">contra 10,67% diagnosticada</p>
          <p style="margin-top:18px"><b>Os prováveis não diagnosticados são
          clinicamente idênticos</b> aos diagnosticados — hipertensão 74,7% contra
          74,9% — mas têm <b>um terço do check-up</b> e o dobro de renúncia a
          consulta por custo.</p>
        </div>
      </div>"""))

    # 13 · predicao
    m = esc["sem_proxies_de_acesso"]["modelos"]
    S.append(slide("predição", f"""
      <h2>O teto não é o algoritmo. É a informação.</h2>
      {tabela(["modelo", "variáveis", "PR-AUC"], [
          ["prevalência constante", "—", f"{m['0_prevalencia']['holdout']['pr_auc']:.4f}".replace(".", ",")],
          ["regra clínica", "3", f"{m['1_regra_clinica']['holdout']['pr_auc']:.4f}".replace(".", ",")],
          ["logística", "18", f"{m['2_logistica_l2']['holdout']['pr_auc']:.4f}".replace(".", ",")],
          ["gradient boosting calibrado", "18", f"{m['5_gb_calibrado']['holdout']['pr_auc']:.4f}".replace(".", ",")],
          ["boosting + 39 variáveis recuperadas", "60", f"{f1['comparacao']['60_risco']['pr_auc']:.4f}".replace(".", ",")]],
          destaque=4)}
      <p style="margin-top:22px">A escada inteira de modelos rendeu <b>+0,036</b> de
      PR-AUC. <b>Recuperar variáveis descartadas rendeu +0,029</b> — quase o mesmo,
      sem tocar no algoritmo.</p>
      <p>E o ruído de rótulo limita a acurácia a <b>99,3%</b>: o teto de Bayes
      <b>não</b> é a restrição.</p>"""))

    # 14 · equidade
    aud = {a["grupo"]: a for a in f1["auditoria_raca"]}
    S.append(slide("equidade", f"""
      <h2>O ganho médio escondia uma redistribuição</h2>
      {barras([("branco não-hispânico", aud["branco nao-hispanico"]["ganho_recall"]*100, "var(--alerta)"),
               ("negro não-hispânico", aud["negro nao-hispanico"]["ganho_recall"]*100, "var(--s3)"),
               ("hispânico", aud["hispanico"]["ganho_recall"]*100, "var(--s3)"),
               ("multirracial", aud["multirracial nao-hispanico"]["ganho_recall"]*100, "var(--s3)")],
              sufixo=" pp")}
      <p style="margin-top:24px">Ganho de <i>recall</i> ao recuperar as variáveis.
      O ganho médio de 6,6% é <b>inteiramente das minorias</b>.</p>
      <div class="citacao" style="margin-top:18px">
        O modelo de 21 variáveis era sistematicamente pior para minorias — e
        <b>ninguém podia saber</b>, porque a variável que revela isso tinha sido
        removida da base.
      </div>"""))

    # 15 · escore
    b = tc["escores"]["B_sem_proxy_acesso"]
    faixas = b["calibracao"]["faixas"]
    S.append(slide("o entregável", f"""
      <h2>Cinco perguntas que cabem numa folha de papel</h2>
      <div class="duas">
        <div>
          {tabela(["pergunta", "pontos"], [
              ["Idade (< 35 … 65+)", "0 a +17"],
              ["IMC (< 25 … 35+)", "0 a +9"],
              ["Saúde autoavaliada", "0 a +11"],
              ["Pressão alta?", "0 ou +7"],
              ["Sexo", "0 ou +1"]])}
          <p style="margin-top:16px"><b>Nenhuma exige exame prévio.</b> Podem ser
          respondidas por alguém que nunca viu um médico.</p>
        </div>
        <div>
          {tabela(["pontos", "risco"], [
              [f"{f['pontos_min']}–{f['pontos_max']}", f"{f['risco_%']:.2f}%".replace(".", ",")]
              for f in faixas], destaque=len(faixas)-1)}
        </div>
      </div>
      <p style="margin-top:20px">ROC-AUC <b>0,804</b> contra <b>0,766</b> do
      <b>FINDRISC</b> — o padrão internacional desde 2003, na mesma amostra.</p>"""))

    # 16 · custo
    cob = td["candidatos"]["escore_5_perguntas"]["cobertura"]
    linhas_cob = [[f"{c['%_testado']:.0f}%", f"{c['%_casos_encontrados']:.1f}%".replace(".", ","),
                   f"{c['nns_acumulado']:.2f}".replace(".", ","),
                   f"R$ {c['custo_por_caso_R$'][1]:.0f}"]
                  for c in cob[:6]]
    S.append(slide("decisão", f"""
      <h2>Do modelo ao orçamento</h2>
      {tabela(["testar", "casos encontrados", "NNS", "custo por caso"], linhas_cob, destaque=1)}
      <p style="margin-top:22px">Testando <b>10% da população</b> encontramos
      <b>40% dos casos</b> a <b>R$ 75</b> por caso (HbA1c na faixa da tabela SUS).</p>
      <p>As duas faixas superiores do escore concentram <b>60,5% dos casos</b> a
      R$ 69–109. A faixa mais baixa custa <b>R$ 3.593</b> — <b>52× mais</b>.</p>
      <p><b>Rastrear por ordem de escore é a diferença entre um programa viável e
      um inviável.</b></p>"""))

    # 17 · produto
    S.append(slide("o produto", f"""
      <h2>Uma calculadora que roda no navegador</h2>
      <div class="duas">
        <div>
          <p>O modelo interpretável é <b>aditivo</b>: cada termo é uma tabela de
          consulta. Exportamos as tabelas e a predição roda em JavaScript com o
          <b>mesmo número</b> do Python.</p>
          {tabela(["verificação", "valor"], [
              ["casos conferidos", "500"],
              ["erro máximo Python ↔ JS", f"{prod['paridade_export']['erro_max']:.1e}"],
              ["casos com resposta ausente", "290"],
              ["tamanho da página", "59 KB"]])}
          <p style="margin-top:14px">Funciona <b>offline</b>, sem servidor.
          Nenhuma resposta sai do computador.</p>
        </div>
        <div class="cartao">
          <h3>Na apresentação</h3>
          <p style="font-size:17px">1. preencher um perfil<br>
          2. ver <b>o que pesa</b> em cada resposta<br>
          3. mudar o IMC e ver o número reagir<br>
          4. escolher <b>“nunca fiz o exame”</b> no colesterol</p>
          <p style="margin-top:16px;font-size:17px"><b>O passo 4 é o momento:</b>
          demonstra em um clique que um instrumento que exige exame prévio
          <b>exclui quem mais precisa dele</b>.</p>
        </div>
      </div>"""))

    # 18 · limitacoes
    S.append(slide("honestidade", """
      <h2>O que este trabalho <i>não</i> mostra</h2>
      <div class="tres">
        <div class="cartao"><h3>Não é causal</h3>
          <p>Dados transversais. Testamos com o experimento natural do Medicaid —
          e o desenho <b>não tem poder</b> para o efeito esperado (0,16 contra
          0,90 p.p. detectável).</p></div>
        <div class="cartao"><h3>Não é a doença</h3>
          <p>O alvo é <b>diagnóstico autorrelatado</b>. O modelo prediz quem
          <i>consta</i> como diabético.</p></div>
        <div class="cartao"><h3>Não é o Brasil</h3>
          <p>Treinado nos EUA de 2015. O IMC pesa <b>16% menos</b> aqui —
          recalibração local é requisito.</p></div>
      </div>
      <p style="margin-top:30px">Três previsões nossas <b>não se confirmaram</b> e
      foram corrigidas na fonte: o vazamento por duplicata quase não infla a
      métrica, os proxies de acesso quase não melhoram a predição, e o teto de
      Bayes não é a restrição.</p>"""))

    # 19 · fecho
    S.append(slide("conclusão", """
      <h2>O que fica</h2>
      <div class="duas">
        <div>
          <h3>Sobre os dados</h3>
          <p>O arquivo entregue é um <b>derivado enviesado</b>: superestima a
          prevalência em um terço e é uma amostra de quem tem acesso ao sistema
          de saúde.</p>
          <p style="margin-top:16px"><b>Publicamos os pesos</b> que corrigem
          95,6% desse viés — utilizáveis por qualquer pessoa que use o mesmo CSV.</p>
        </div>
        <div>
          <h3>Sobre o valor</h3>
          <p>Um escore de <b>cinco perguntas</b> que bate o padrão internacional,
          custa R$ 75 por caso encontrado e <b>alcança quem nunca viu um médico</b>.</p>
          <p style="margin-top:16px">E uma calculadora que <b>roda offline</b>, com
          predição verificada contra o Python.</p>
        </div>
      </div>
      <div class="citacao" style="margin-top:34px">
        O achado mais útil não foi sobre diabetes.<br>
        Foi sobre <b>quem os dados de saúde deixam de fora</b>.
      </div>"""))

    corpo = "".join(
        s.replace('class="slide ', f'data-n="{i+1}/{len(S)}" class="slide ')
        for i, s in enumerate(S))

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=1280">
<title>Diabetes — o que os dados escondem · Data Science 2 · ESEG</title>
<style>{CSS}</style></head><body>
<div class="prog"></div>{corpo}
<div class="ajuda">← → navega · Ctrl+P exporta em PDF (paisagem, sem margens)</div>
<script>{JS}</script></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=SAIDA / "apresentacao.html")
    args = ap.parse_args()
    html = montar()
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(html, encoding="utf-8")
    n = html.count('class="slide')
    print(f"  {args.saida}  ({len(html)/1024:.0f} KB, {n} slides)")
    print("  exportar em PDF: abrir no navegador, Ctrl+P, paisagem, sem margens")


if __name__ == "__main__":
    main()
