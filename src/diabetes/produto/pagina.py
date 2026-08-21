"""Produto — monta a pagina autocontida a partir do modelo exportado.

O JSON do modelo e **embutido** no HTML: o arquivo resultante nao faz nenhuma
requisicao, funciona offline e pode ser aberto por duplo clique. Isso e requisito
de apresentacao — nao da para depender de rede na hora.

A funcao de predicao em JavaScript e a traducao literal de
`exportar.prever_do_json`, e a paridade foi verificada antes do export
(erro maximo 1,1e-16).

Uso:
    python -m diabetes.produto.pagina
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SAIDA = Path("reports/produto")

# --------------------------------------------------------------------------

CSS = """
:root{color-scheme:light dark;
  --bg:#f9f9f7; --card:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --ink3:#898781;
  --linha:#e1e0d9; --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --alerta:#d03b3b;
  --campo:#fff; --sombra:0 1px 3px rgba(11,11,11,.06)}
@media (prefers-color-scheme:dark){:root{
  --bg:#0d0d0d; --card:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --ink3:#898781;
  --linha:#2c2c2a; --s1:#3987e5; --s2:#d95926; --s3:#199e70; --alerta:#e66767;
  --campo:#232322; --sombra:0 1px 3px rgba(0,0,0,.3)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1120px;margin:0 auto;padding:32px 20px 72px}
header{margin-bottom:28px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:-.02em}
.lead{color:var(--ink2);margin:0;max-width:65ch}
.aviso{margin:18px 0 0;padding:12px 16px;border-left:3px solid var(--s2);
  background:var(--card);border-radius:0 8px 8px 0;font-size:14px;color:var(--ink2)}
.grade{display:grid;grid-template-columns:1fr 420px;gap:28px;align-items:start}
@media(max-width:940px){.grade{grid-template-columns:1fr}}
.cartao{background:var(--card);border:1px solid var(--linha);border-radius:12px;
  padding:22px;box-shadow:var(--sombra)}
.cartao+.cartao{margin-top:18px}
h2{font-size:15px;margin:0 0 16px;letter-spacing:.04em;text-transform:uppercase;
  color:var(--ink3);font-weight:600}
.abas{display:flex;gap:6px;margin-bottom:20px;background:var(--bg);
  padding:4px;border-radius:10px;border:1px solid var(--linha)}
.abas button{flex:1;padding:9px 12px;border:0;background:transparent;color:var(--ink2);
  font:inherit;font-size:14px;border-radius:7px;cursor:pointer}
.abas button[aria-selected=true]{background:var(--card);color:var(--ink);
  font-weight:600;box-shadow:var(--sombra)}
.campo{margin-bottom:20px}
.campo label{display:block;font-size:14px;font-weight:500;margin-bottom:7px}
.campo .nota{font-size:12px;color:var(--ink3);margin:5px 0 0}
select,input[type=number]{width:100%;padding:9px 11px;font:inherit;font-size:15px;
  background:var(--campo);color:var(--ink);border:1px solid var(--linha);border-radius:8px}
select:focus,input:focus{outline:2px solid var(--s1);outline-offset:1px}
.dupla{display:grid;grid-template-columns:1fr 1fr auto;gap:10px;align-items:end}
.imc-valor{font-size:13px;color:var(--ink2);white-space:nowrap;padding-bottom:10px;
  font-variant-numeric:tabular-nums}
.resultado{position:sticky;top:20px}
.numero{font-size:56px;font-weight:650;line-height:1;letter-spacing:-.03em;
  font-variant-numeric:tabular-nums}
.numero span{font-size:26px;font-weight:500;color:var(--ink2)}
.faixa-txt{font-size:15px;color:var(--ink2);margin:8px 0 0}
.barra{height:9px;background:var(--linha);border-radius:5px;overflow:hidden;margin:6px 0 3px}
.barra i{display:block;height:100%;border-radius:5px;transition:width .25s}
.comp{margin:20px 0 0}
.comp .linha{display:grid;grid-template-columns:1fr 54px;gap:10px;align-items:center;
  font-size:13px;margin-bottom:9px}
.comp .rot{color:var(--ink2)}
.comp .val{text-align:right;font-variant-numeric:tabular-nums;color:var(--ink)}
.wf{margin-top:4px}
.wf .item{display:grid;grid-template-columns:150px 1fr 52px;gap:9px;align-items:center;
  font-size:13px;margin-bottom:7px}
.wf .rot{color:var(--ink2);text-align:right;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.wf .eixo{position:relative;height:15px}
.wf .eixo::before{content:"";position:absolute;left:50%;top:0;bottom:0;width:1px;
  background:var(--linha)}
.wf .bar{position:absolute;top:2px;height:11px;border-radius:3px}
.wf .val{text-align:right;font-variant-numeric:tabular-nums;font-size:12px;color:var(--ink2)}
.cf{margin-top:4px}
.cf .item{display:flex;justify-content:space-between;gap:12px;font-size:14px;
  padding:9px 0;border-bottom:1px solid var(--linha)}
.cf .item:last-child{border:0}
.cf b{font-variant-numeric:tabular-nums;white-space:nowrap}
.baixa{color:var(--s3)} .sobe{color:var(--alerta)}
.pontos{font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
th,td{text-align:left;padding:6px 8px 6px 0;border-bottom:1px solid var(--linha);
  font-variant-numeric:tabular-nums}
th{color:var(--ink3);font-weight:600;font-size:12px;text-transform:uppercase;
  letter-spacing:.03em}
tr.ativa td{background:color-mix(in srgb,var(--s1) 12%,transparent);font-weight:600}
footer{margin-top:44px;padding-top:22px;border-top:1px solid var(--linha);
  font-size:13px;color:var(--ink3)}
footer b{color:var(--ink2)}
.metricas{display:flex;gap:24px;flex-wrap:wrap;margin-bottom:14px}
.metricas div{font-size:13px}
.metricas b{display:block;font-size:19px;color:var(--ink);font-variant-numeric:tabular-nums}
@media print{body{background:#fff}.abas,.aviso{display:none}
  .grade{grid-template-columns:1fr}.cartao{break-inside:avoid;box-shadow:none}}
"""

JS = r"""
const M = MODELO;
const $ = s => document.querySelector(s);

/* --- predicao: traducao literal de exportar.prever_do_json --------------
   O EBM e aditivo e cada termo e uma tabela de consulta sobre faixas.
   Paridade com o sklearn verificada no export: erro maximo 1,1e-16. */
function indice(v, cortes){
  if (v === null || v === undefined || Number.isNaN(v)) return 0;  // faixa "ausente"
  let i = 1;
  for (const c of cortes){ if (v < c) break; i++; }
  return i;
}
function prever(linha){
  let total = M.ebm.intercepto;
  const contrib = [];
  for (const t of M.ebm.termos){
    const forma = t.forma;
    let plano = 0;
    t.variaveis.forEach((v, k) => {
      let i = indice(linha[v], t.cortes[k]);
      if (i > forma[k] - 1) i = forma[k] - 1;
      plano = plano * forma[k] + i;
    });
    const s = t.scores[plano];
    total += s;
    contrib.push({termo: t.nome, vars: t.variaveis, s});
  }
  return {p: 1 / (1 + Math.exp(-total)), contrib};
}

/* --- escore de papel --------------------------------------------------- */
function faixaIdade(a){ return a<35?"<35":a<45?"35-44":a<55?"45-54":a<65?"55-64":"65+"; }
function faixaImc(b){ return b<25?"<25":b<30?"25-29":b<35?"30-34":"35+"; }
function faixaSaude(g){ return g<=2?"excelente/muito boa":g==3?"boa":"regular/ruim"; }
function escorePapel(l){
  const t = M.escore_papel.tabela;
  const p = (t.idade[faixaIdade(l._AGE80)]||0) + (t.imc[faixaImc(l._BMI5/100)]||0)
          + (t.saude[faixaSaude(l.GENHLTH)]||0)
          + (t.hipertensao[l._RFHYPE5==2?"sim":"nao"]||0)
          + (t.sexo[l.SEX==1?"masculino":"feminino"]||0);
  const f = M.escore_papel.calibracao.faixas;
  let alvo = f[0];
  for (const x of f){ if (p >= x.pontos_min) alvo = x; }
  return {pontos: p, faixa: alvo};
}

/* --- percentil populacional -------------------------------------------- */
function percentil(p){
  const t = M.percentis;
  for (let i=0;i<t.length;i++) if (p <= t[i].risco) return t[i].percentil;
  return 100;
}

/* --- formulario --------------------------------------------------------- */
const estado = {};
function montarFormulario(){
  const alvo = $("#form");
  M.perguntas.forEach(q => {
    const d = document.createElement("div"); d.className = "campo";
    if (q.tipo === "imc"){
      d.innerHTML = `<label>${q.rotulo}</label>
        <div class="dupla">
          <div><input type="number" id="peso" value="78" min="30" max="250" step="0.5"
            aria-label="peso em quilos"><div class="nota">peso (kg)</div></div>
          <div><input type="number" id="altura" value="170" min="120" max="220"
            aria-label="altura em centímetros"><div class="nota">altura (cm)</div></div>
          <div class="imc-valor" id="imcOut">IMC —</div>
        </div>`;
    } else if (q.tipo === "numero"){
      d.innerHTML = `<label for="f_${q.var}">${q.rotulo}</label>
        <input type="number" id="f_${q.var}" value="${q.padrao}" min="${q.min}" max="${q.max}">
        ${q.nota?`<div class="nota">${q.nota}</div>`:""}`;
    } else {
      const ops = q.opcoes.map(([v,r]) =>
        `<option value="${v===null?"":v}"${v===q.padrao?" selected":""}>${r}</option>`).join("");
      d.innerHTML = `<label for="f_${q.var}">${q.rotulo}</label>
        <select id="f_${q.var}">${ops}</select>
        ${q.nota?`<div class="nota">${q.nota}</div>`:""}`;
    }
    alvo.appendChild(d);
  });
  alvo.addEventListener("input", calcular);
}

function lerFormulario(){
  const l = {};
  M.perguntas.forEach(q => {
    if (q.tipo === "imc"){
      const kg = +$("#peso").value, cm = +$("#altura").value;
      const imc = cm > 0 ? kg / Math.pow(cm/100, 2) : NaN;
      $("#imcOut").textContent = isFinite(imc) ? `IMC ${imc.toFixed(1)}` : "IMC —";
      l._BMI5 = isFinite(imc) ? imc * 100 : null;   // o modelo usa IMC x 100
    } else {
      const el = $(`#f_${q.var}`);
      const v = el.value;
      l[q.var] = (v === "" ? null : +v);
    }
  });
  return l;
}

/* --- apresentacao ------------------------------------------------------- */
function corDoRisco(p){
  return p < 0.05 ? "var(--s3)" : p < 0.15 ? "var(--s1)"
       : p < 0.30 ? "var(--s2)" : "var(--alerta)";
}
function rotuloDoRisco(p){
  return p < 0.05 ? "risco baixo" : p < 0.15 ? "risco moderado"
       : p < 0.30 ? "risco elevado" : "risco muito elevado";
}

function calcular(){
  const l = lerFormulario();
  Object.assign(estado, l);
  const {p, contrib} = prever(l);
  const pct = percentil(p);

  $("#numero").innerHTML = (p*100).toFixed(1).replace(".", ",") + "<span>%</span>";
  $("#numero").style.color = corDoRisco(p);
  $("#faixaTxt").textContent =
    `${rotuloDoRisco(p)} · maior que ${pct.toFixed(0)}% da população adulta dos EUA`;
  $("#barraPct").style.width = pct + "%";
  $("#barraPct").style.background = corDoRisco(p);

  /* comparacao com as referencias das outras bases */
  const R = M.referencias;
  const linhas = [
    ["Você", p*100, corDoRisco(p)],
    /* as chaves terminam em '%', entao exigem colchete: R.chave_% e erro de sintaxe */
    ["EUA — diagnosticado (BRFSS)", R["prevalencia_eua_diagnosticada_%"], "var(--ink3)"],
    ["EUA — real, com subdiagnóstico", R["prevalencia_eua_verdadeira_%"], "var(--ink3)"],
    ["Brasil — capitais (Vigitel)", R["prevalencia_brasil_vigitel_2015_%"], "var(--ink3)"],
  ];
  const maxv = Math.max(...linhas.map(x => x[1]), 1);
  $("#comp").innerHTML = linhas.map(([r,v,c]) => `
    <div class="linha"><div>
      <div class="rot">${r}</div>
      <div class="barra"><i style="width:${Math.min(v/maxv*100,100)}%;background:${c}"></i></div>
    </div><div class="val">${v.toFixed(1).replace(".",",")}%</div></div>`).join("");

  /* contribuicoes: soma por variavel, nao por termo — a interacao e dividida
     entre as variaveis que a compoem, senao o leitor ve um termo que nao
     corresponde a nenhuma pergunta que ele respondeu */
  const porVar = {};
  contrib.forEach(c => c.vars.forEach(v => {
    porVar[v] = (porVar[v] || 0) + c.s / c.vars.length;
  }));
  const itens = Object.entries(porVar)
    .map(([v,s]) => ({rot: M.nomes_pt[v] || v, s}))
    .sort((a,b) => Math.abs(b.s) - Math.abs(a.s)).slice(0, 8);
  const maxs = Math.max(...itens.map(i => Math.abs(i.s)), .01);
  $("#wf").innerHTML = itens.map(i => {
    const larg = Math.abs(i.s)/maxs*48;
    const est = i.s >= 0
      ? `left:50%;width:${larg}%;background:var(--alerta)`
      : `right:50%;width:${larg}%;background:var(--s3)`;
    return `<div class="item"><div class="rot">${i.rot}</div>
      <div class="eixo"><div class="bar" style="${est}"></div></div>
      <div class="val">${i.s>=0?"+":"−"}${Math.abs(i.s).toFixed(2)}</div></div>`;
  }).join("");

  /* contrafactuais: so o que a pessoa consegue mudar */
  const cf = [];
  const imc = l._BMI5 / 100;
  if (imc > 23){
    const alvo = Math.max(imc - 5, 22);
    const q = prever({...l, _BMI5: alvo*100}).p;
    const n1 = x => x.toFixed(1).replace(".", ",");
    cf.push([`IMC de ${n1(imc)} para ${n1(alvo)}`, q - p]);
  }
  if (l.GENHLTH > 2){
    const q = prever({...l, GENHLTH: l.GENHLTH - 1}).p;
    cf.push(["Saúde autoavaliada um nível melhor", q - p]);
  }
  if (l._RFHYPE5 == 2){
    const q = prever({...l, _RFHYPE5: 1}).p;
    cf.push(["Pressão sob controle", q - p]);
  }
  const dez = prever({...l, _AGE80: Math.min((l._AGE80||45) + 10, 80)}).p;
  cf.push(["Daqui a 10 anos, sem mudar nada", dez - p]);
  $("#cf").innerHTML = cf.map(([r,d]) => `<div class="item"><span>${r}</span>
    <b class="${d<0?"baixa":"sobe"}">${d<0?"−":"+"}${Math.abs(d*100).toFixed(1).replace(".",",")} p.p.</b>
    </div>`).join("");

  /* escore de papel */
  const e = escorePapel(l);
  $("#pontos").textContent = e.pontos;
  $("#riscoPapel").textContent = e.faixa["risco_%"].toFixed(2).replace(".",",") + "%";
  document.querySelectorAll("#tabPapel tr[data-min]").forEach(tr => {
    tr.classList.toggle("ativa", +tr.dataset.min === e.faixa.pontos_min);
  });
}

/* --- abas --------------------------------------------------------------- */
function abas(){
  document.querySelectorAll(".abas button").forEach(b => {
    b.onclick = () => {
      document.querySelectorAll(".abas button").forEach(x =>
        x.setAttribute("aria-selected", x === b));
      document.querySelectorAll("[data-painel]").forEach(pn =>
        pn.hidden = pn.dataset.painel !== b.dataset.aba);
    };
  });
}

montarFormulario(); abas(); calcular();
"""


def montar(modelo: dict) -> str:
    fx = modelo["escore_papel"]["calibracao"]["faixas"]
    linhas_tab = "".join(
        f'<tr data-min="{f["pontos_min"]}"><td>{f["pontos_min"]}–{f["pontos_max"]}</td>'
        f'<td>{f["risco_%"]:.2f}%</td></tr>'.replace(".", ",", 1)
        for f in fx)
    m = modelo["metricas"]
    par = modelo["paridade_export"]

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Calculadora de risco de diabetes — Data Science 2 · ESEG</title>
<style>{CSS}</style></head><body><main>

<header>
  <h1>Calculadora de risco de diabetes</h1>
  <p class="lead">Modelo treinado em <b>432.968 respondentes</b> da pesquisa BRFSS 2015
  do CDC. Roda inteiramente no seu navegador — nenhuma resposta sai deste
  computador, e a página funciona sem internet.</p>
  <p class="aviso"><b>Isto não é um diagnóstico.</b> É um trabalho acadêmico
  (Data Science 2 · ESEG). O modelo estima a probabilidade de uma pessoa com este
  perfil <i>constar como diagnosticada</i> numa pesquisa populacional americana de
  2015 — não a presença da doença. Procure um profissional de saúde.</p>
</header>

<div class="grade">
  <div>
    <div class="cartao">
      <h2>Suas respostas</h2>
      <div id="form"></div>
    </div>

    <div class="cartao">
      <h2>Escore de papel — 5 perguntas</h2>
      <p class="lead" style="font-size:14px">A versão que roda numa unidade básica
      de saúde <b>sem computador</b>. Usa apenas idade, IMC, saúde autoavaliada,
      pressão alta e sexo — nenhuma exige exame prévio. Discrimina melhor que o
      FINDRISC, o padrão internacional desde 2003.</p>
      <p style="margin:14px 0 4px"><span class="pontos" id="pontos"
        style="font-size:30px;font-weight:650">—</span>
        <span style="color:var(--ink2)">pontos → risco de
        <b id="riscoPapel">—</b></span></p>
      <table id="tabPapel"><thead><tr><th>pontos</th><th>risco</th></tr></thead>
      <tbody>{linhas_tab}</tbody></table>
    </div>
  </div>

  <div class="resultado">
    <div class="cartao">
      <h2>Risco estimado</h2>
      <div class="numero" id="numero">—</div>
      <div class="barra" style="margin-top:14px"><i id="barraPct" style="width:0"></i></div>
      <p class="faixa-txt" id="faixaTxt">—</p>
      <div class="comp" id="comp"></div>
    </div>

    <div class="cartao">
      <div class="abas" role="tablist">
        <button data-aba="wf" aria-selected="true">O que pesa</button>
        <button data-aba="cf" aria-selected="false">E se mudasse</button>
      </div>
      <div data-painel="wf">
        <div class="wf" id="wf"></div>
        <p class="nota" style="margin-top:12px;font-size:12px;color:var(--ink3)">
        Contribuição de cada resposta ao logit. Vermelho aumenta o risco, verde reduz.
        Termos de interação são divididos entre as variáveis que os compõem.</p>
      </div>
      <div data-painel="cf" hidden>
        <div class="cf" id="cf"></div>
        <p class="nota" style="margin-top:12px;font-size:12px;color:var(--ink3)">
        Simulação sobre o modelo, não promessa clínica: mostra o que o modelo
        prevê para um perfil diferente, não o efeito causal de mudar de hábito.</p>
      </div>
    </div>
  </div>
</div>

<footer>
  <div class="metricas">
    <div><b>{m["roc_auc"]:.3f}</b> ROC-AUC (holdout)</div>
    <div><b>{m["pr_auc"]:.3f}</b> PR-AUC</div>
    <div><b>{m["n_treino"]:,}</b> no treino</div>
    <div><b>{m["n_holdout"]:,}</b> no holdout</div>
    <div><b>{par["erro_max"]:.1e}</b> erro máximo Python↔JavaScript</div>
  </div>
  <p><b>Modelo:</b> Explainable Boosting Machine com {len(modelo["ebm"]["termos"])}
  termos, exportado como tabela de consulta. A predição no navegador é idêntica à
  do Python — a paridade é verificada automaticamente a cada build e o processo
  falha se divergir.</p>
  <p><b>Limitações que importam:</b> o alvo é diagnóstico autorrelatado, não a doença
  — cerca de 27,6% dos diabéticos nos EUA não sabem que têm (NHANES). O modelo foi
  treinado nos EUA e o IMC pesa ~16% menos no Brasil (Vigitel 2015), então o risco
  para brasileiros é provavelmente superestimado. Raça/etnia entra como proxy de
  determinantes sociais, nunca como fator biológico.</p>
  <p>Data Science 2 · ESEG · Prof. Marino Catarino ·
  <b>github.com/felipe44776-eseg/data-science-2-eseg-diabetes</b></p>
</footer>
</main>
<script>const MODELO={json.dumps(modelo, ensure_ascii=False, separators=(",", ":"))};</script>
<script>{JS}</script>
</body></html>"""


def verificar_js(js: str) -> None:
    """Roda `node --check` no JavaScript antes de publicar a pagina.

    Motivo concreto: a primeira versao acessava `R.prevalencia_eua_..._%`, e `%`
    nao e identificador valido — a pagina abria, ficava com aparencia correta e
    **nao calculava nada**. Erro silencioso em apresentacao ao vivo e o pior
    tipo. O build agora falha em vez de publicar HTML quebrado.
    """
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if not node:
        print("  [aviso] node ausente — verificacao de sintaxe do JS pulada")
        return
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("const MODELO={};const document={querySelector:()=>null,"
                 "querySelectorAll:()=>[],createElement:()=>({}),"
                 "addEventListener:()=>{}};\n" + js)
        caminho = fh.name
    r = subprocess.run([node, "--check", caminho], capture_output=True, text=True)
    Path(caminho).unlink(missing_ok=True)
    if r.returncode != 0:
        raise SystemExit("JavaScript invalido:\n" + r.stderr)
    print("  sintaxe do JavaScript verificada (node --check)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--modelo", type=Path, default=SAIDA / "modelo.json")
    ap.add_argument("--saida", type=Path, default=SAIDA / "index.html")
    args = ap.parse_args()

    modelo = json.loads(args.modelo.read_text(encoding="utf-8"))
    verificar_js(JS)
    html = montar(modelo)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(html, encoding="utf-8")
    print(f"  {args.saida}  ({len(html)/1024:.0f} KB, autocontido)")


if __name__ == "__main__":
    main()
