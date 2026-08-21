/* Paridade Python <-> JavaScript do modelo do produto.
 *
 * Le `reports/produto/modelo.json` e o arquivo de casos gerado pelo Python
 * (`reports/produto/_casos_paridade.json`, com entrada e probabilidade
 * calculada pelo sklearn) e verifica que a implementacao em JavaScript —
 * a MESMA que roda na pagina — devolve o mesmo numero.
 *
 * Por que isto existe: a pagina e o entregavel da apresentacao. Se o
 * JavaScript divergir do Python, o numero mostrado ao vivo nao e o numero do
 * modelo validado, e nada no HTML denuncia isso.
 *
 * Uso: node tests/paridade_js.mjs
 */
import { readFileSync } from "node:fs";

const M = JSON.parse(readFileSync("reports/produto/modelo.json", "utf8"));
const CASOS = JSON.parse(readFileSync("reports/produto/_casos_paridade.json", "utf8"));

/* --- copia literal da funcao da pagina --------------------------------- */
function indice(v, cortes) {
  if (v === null || v === undefined || Number.isNaN(v)) return 0;
  let i = 1;
  for (const c of cortes) { if (v < c) break; i++; }
  return i;
}
function prever(linha) {
  let total = M.ebm.intercepto;
  for (const t of M.ebm.termos) {
    const forma = t.forma;
    let plano = 0;
    t.variaveis.forEach((v, k) => {
      let i = indice(linha[v], t.cortes[k]);
      if (i > forma[k] - 1) i = forma[k] - 1;
      plano = plano * forma[k] + i;
    });
    total += t.scores[plano];
  }
  return 1 / (1 + Math.exp(-total));
}

/* --- verificacao -------------------------------------------------------- */
let pior = 0, piorCaso = null;
for (const caso of CASOS.casos) {
  const p = prever(caso.entrada);
  const d = Math.abs(p - caso.p_python);
  if (d > pior) { pior = d; piorCaso = caso; }
}

const TOLERANCIA = 1e-12;
const linhas = [
  `casos verificados      ${CASOS.casos.length}`,
  `erro maximo            ${pior.toExponential(3)}`,
  `tolerancia             ${TOLERANCIA.toExponential(0)}`,
];
console.log(linhas.join("\n"));

if (pior > TOLERANCIA) {
  console.error("\nREPROVADO — o JavaScript diverge do Python.");
  console.error("pior caso:", JSON.stringify(piorCaso, null, 2));
  process.exit(1);
}

/* casos com valor ausente tem de ser aceitos, nao viram NaN */
const comAusente = CASOS.casos.filter(c =>
  Object.values(c.entrada).some(v => v === null));
if (comAusente.length === 0) {
  console.error("\nREPROVADO — nenhum caso com valor ausente foi testado.");
  process.exit(1);
}
for (const c of comAusente) {
  const p = prever(c.entrada);
  if (!Number.isFinite(p) || p < 0 || p > 1) {
    console.error("\nREPROVADO — valor ausente produziu probabilidade invalida:", p);
    process.exit(1);
  }
}

console.log(`casos com ausente      ${comAusente.length} (todos validos)`);
console.log("\nAPROVADO — a pagina calcula o mesmo que o Python.");
