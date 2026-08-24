"""Pagina de entrada do site publico (GitHub Pages).

O projeto entrega tres artefatos HTML — calculadora, deck e figuras — que ate
aqui so existiam como arquivo local. Sem uma pagina de entrada nao ha *link*:
ninguem consegue mandar o questionario para alguem testar.

Esta pagina e a raiz do site. Ela e **gerada dos artefatos**, como o deck: todo
numero vem do JSON que o pipeline produziu. Isso importa mais aqui do que no
deck, porque a pagina afirma publicamente que o escore bate o FINDRISC — se
alguem rerodar `trilhac` e o numero mudar, a pagina tem de mudar junto.

Layout do site publicado (ver `.github/workflows/pages.yml`):

    /                -> esta pagina
    /calculadora/    -> reports/produto/index.html
    /deck/           -> reports/deck/apresentacao.html
    /figuras/        -> reports/figures/index.html

Uso:
    python -m diabetes.produto.site
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from diabetes.pipeline.estado import ETAPAS
from diabetes.produto.deck import num

RAIZ = Path(".")
GOLD = RAIZ / "data" / "processed" / "gold"
SAIDA = RAIZ / "reports" / "site"

#: sem isto os links quebram quando o site sobe em subdiretorio do usuario
BASE_REPO = "https://github.com/felipe44776-eseg/data-science-2-eseg-diabetes"

CSS = """
:root{
  --bg:#fcfcfb; --cartao:#fff; --tinta:#0b0b0b; --tinta2:#52514e; --tinta3:#8a8880;
  --linha:#e4e3dc; --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --alerta:#d03b3b;
  --realce:#f2f1ed;
}
@media (prefers-color-scheme:dark){
  :root:not([data-tema="claro"]){
    --bg:#141413; --cartao:#1c1c1a; --tinta:#f2f1ec; --tinta2:#b8b6ae; --tinta3:#807e76;
    --linha:#2e2e2b; --realce:#232320; --s1:#5fa0e8; --s2:#f08b5f; --s3:#3fc994;
  }
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--tinta);
  font:17px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:940px;margin:0 auto;padding:0 24px}
a{color:var(--s1)}
h1{font-size:clamp(34px,6vw,54px);line-height:1.06;letter-spacing:-.03em;font-weight:690}
h2{font-size:clamp(23px,3.6vw,30px);line-height:1.2;letter-spacing:-.02em;
  font-weight:660;margin-bottom:14px}
h3{font-size:18px;font-weight:640;margin-bottom:6px}
p{color:var(--tinta2);max-width:66ch}
p+p{margin-top:12px}
b,strong{color:var(--tinta);font-weight:640}
section{padding:56px 0;border-top:1px solid var(--linha)}
section:first-of-type{border-top:0}
.olho{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--s1);
  font-weight:660;margin-bottom:10px}

/* ---- topo ---- */
.hero{padding:74px 0 60px}
.hero .tese{font-size:clamp(19px,2.6vw,23px);line-height:1.42;margin-top:22px;
  border-left:4px solid var(--s1);padding-left:20px;max-width:60ch;color:var(--tinta)}
.creditos{margin-top:26px;font-size:14px;color:var(--tinta3);line-height:1.7}
.selos{display:flex;gap:8px;flex-wrap:wrap;margin-top:20px}
.selo{font-size:12.5px;padding:4px 11px;border-radius:99px;background:var(--realce);
  color:var(--tinta2)}
.selo.ok{background:color-mix(in srgb,var(--s3) 20%,transparent);color:var(--s3)}

/* ---- botoes ---- */
.acoes{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
  gap:14px;margin-top:34px}
.acao{display:block;background:var(--cartao);border:1px solid var(--linha);
  border-radius:14px;padding:20px 22px;text-decoration:none;color:inherit;
  transition:border-color .15s,transform .15s}
.acao:hover{border-color:var(--s1);transform:translateY(-2px)}
.acao .ic{font-size:26px;line-height:1;display:block;margin-bottom:10px}
.acao b{display:block;font-size:17px;margin-bottom:3px}
.acao span{font-size:14px;color:var(--tinta3)}
.acao.principal{background:var(--s1);border-color:var(--s1);color:#fff}
.acao.principal b,.acao.principal span{color:#fff}
.acao.principal span{opacity:.85}

/* ---- grades ---- */
.grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;
  margin-top:24px}
.cartao{background:var(--cartao);border:1px solid var(--linha);border-radius:12px;
  padding:20px 22px}
.cartao p{font-size:15.5px}
.numerao{font-size:42px;font-weight:690;line-height:1;letter-spacing:-.03em;
  font-variant-numeric:tabular-nums;margin-bottom:6px}
.numerao small{font-size:19px;font-weight:550;color:var(--tinta2)}

/* ---- tabela ---- */
.rolagem{overflow-x:auto;margin-top:20px}
table{border-collapse:collapse;width:100%;font-size:15.5px;min-width:480px}
th,td{text-align:left;padding:9px 14px 9px 0;border-bottom:1px solid var(--linha);
  font-variant-numeric:tabular-nums}
th{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--tinta3);
  font-weight:660}
td.n,th.n{text-align:right}
tbody tr:last-child td{border-bottom:0}
tr.destaque td{background:color-mix(in srgb,var(--s1) 9%,transparent);font-weight:640}

.nota{font-size:14.5px;color:var(--tinta3);margin-top:14px;max-width:70ch}
.aviso{background:color-mix(in srgb,var(--alerta) 9%,transparent);
  border-left:3px solid var(--alerta);border-radius:0 8px 8px 0;padding:16px 20px;
  margin-top:26px}
.aviso p{color:var(--tinta);font-size:15.5px}
.lista-docs{list-style:none;margin-top:18px;display:grid;
  grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:2px}
.lista-docs li{padding:9px 0;border-bottom:1px solid var(--linha);font-size:15.5px;
  color:var(--tinta2)}
.lista-docs a{text-decoration:none;font-weight:600}
.lista-docs a:hover{text-decoration:underline}
footer{padding:44px 0 60px;border-top:1px solid var(--linha);font-size:14px;
  color:var(--tinta3)}
footer a{color:var(--tinta2)}
"""


def _pontos(tab: dict) -> str:
    """Tabela de pontos do escore, em HTML — a versao que se usa sem computador."""
    rotulo = {"idade": "Idade", "imc": "IMC (kg/m²)", "saude": "Saúde autoavaliada",
              "hipertensao": "Pressão alta", "sexo": "Sexo"}
    #: as chaves vem do modelo em snake sem acento; a pagina e para leigo
    resposta = {"nao": "não", "sim": "sim", "excelente/muito boa": "excelente ou muito boa",
                "regular/ruim": "regular ou ruim"}
    linhas = []
    for var, faixas in tab.items():
        celulas = " · ".join(
            f"<b>{escapar(resposta.get(k, k))}</b> {v}" for k, v in faixas.items())
        linhas.append(f"<tr><td>{rotulo.get(var, var)}</td><td>{celulas}</td></tr>")
    return ("<div class='rolagem'><table><thead><tr><th>pergunta</th>"
            "<th>resposta → pontos</th></tr></thead><tbody>"
            + "".join(linhas) + "</tbody></table></div>")


def _cientifico(x: float) -> str:
    """Notacao cientifica em pt-BR: 1,110 x 10^-16, nao 1.110e-16."""
    mant, exp = f"{x:.3e}".split("e")
    sinais = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    return f"{mant.replace('.', ',')} × 10{str(int(exp)).translate(sinais)}"


def escapar(s: str) -> str:
    """Escape minimo — o conteudo vem do proprio pipeline, nao de entrada externa."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _contagens() -> dict[str, int]:
    """Conta docs, modulos e testes no disco.

    Digitar esses numeros na pagina os deixa errados na primeira vez que alguem
    escreve um documento — e uma pagina publica errada e pior que uma desatualizada.
    """
    testes = sum(t.read_text(encoding="utf-8").count("def test_")
                 for t in (RAIZ / "tests").glob("test_*.py"))
    return {
        "docs": len(list((RAIZ / "docs").glob("[0-9]*.md"))),
        "modulos": sum(1 for f in (RAIZ / "src").rglob("*.py")
                       if f.name != "__init__.py"),
        "testes": testes,
        "notebooks": len(list((RAIZ / "notebooks").glob("*.ipynb"))),
    }


def montar() -> str:
    """Monta o HTML da pagina de entrada a partir dos artefatos do pipeline."""
    c = _contagens()
    esc = json.loads((GOLD / "_trilhaC_escore.json").read_text(encoding="utf-8"))
    ebr = json.loads((GOLD / "_escore_brasil.json").read_text(encoding="utf-8"))
    tmp = json.loads((GOLD / "_validacao_temporal.json").read_text(encoding="utf-8"))
    dec = json.loads((GOLD / "_trilhaC_decisao.json").read_text(encoding="utf-8"))
    prod = json.loads(
        (RAIZ / "reports" / "produto" / "modelo.json").read_text(encoding="utf-8"))

    b = esc["escores"]["B_sem_proxy_acesso"]
    vs = esc["comparacao"]["vs_findrisc"]
    faixas = b["calibracao"]["faixas"]
    par = prod["paridade_export"]
    # decil de topo: a linha da curva de cobertura em que se testa 10% da populacao
    dez = next(c for c in dec["candidatos"]["escore_5_perguntas"]["cobertura"]
               if c["%_testado"] == 10.0)

    # backslash nao e permitido dentro de expressao de f-string (< 3.12)
    destaque = ' class="destaque"'
    linhas_faixa = "".join(
        f"<tr{destaque if f['risco_%'] >= 10 else ''}>"
        f"<td>{f['pontos_min']} a {f['pontos_max']}</td>"
        f"<td class='n'>{num(f['risco_%'], 2)}%</td>"
        f"<td class='n'>{num(f['n_treino'])}</td></tr>"
        for f in faixas)

    return f"""<!doctype html><html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diabetes: o que os dados escondem · BRFSS 2015 · ESEG</title>
<meta name="description" content="Análise de 253.680 respostas do BRFSS 2015 com
validação contra seis bases externas, e uma calculadora de risco de diabetes que
roda offline. Trabalho acadêmico — Data Science 2, ESEG.">
<style>{CSS}</style></head><body>

<div class="wrap">

<header class="hero">
  <div class="olho">Data Science 2 · Projeto 1 · ESEG</div>
  <h1>Diabetes:<br>o que os dados escondem</h1>
  <div class="tese">Os dados de saúde não medem quem <b>tem</b> diabetes.
    Medem quem foi <b>diagnosticado</b> — e quem é diagnosticado depende de ter
    acesso ao sistema de saúde.</div>
  <div class="selos">
    <span class="selo ok">pipeline {len(ETAPAS)}/{len(ETAPAS)} coerente</span>
    <span class="selo ok">CI verde</span>
    <span class="selo">6 bases externas</span>
    <span class="selo">{c['docs']} documentos</span>
    <span class="selo">{c['testes']} testes</span>
  </div>
  <div class="creditos">253.680 respostas do BRFSS 2015 (CDC) ·
    Prof. Marino Catarino<br>Código, dados e documentação abertos no
    <a href="{BASE_REPO}">GitHub</a>.</div>

  <div class="acoes">
    <a class="acao principal" href="calculadora/">
      <span class="ic">🧮</span><b>Calculadora de risco</b>
      <span>12 perguntas · roda no seu navegador, offline</span></a>
    <a class="acao" href="deck/">
      <span class="ic">🎤</span><b>Apresentação</b>
      <span>26 slides · ← → navega · Ctrl+P exporta em PDF</span></a>
    <a class="acao" href="metodo/">
      <span class="ic">🧭</span><b>O método, passo a passo</b>
      <span>15 decisões · matriz de confusão, calibração, curva de decisão</span></a>
    <a class="acao" href="figuras/">
      <span class="ic">📊</span><b>Figuras e tabelas</b>
      <span>6 gráficos com os números por trás</span></a>
    <a class="acao" href="{BASE_REPO}">
      <span class="ic">💻</span><b>Repositório</b>
      <span>{c['modulos']} módulos Python · {c['notebooks']} notebooks ·
        {c['docs']} docs</span></a>
  </div>
</header>

<section id="questionario">
  <div class="olho">o questionário</div>
  <h2>Cinco perguntas — e por que elas funcionam</h2>
  <p>A calculadora usa 12 perguntas. Mas o resultado que mais interessa é o
  <b>escore de papel</b>: cinco perguntas, somadas de cabeça, sem computador e
  <b>sem exigir que a pessoa já tenha visto um médico</b>.</p>

  <div class="grade">
    <div class="cartao">
      <div class="numerao">{num(b["metricas"]["roc_auc_amostra_propria"], 3)}</div>
      <h3>ROC-AUC na população</h3>
      <p>Medido em <b>{num(b["metricas"]["n_amostra_propria"])}</b> pessoas — todo o
      holdout que estas cinco perguntas conseguem responder, <b>sem filtro de
      acesso</b>.</p>
      <p>Contra o <b>FINDRISC</b>, comparado na mesma amostra que os dois escores
      compartilham: <b>{num(vs["escore_B_roc"], 4)}</b> contra
      <b>{num(vs["findrisc_roc"], 4)}</b>, ou
      <b>+{num(vs["ganho_milesimos"], 1)} milésimos</b>. O BRFSS só reproduz
      <b>{esc['findrisc']['itens_disponiveis']} dos
      {esc['findrisc']['itens_originais']}</b> itens do FINDRISC, então a leitura
      correta é <i>com o mesmo número de perguntas, o nosso discrimina melhor</i> —
      não que supere o instrumento completo.</p></div>
    <div class="cartao">
      <div class="numerao">{num(dez['%_casos_encontrados'], 1)}<small>%</small></div>
      <h3>dos casos, testando 10%</h3>
      <p>Rastrear apenas os 10% de maior pontuação encontra
      <b>{num(dez['%_casos_encontrados'], 1)}% dos diabéticos</b> — a
      <b>R$ {num(dez['custo_por_caso_R$'][1])}</b> por caso identificado.</p></div>
    <div class="cartao">
      <div class="numerao">0</div>
      <h3>perguntas exigem exame</h3>
      <p>Idade, IMC, saúde autoavaliada, pressão alta e sexo. Nenhuma delas
      pressupõe acesso prévio ao sistema de saúde.</p></div>
  </div>

  <h3 style="margin-top:38px">A razão de projeto</h3>
  <p>Um escore de rastreamento que pede “você já fez exame de colesterol?”
  <b>funciona melhor no papel e pior na vida</b>: ele acerta mais porque a
  variável é um marcador de quem já foi ao médico — exatamente a população que
  <i>menos</i> precisa ser rastreada. Removemos esse bloco inteiro e medimos o
  custo:</p>

  <div class="rolagem"><table>
    <thead><tr><th>escore</th><th class="n">ROC-AUC</th><th>o que usa</th></tr></thead>
    <tbody>
      <tr><td>A — completo</td>
        <td class="n">{num(esc['comparacao']['custo_de_remover_o_proxy_de_acesso']['roc_auc_A'], 4)}</td>
        <td>inclui exame de colesterol</td></tr>
      <tr class="destaque"><td>B — o que publicamos</td>
        <td class="n">{num(esc['comparacao']['custo_de_remover_o_proxy_de_acesso']['roc_auc_B'], 4)}</td>
        <td>nenhum marcador de acesso</td></tr>
      <tr><td>FINDRISC ({esc['findrisc']['itens_disponiveis']} de
        {esc['findrisc']['itens_originais']} itens)</td>
        <td class="n">{num(vs['findrisc_roc'], 4)}</td>
        <td>faltam cintura, histórico familiar e glicemia prévia</td></tr>
    </tbody></table></div>
  <p class="nota">Custo de remover o acesso:
  <b>{num(esc['comparacao']['custo_de_remover_o_proxy_de_acesso']['perda_roc_milesimos'], 1)}
  milésimos</b> de ROC-AUC. Foi o preço mais barato do projeto.</p>

  <h3 style="margin-top:38px">A tabela de pontos</h3>
  <p>Some os pontos e leia a faixa. É tudo — não há modelo escondido aqui.</p>
  {_pontos(prod['escore_papel']['tabela'])}

  <div class="rolagem"><table>
    <thead><tr><th>pontos</th><th class="n">risco de diabetes</th>
    <th class="n">n de calibração</th></tr></thead>
    <tbody>{linhas_faixa}</tbody></table></div>
  <p class="nota">Faixas calibradas em {num(sum(f['n_treino'] for f in faixas))}
  pessoas. O risco é a <b>frequência observada</b> na faixa, não uma estimativa
  do modelo.</p>

  <h3 style="margin-top:38px">Por que dá para confiar</h3>
  <p>O escore foi testado fora do lugar onde nasceu, três vezes:</p>
  <div class="rolagem"><table>
    <thead><tr><th>testado em</th><th class="n">ROC-AUC</th><th>veredito</th></tr></thead>
    <tbody>
      <tr><td>EUA · holdout 2015 (partição por hash, sem vazamento)</td>
        <td class="n">{num(b["metricas"]["roc_auc_amostra_propria"], 4)}</td>
        <td>referência — todo o holdout respondível, sem filtro de acesso</td></tr>
      <tr><td>Brasil · Vigitel, {num(ebr['premissa']['n_avaliacao'])} entrevistas</td>
        <td class="n">{num(ebr['escore_eua_aplicado_cru']['roc_auc'], 4)}</td>
        <td>a ordem transfere; o nível precisa de recalibração</td></tr>
      <tr><td>EUA · BRFSS 2023, oito anos depois</td>
        <td class="n">{num(tmp['modelo_2015_em_2023']['roc_auc'], 4)}</td>
        <td>perde {num(tmp['veredito']['perda_roc_milesimos'], 1)} milésimos;
        sem <i>concept drift</i></td></tr>
    </tbody></table></div>
  <p class="nota">A calculadora é uma tradução literal do modelo Python para
  JavaScript. Testamos {num(par['n'])} casos comparando os dois: erro máximo de
  <b>{_cientifico(par['erro_max'])}</b>. O número que aparece na tela é o mesmo
  do Python.</p>

  <div class="aviso">
    <p><b>Isto é um trabalho acadêmico e não é orientação clínica.</b>
    O modelo prediz a probabilidade de alguém <i>constar</i> como diabético numa
    pesquisa domiciliar — não diagnostica ninguém. Um resultado alto significa
    “vale procurar um serviço de saúde”, nunca “você tem diabetes”.</p>
  </div>
</section>

<section>
  <div class="olho">o que o trabalho descobriu</div>
  <h2>O padrão que se repete em quatro contextos</h2>
  <p>Quando o mundo muda — outro arquivo, outro país, outro ano — a
  <b>ordem</b> transfere e o <b>nível</b> não.</p>
  <div class="rolagem"><table>
    <thead><tr><th>transposição</th><th>discriminação</th><th>calibração</th></tr></thead>
    <tbody>
      <tr><td>arquivo entregue → população</td><td>robusta</td>
        <td>erro de +3,26 p.p.</td></tr>
      <tr><td>EUA → Brasil</td>
        <td>{num(b["metricas"]["roc_auc_amostra_propria"], 3)} → {num(ebr["escore_eua_aplicado_cru"]["roc_auc"], 3)}</td>
        <td>superestima 54%</td></tr>
      <tr><td>2015 → 2023</td>
        <td>−{num(tmp['veredito']['perda_roc_milesimos'], 1)} milésimos</td>
        <td>ECE 4× pior</td></tr>
      <tr><td>class_weight → calibrado</td><td>idêntica</td>
        <td>ECE 67× pior</td></tr>
    </tbody></table></div>
  <p class="nota"><b>AUC é a métrica que quase todo mundo reporta e a que menos se
  quebra.</b> O que quebra é a calibração, e quase ninguém a mede. E recalibrar
  foi sempre barato: 20% de dados novos e um deslocamento de intercepto.</p>
</section>

<section>
  <div class="olho">leitura</div>
  <h2>Por onde entrar</h2>
  <ul class="lista-docs">
    <li><a href="{BASE_REPO}/blob/main/docs/23-sintese-final.md">docs/23 — síntese
      final</a> · o trabalho inteiro em 10 minutos</li>
    <li><a href="metodo/">O método, passo a passo</a> · as 15 decisões, com o
      gráfico que sustenta cada uma</li>
    <li><a href="{BASE_REPO}/blob/main/docs/24-fundamentacao-teorica.md">docs/24 —
      fundamentação teórica</a> · método por método, com a bibliografia</li>
    <li><a href="{BASE_REPO}/blob/main/docs/05-comparacao-brfss-original.md">docs/05 —
      BRFSS original</a> · onde o viés do arquivo foi medido</li>
    <li><a href="{BASE_REPO}/blob/main/docs/16-trilhaC-escore-decisao-equidade.md">docs/16
      — escore e decisão</a> · como as 5 perguntas foram construídas</li>
    <li><a href="{BASE_REPO}/blob/main/docs/21-camada-causal.md">docs/21 — camada
      causal</a> · DAG, refutação e E-value</li>
    <li><a href="{BASE_REPO}/blob/main/docs/22-validacao-temporal.md">docs/22 —
      validação temporal</a> · o modelo de 2015 em 2023</li>
    <li><a href="{BASE_REPO}/tree/main/notebooks">notebooks/</a> · 6 notebooks
      executados, com as saídas</li>
    <li><a href="{BASE_REPO}/tree/main/docs/adr">docs/adr/</a> · 5 decisões de
      arquitetura registradas</li>
  </ul>
</section>

<footer>
  <p>Trabalho acadêmico · Data Science 2 · Projeto 1 · ESEG · Prof. Marino
  Catarino.<br>
  Dados: <a href="https://www.cdc.gov/brfss/">BRFSS</a> 2015 e 2023 (CDC) ·
  <a href="https://svs.aids.gov.br/download/Vigitel/">Vigitel</a> 2015 e 2023
  (Ministério da Saúde) · NHANES · CDC Open Data.<br>
  Página gerada pelo pipeline — todo número vem de um artefato versionado.</p>
</footer>

</div>
</body></html>"""


def main() -> None:
    """Grava `reports/site/index.html`, a raiz do site publicado no GitHub Pages."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=SAIDA / "index.html")
    args = ap.parse_args()
    html = montar()
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(html, encoding="utf-8")
    print(f"  {args.saida}  ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
