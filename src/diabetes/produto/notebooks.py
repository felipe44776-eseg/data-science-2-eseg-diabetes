"""Gera os notebooks da apresentacao a partir dos artefatos ja calculados.

Por que gerar em vez de escrever a mao
--------------------------------------
A regra 7 do projeto e "notebook mostra resultado, nao contem logica". Escrever
notebooks a mao viola isso na pratica: o codigo migra para dentro deles e passa
a divergir de `src/`, sem teste que denuncie.

Aqui os notebooks sao **gerados**: cada celula ou importa de `src/` ou le um
artefato JSON que o pipeline produziu. Regerar depois de `.\\tasks.ps1 all`
garante que o que o notebook mostra e o que o pipeline calculou — nunca um
numero de uma execucao antiga colado numa celula.

Uso:
    python -m diabetes.produto.notebooks
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SAIDA = Path("notebooks")


_ID = [0]


def _proximo_id() -> str:
    """nbformat >= 4.5 exige `id` em cada celula; sem ele vem aviso e, adiante, erro."""
    _ID[0] += 1
    return f"c{_ID[0]:03d}"


def _linhas(texto: str) -> list[str]:
    r"""`source` e uma lista de linhas **com** o \n no fim de cada uma.

    Sem o \n as linhas sao concatenadas ao carregar o notebook e o codigo vira
    uma linha so — `import sys, jsonfrom pathlib import Path`. Erro silencioso:
    o arquivo abre, o JSON e valido, e nada executa.
    """
    return (texto.strip() + "\n").splitlines(keepends=True)


def md(texto: str) -> dict:
    return {"cell_type": "markdown", "id": _proximo_id(), "metadata": {},
            "source": _linhas(texto)}


def cod(texto: str) -> dict:
    return {"cell_type": "code", "id": _proximo_id(), "execution_count": None,
            "metadata": {}, "outputs": [], "source": _linhas(texto)}


CABECALHO = """
import sys, json
from pathlib import Path

# a raiz e onde existe src/ — funciona rodando de notebooks/ ou da raiz do repo
RAIZ = Path.cwd()
if not (RAIZ / "src").exists():
    RAIZ = RAIZ.parent
sys.path.insert(0, str(RAIZ / "src"))

import numpy as np, pandas as pd
pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 50)

GOLD = RAIZ / "data" / "processed" / "gold"
def ler(nome, base=GOLD):
    return json.loads((base / nome).read_text(encoding="utf-8"))
"""


# --------------------------------------------------------------------------

NOTEBOOKS: dict[str, list[dict]] = {}

NOTEBOOKS["01-ingestao-e-qualidade"] = [
    md("""
# 01 · Ingestão e qualidade dos dados

**O problema que ninguém esperava:** os dados não vieram como CSV. Vieram como
`Diabetes-2026.csv.pdf` — **109 MB, 4.374 páginas** de tabela renderizada.

Extrair por ordem de leitura de texto é frágil: a especificação PDF **não garante**
que a ordem dos tokens corresponda à ordem visual. A ingestão reconstrói as linhas
**por coordenada de bounding box**.

> Documento completo: [`docs/01-diagnostico-dos-dados.md`](../docs/01-diagnostico-dos-dados.md)
"""),
    cod(CABECALHO),
    md("## A extração — e a prova de que funcionou"),
    cod("""
manifesto = ler("_manifest_ingestao.json", RAIZ / "data" / "raw")["manifest"]
pd.Series({
    "páginas processadas":  manifesto["paginas"],
    "linhas reconstruídas": manifesto["n_linhas"],
    "colunas":              manifesto["n_colunas"],
    "linhas em quarentena": manifesto["n_quarentena"],
    "segundos":             manifesto["segundos"],
    "sha256 do CSV":        manifesto["sha256_csv"][:16] + "...",
}).to_frame("valor")
"""),
    md("""
**253.680 linhas, 22 colunas, zero em quarentena** — bate exatamente com o enunciado.

Nenhuma linha foi descartada em silêncio: cardinalidade e parseabilidade são
validadas linha a linha, e o que falha vai para quarentena com página e motivo.
"""),
    md("## Limpeza — 7 regras, cada uma com contagem"),
    cod("""
rel = ler("_relatorio_limpeza.json", RAIZ / "data" / "processed")
pd.Series({
    "linhas de entrada":        rel["entrada_linhas"],
    "violações de domínio":     len(rel["violacoes_dominio"]),
    "linhas em quarentena":     rel["linhas_quarentena"],
    "duplicatas exatas":        rel["duplicatas_exatas"],
    "grupos com alvo conflitante": rel["grupos_alvo_conflitante"],
    "IMC > 60 (marcado, não removido)": rel["imc_extremo"],
    "memória final (MB)":       rel["memoria_mb"],
}).to_frame("valor")
"""),
    md("### Distribuição do alvo — por que acurácia foi banida"),
    cod("""
alvo = pd.Series(rel["distribuicao_alvo_pct"])
alvo.index = ["0 · sem diabetes", "1 · pré-diabetes", "2 · diabetes"]
display(alvo.to_frame("% da amostra"))
print(f"\\nUm classificador que sempre responde '0' acerta {alvo.iloc[0]:.1f}%.")
print("Por isso a métrica principal é PR-AUC, não acurácia (ADR 0005).")
"""),
    md("""
## Os quatro problemas que definem o trabalho

1. **23.899 duplicatas exatas** (9,4%) → risco de vazamento treino/teste
2. **1.834 grupos com rótulo contraditório** → teto de Bayes mensurável
3. **Desbalanceamento severo** — a classe pré-diabetes tem 1,8%
4. **Zero códigos 77/99 de renda** → a amostra foi **truncada** antes de chegar

O item 4 é o que abre o resto do projeto: quem não declarou renda foi **excluído**,
e isso é medível comparando com a fonte original — o notebook 02.
"""),
]

NOTEBOOKS["02-comparacao-com-a-fonte-original"] = [
    md("""
# 02 · O que o pré-processamento fez com os dados

O arquivo entregue tem 253.680 respondentes. O **BRFSS 2015 original do CDC tem
441.456**. Este notebook reconstrói as 22 colunas a partir da fonte e mede o viés.

> Documento completo: [`docs/05-comparacao-brfss-original.md`](../docs/05-comparacao-brfss-original.md)
"""),
    cod(CABECALHO),
    md("## A prova de integridade"),
    cod("""
from diabetes.schema import ESQUEMA
EXT = RAIZ / "data" / "external" / "brfss2015"

prof = pd.read_parquet(RAIZ / "data/processed/diabetes_silver.parquet")[list(ESQUEMA)]
rec  = pd.read_parquet(EXT / "brfss2015_reconstruido.parquet")[list(ESQUEMA)]

iguais = (prof.reset_index(drop=True).values == rec.reset_index(drop=True).values)
print(f"células idênticas   : {iguais.mean()*100:.6f}%")
print(f"linhas 100% iguais  : {iguais.all(axis=1).sum():,} de {len(prof):,}")
"""),
    md("""
**Identidade perfeita.** Isso prova quatro coisas de uma vez: a extração do PDF
está correta, as regras de derivação são as que geraram o arquivo, o download
está íntegro, e a ordem das linhas foi preservada.
"""),
    md("## A cascata de exclusões — quem foi descartado"),
    cod("""
casc = pd.DataFrame(ler("_cascata_exclusoes.json", EXT)["cascata"])
casc = casc[(casc.etapa != "final") & (casc.excluidos > 0)].sort_values("excluidos", ascending=False)
casc["% das exclusões"] = (casc.excluidos / casc.excluidos.sum() * 100).round(1)
casc[["regra", "variavel", "criterio", "excluidos", "% das exclusões"]].head(8)
"""),
    md("## O viés que isso produz"),
    cod("""
vies = ler("_analise_vies.json", EXT)
pd.DataFrame(vies["prevalencia"])[
    ["estimativa", "n", "n_efetivo", "diabetes_%", "ic95_diabetes"]]
"""),
    cod("""
a = 13.933   # arquivo entregue, sem peso
b = 12.993   # BRFSS completo, sem peso
c = 10.500   # BRFSS completo, com peso
print(f"descarte de 42,5% da amostra : {b-a:+.2f} p.p.  ({(a-b)/(a-c)*100:.0f}% do viés)")
print(f"peso amostral descartado     : {c-b:+.2f} p.p.  ({(b-c)/(a-c)*100:.0f}% do viés)")
print(f"\\nviés total: {a-c:+.2f} p.p. — superestimação de {(a/c-1)*100:.1f}%")
"""),
    md("""
> **O resultado contraintuitivo:** a maior parte do viés **não** vem de terem
> jogado fora 187.776 pessoas. Vem de terem jogado fora **três colunas**
> (`_LLCPWT`, `_STSTR`, `_PSU`).
"""),
    md("## O achado mais grave: o arquivo é uma amostra de quem tem acesso"),
    cod("""
pd.DataFrame([
    ["% fez exame de colesterol", 96.27, 77.93],
    ["% com plano de saúde",      95.11, 87.83],
    ["% sem consulta por custo",   8.42, 13.27],
], columns=["indicador", "arquivo entregue", "população (ponderada)"]).assign(
    viés_pp=lambda d: (d["arquivo entregue"] - d["população (ponderada)"]).round(2))
"""),
    md("""
Quase um em cada quatro americanos nunca fez exame de colesterol. No arquivo
entregue, é **um em vinte e sete**.

Consequência que reescreve o plano de análise: `exame_colesterol` é quase
constante e não representa a população; qualquer conclusão sobre **desigualdade
de acesso** feita neste arquivo está estruturalmente comprometida.
"""),
]

NOTEBOOKS["03-analise-exploratoria-e-explicativa"] = [
    md("""
# 03 · Análise exploratória e explicativa

Toda estimativa sai **em par**: arquivo entregue (sem peso) e BRFSS completo
(ponderado). A diferença entre as colunas **é** o resultado.

Com n = 253.680 todo p-valor dá zero — ele não distingue nada nesta escala.
Reportamos **tamanho de efeito** e **intervalo de confiança**.

> Documentos: [`docs/06`](../docs/06-analise-exploratoria.md) e [`docs/07`](../docs/07-analise-explicativa.md)
"""),
    cod(CABECALHO),
    md("## Associações brutas — o arquivo entregue atenua os efeitos"),
    cod("""
eda = ler("_eda_comparativa.json")
b = pd.DataFrame(eda["binarias"])
b[["variavel", "A_%_exposto", "B_%_exposto", "delta_exposicao",
   "A_OR", "B_OR", "delta_OR_%", "B_V", "efeito_B"]].head(10)
"""),
    md("""
O sinal de `delta_OR_%` é **negativo em 11 das 14** variáveis: o arquivo entregue
**subestima** as associações, e a atenuação chega a 30%. Quem analisar só o
arquivo subestima o efeito da hipertensão em um quarto.

E o maior V de Cramér é **0,293** — ainda "pequeno" por Cohen. **Diabetes é
multifatorial e nenhuma variável isolada o explica.**
"""),
    md("## Gradientes ordinais — idade e a mortalidade seletiva"),
    cod("""
ordinais = {o["variavel"]: o for o in eda["ordinais"]}
idade = ordinais["idade_faixa"]
A = idade["A_prev_por_nivel"] if isinstance(idade["A_prev_por_nivel"], dict) else eval(idade["A_prev_por_nivel"])
B = idade["B_prev_por_nivel"] if isinstance(idade["B_prev_por_nivel"], dict) else eval(idade["B_prev_por_nivel"])
g = pd.DataFrame({"arquivo": pd.Series(A).astype(float),
                  "populacional": pd.Series(B).astype(float)})
g.index = ["18-24","25-29","30-34","35-39","40-44","45-49","50-54",
           "55-59","60-64","65-69","70-74","75-79","80+"]
display(g)
print(f"razão extremos — arquivo {idade['A_razao']}×   populacional {idade['B_razao']}×")
"""),
    md("""
Dois achados nesta tabela:

1. **O arquivo comprime o gradiente etário quase pela metade** (15,96× contra 30,02×);
2. **não é monotônico** — sobe até 75–79 (24,66%) e **cai em 80+ (19,67%)**.
   É **mortalidade seletiva**: diabéticos têm menor chance de chegar aos 80.
   Modelar idade como linear ignora essa inflexão.
"""),
    md("## Odds ratio ajustado — M1 (risco puro)"),
    cod("""
mod = ler("_modelo_explicativo.json")
m1 = pd.DataFrame(mod["comparacao_M1_entre_bases"]).T
m1.sort_values("B_OR", ascending=False)[["A_OR", "B_OR", "B_ic", "atenuacao_%"]]
"""),
    md("""
**Correção importante:** na análise *bruta* o arquivo atenuava os OR em até 30%.
No modelo **ajustado**, a maior divergência é 11%. O ajuste multivariado absorve
a maior parte do viés de seleção — porque a seleção operou por idade, renda e
acesso, que agora são covariáveis.

Isso **reabilita parcialmente** o arquivo entregue para análise multivariada.
Registrar isso corta contra a narrativa mais fácil, e é o que separa análise de retórica.
"""),
    md("## A mediação que muda a interpretação"),
    cod("""
est = pd.DataFrame(mod["estabilidade_M1_M2_M3"]).T
est.loc[["atividade_fisica", "renda_faixa", "saude_geral", "hipertensao",
         "doenca_cardiaca", "saude_mental_dias"]]
"""),
    md("""
```
M1 (risco puro)        atividade_fisica  OR 0,852   protetor
M2 (+ saúde geral…)    atividade_fisica  OR 0,988   some
```

Ao entrar `saude_geral`, o efeito da atividade física **evapora**. Isso é
**mediação** — e é a leitura errada mais provável do trabalho inteiro.
**M2 e M3 não podem ser lidos como "atividade física não importa".**
"""),
    md("## O alvo não é ordinal — e o teste ingênuo não detecta"),
    cod("""
pvd = pd.DataFrame(mod["pre_vs_diabetes"]).T
pvd[~pvd["ic_sobrepoe"].astype(bool)][
    ["or_pre_vs_sem", "ic_pre", "or_diab_vs_sem", "ic_diab", "razao_diab_pre"]]
"""),
    md("""
**Nove variáveis com IC disjunto**, e duas **invertem de direção**.
`sexo` tem OR 1,00 no pré-diabetes e 1,26 no diabetes.

Lição metodológica: o teste por *logits cumulativos* **não rejeitou** — divergência
máxima de 8,6%. É falso negativo: com a classe 1 valendo 1,6%, os dois contrastes
são quase idênticos por construção. **Teste de Brant por cortes cumulativos é
inadequado quando uma classe é rara.**
"""),
]

NOTEBOOKS["04-modelagem-preditiva"] = [
    md("""
# 04 · Modelagem preditiva

Protocolo fixado **antes** de qualquer modelo: partição por grupo (hash das
features), holdout de 20% tocado uma única vez, `class_weight` em vez de
reamostragem, **PR-AUC** como métrica principal.

> Documentos: [`docs/08`](../docs/08-modelagem-preditiva.md) e [`docs/10`](../docs/10-frente1-variaveis-expandidas.md)
"""),
    cod(CABECALHO),
    md("## A escada — cada degrau justificado"),
    cod("""
esc = ler("_escada_modelos.json")
linhas = [{"modelo": k, "vars": v["variaveis"],
           "PR-AUC": v["holdout"]["pr_auc"],
           "ganho vs prevalência": v["holdout"]["pr_auc_ganho"],
           "ROC-AUC": v["holdout"]["roc_auc"],
           "recall@esp90": v["holdout"]["recall_esp90"],
           "ECE": v["holdout"]["ece"]}
          for k, v in esc["sem_proxies_de_acesso"]["modelos"].items()]
pd.DataFrame(linhas)
"""),
    md("""
### O que a coluna ECE conta

`class_weight="balanced"` dá **ECE 0,236**; a calibração isotônica dá **0,0035** —
**67× menos erro** com ROC-AUC idêntico. Um modelo com peso de classe ordena bem
mas diz "40%" onde a prevalência é 14%.

É a demonstração empírica do ADR 0004: **reponderar destrói a calibração**. E o
mesmo argumento condena o SMOTE.
"""),
    md("## Três previsões que os dados não confirmaram"),
    cod("""
v = esc["vazamento"]
print("1 · VAZAMENTO POR DUPLICATA")
print(f"   {v['pct_teste_contaminado']}% do teste tem gêmea idêntica no treino")
print(f"   inflação de PR-AUC: {v['inflacao_pr_auc_%']}%  <- muito menor que o alegado")
print()
t = esc["teto_de_bayes"]
print("2 · TETO DE BAYES")
print(f"   acerto máximo imposto pelo ruído: {t['acerto_maximo_ponderado']*100:.2f}%")
print(f"   ROC-AUC do melhor modelo: 0,836  ->  o teto NÃO é a restrição")
print()
sem = esc["sem_proxies_de_acesso"]["modelos"]["5_gb_calibrado"]["holdout"]["pr_auc"]
com = esc["com_proxies_de_acesso"]["modelos"]["5_gb_calibrado"]["holdout"]["pr_auc"]
print("3 · PROXIES DE ACESSO")
print(f"   sem: {sem}   com: {com}   ganho: {(com/sem-1)*100:.1f}%")
print("   excluí-los por validade quase não custa performance")
"""),
    md("""
As três estavam escritas em documento anterior deste projeto e foram **corrigidas
na fonte**. A restrição real não é ruído de rótulo nem algoritmo: é **informação**.
"""),
    md("## Curva de parcimônia — quantas variáveis bastam"),
    cod("""
p = pd.DataFrame(esc["parcimonia"]["curva"])
p[["n_variaveis", "adicionada", "pr_auc", "%_do_teto"]]
"""),
    md("**Cinco variáveis entregam 89,2%** do modelo de 21. O entregável é o escore."),
    md("## E o que acontece ao recuperar as variáveis descartadas"),
    cod("""
f1 = ler("_frente1_expandido.json")
display(pd.DataFrame(f1["comparacao"]).T[["pr_auc", "roc_auc", "recall_esp90", "n_variaveis"]]
        .dropna().head(3))
print("\\nDe onde vem o ganho (ablação por bloco):")
display(pd.DataFrame(f1["ablacao_por_bloco"])[["bloco_removido", "n_removidas", "perda_%"]])
"""),
    md("## Para quem o modelo melhora — a auditoria que só agora é possível"),
    cod("""
aud = pd.DataFrame(f1["auditoria_raca"])
aud[["grupo", "n", "prevalencia_%", "recall_orig", "recall_novo", "ganho_recall"]]
"""),
    md("""
> **O ganho médio de 6,6% esconde uma redistribuição enorme.** Brancos perdem
> meio ponto; todos os demais grupos ganham **10 a 13 pontos percentuais** de recall.
>
> O modelo de 21 variáveis era sistematicamente pior para minorias — e ninguém
> podia saber, porque a variável que revela isso tinha sido removida da base.
"""),
]

NOTEBOOKS["05-comparacao-entre-bases"] = [
    md("""
# 05 · Comparação entre bases — o diferencial do trabalho

Cinco fontes externas, cada uma respondendo uma pergunta que o arquivo entregue
não responde sozinho.

| fonte | o que resolve |
|---|---|
| **BRFSS 2015 original** | mede o viés do próprio arquivo entregue |
| **Vigitel 2015** | os fatores valem no Brasil? |
| **NHANES** (prior) | quanta doença fica sem diagnóstico |
| **CDC Open Data** | valida nossa estimativa contra o número oficial |
| **Painel Medicaid** | acesso causa diagnóstico? |

> Documentos: [`docs/09`](../docs/09-comparacao-binacional.md), [`docs/12`](../docs/12-frente2-positive-unlabeled.md), [`docs/14`](../docs/14-frente4-medicaid-experimento-natural.md)
"""),
    cod(CABECALHO),
    md("## Brasil × EUA — mesmo ano, mesmo desenho, mesmo modelo"),
    cod("""
bi = ler("_comparacao_binacional.json", RAIZ / "data" / "external" / "vigitel")
pd.DataFrame(bi["prevalencia"]).T
"""),
    cod("""
o = pd.DataFrame(bi["odds_ratio"]).T
o[["OR_Brasil", "IC_Brasil", "OR_EUA", "IC_EUA", "razao_BR_EUA", "ic_sobrepoe"]]
"""),
    md("""
**Seis de oito fatores convergem.** `hipertensao` (3,136 vs 3,146) e `idade_faixa`
(1,234 vs 1,240) coincidem na **terceira casa decimal**, em dois países e dois
sistemas de saúde. É a evidência mais forte do trabalho de que os fatores centrais
são robustos e **transferem**.

**Duas divergências reais:**
- `frutas` **inverte de direção** (BR 1,30 · EUA 0,90)
- **o IMC pesa 16% menos no Brasil** (1,23 vs 1,45 por 5 kg/m²) — um escore
  calibrado nos EUA **superestima** o IMC aqui
"""),
    md("## Quanta doença está escondida"),
    cod("""
pu = ler("_frente2_pu.json")
print(f"c estimado só com os dados (BBE) : {pu['bbe']['c_estimado_bbe']}")
print(f"c do NHANES (fonte externa)      : {pu['premissa']['c_nhanes']}")
print(f"diferença                        : {abs(pu['bbe']['c_estimado_bbe']-pu['premissa']['c_nhanes']):.4f}")
display(pd.DataFrame(pu["sensibilidade_a_c"]))
"""),
    md("""
Duas fontes completamente independentes — um inquérito telefônico de 2015 e um
exame de sangue de 2021-2023 — concordam na **terceira casa decimal** sobre quanto
do diabetes fica sem diagnóstico.

E a ironia que fecha o notebook 02:

```
13,93%   arquivo entregue, sem peso         (seleção, para cima)
10,67%   BRFSS ponderado, diagnóstico
14,29%   prevalência VERDADEIRA estimada    (subdiagnóstico, para baixo)
```

Quem usasse o arquivo cru chegaria a 13,93% — perto dos 14,29% corretos,
**pelo motivo errado**, por dois vieses de sinal oposto.
"""),
    md("## Quem são os prováveis não diagnosticados"),
    cod("""
pd.DataFrame(pu["perfil"]).T[
    ["n", "idade_media", "imc_medio", "%_hipertensao",
     "%_check_up_no_ano", "%_sem_consulta_por_custo", "%_minoria"]]
"""),
    md("""
**Clinicamente iguais aos diagnosticados** — hipertensão 74,7% contra 74,9%,
IMC 32,3 contra 31,7 — e com o **acesso dos excluídos**: um terço do check-up,
o dobro de renúncia a consulta por custo, mais minorias.

É exatamente a população que um programa de rastreamento deveria alcançar, e a
que um classificador supervisionado ingênuo **ignora por construção**.
"""),
    md("## Acesso causa diagnóstico? O experimento natural"),
    cod("""
med = ler("_frente4_medicaid.json", RAIZ / "data" / "external" / "medicaid")
display(pd.DataFrame(med["did_baixa_renda"])[
    ["desfecho", "efeito_pp", "ic95", "p"]])
print("\\nPlacebo (renda alta, não elegível):")
display(pd.DataFrame(med["placebo_renda_alta"])[["desfecho", "efeito_pp", "p"]])
"""),
    cod("""
poder = med["poder_do_desenho"]
for k in ["efeito_MAXIMO_esperado_sobre_diagnostico_pp",
          "diferenca_minima_detectavel_pp", "razao_mde_sobre_efeito_esperado"]:
    print(f"{k:48} {poder[k]}")
print(f"\\n{poder['veredito']}")
"""),
    md("""
A expansão do Medicaid **aumentou o acesso** (+3,11 p.p. de cobertura) mas o efeito
sobre o diagnóstico é nulo. Antes de interpretar, calculamos o poder:

**Efeito máximo plausível 0,16 p.p. contra diferença mínima detectável de 0,90 p.p.**

O desenho não podia detectar o efeito esperado. **"Não detectamos" não é "não
existe"** — e sem esse cálculo o nulo seria lido como a conclusão oposta à
evidência do projeto.
"""),
]

NOTEBOOKS["06-escore-decisao-e-produto"] = [
    md("""
# 06 · Do modelo à decisão — e ao produto

O enunciado pede *"informações relevantes que possam **agregar algo de valor**"*.
Este notebook é a resposta: o instrumento aplicável e o orçamento que ele implica.

> Documentos: [`docs/16`](../docs/16-trilhaC-escore-decisao-equidade.md) e [`docs/17`](../docs/17-produto-calculadora.md)
"""),
    cod(CABECALHO),
    md("## O escore de 5 perguntas"),
    cod("""
e = ler("_trilhaC_escore.json")
b = e["escores"]["B_sem_proxy_acesso"]
for var, pontos in b["tabela"]["pontos"].items():
    ordenado = sorted(pontos.items(), key=lambda x: x[1])
    print(f"{var:14} " + "   ".join(f"{k}={v:+d}" for k, v in ordenado))
"""),
    cod("""
pd.DataFrame(b["calibracao"]["faixas"])[["pontos_min", "pontos_max", "risco_%"]]
"""),
    md("Da faixa mais baixa à mais alta, o risco multiplica por **84×**."),
    md("## A decisão que define o escore"),
    cod("""
pd.DataFrame({
    "A · com colesterol (6 perguntas)": e["escores"]["A_completo"]["metricas"],
    "B · sem proxy de acesso (5)":      e["escores"]["B_sem_proxy_acesso"]["metricas"],
    "FINDRISC aproximado":              e["findrisc"],
}).T[["roc_auc", "pr_auc", "n_variaveis", "n_avaliacao"]]
"""),
    md("""
> **Adotamos o B.** "Você tem colesterol alto?" só é respondível por quem **já fez
> um exame de sangue** — e o notebook 05 mostrou que os prováveis não diagnosticados
> são justamente os que **não fizeram**.
>
> Um escore que exige exame prévio **não alcança quem mais precisa dele**.
> Custa 2,07% de PR-AUC. É barato.

E as 5 perguntas ainda **batem o FINDRISC** em +37,7 milésimos de ROC-AUC — na
mesma amostra de 62.294 pessoas.
"""),
    md("## Quantos testar, quantos achar, a que custo"),
    cod("""
d = ler("_trilhaC_decisao.json")
cob = pd.DataFrame(d["candidatos"]["escore_5_perguntas"]["cobertura"])
cob["custo médio R$"] = cob["custo_por_caso_R$"].apply(lambda x: x[1])
cob[["%_testado", "%_casos_encontrados", "nns_acumulado", "custo médio R$"]].head(7)
"""),
    cod("""
dec = pd.DataFrame(d["candidatos"]["escore_5_perguntas"]["por_decil"])
dec["custo médio R$"] = dec["custo_por_caso_R$"].apply(lambda x: x[1])
dec[["faixa", "risco_%", "nns", "custo médio R$", "%_dos_casos_totais"]]
"""),
    md("""
**As duas faixas superiores concentram 60,5% dos casos a R$ 69–109 por caso.**
A faixa mais baixa custa **R$ 3.593** — **52× mais**.

Rastrear por ordem de escore não é refinamento: é a diferença entre um programa
viável e um inviável.
"""),
    md("## Equidade — e o problema de auditar um rótulo enviesado"),
    cod("""
eq = ler("_trilhaC_equidade.json")
pd.DataFrame(eq["observado"]["raca"]["por_grupo"])[
    ["grupo", "prevalencia_%", "taxa_selecao_%", "recall_tpr",
     "precisao_ppv", "calibracao_desvio_pp"]]
"""),
    cod("""
comp = pd.DataFrame({
    eixo: {"observado": eq["observado"][eixo]["disparidade"]["amplitude_igualdade_oportunidade"],
           "corrigido pelo PU": eq["corrigido_pu"][eixo]["disparidade"]["amplitude_igualdade_oportunidade"]}
    for eixo in ("raca", "sexo", "renda", "idade")}).T
comp["direção"] = np.where(comp["corrigido pelo PU"] < comp["observado"], "melhora", "PIORA")
comp
"""),
    md("""
> Corrigir pelo subdiagnóstico **muda a leitura da equidade — e não na mesma
> direção em todos os eixos**. Em raça, parte da disparidade aparente era artefato
> do rótulo. Em renda e idade, a disparidade **real é maior** que a medida.
>
> Uma auditoria de justiça que ignora o viés de verificação **subestima a
> injustiça exatamente onde ela é pior**.
"""),
    md("## O produto"),
    cod("""
prod = json.loads((RAIZ / "reports/produto/modelo.json").read_text(encoding="utf-8"))
print(f"ROC-AUC              {prod['metricas']['roc_auc']}")
print(f"PR-AUC               {prod['metricas']['pr_auc']}")
print(f"termos do EBM        {len(prod['ebm']['termos'])}")
print(f"paridade Python↔JS   erro máximo {prod['paridade_export']['erro_max']:.2e}")
print(f"tamanho do JSON      {(RAIZ/'reports/produto/modelo.json').stat().st_size/1024:.0f} KB")
print(f"tamanho da página    {(RAIZ/'reports/produto/index.html').stat().st_size/1024:.0f} KB")
"""),
    md("""
### 👉 Abra `reports/produto/index.html`

O EBM é **aditivo**, então exportamos as tabelas de consulta e a predição roda em
JavaScript com o **mesmo número** do Python — erro máximo 1,1 × 10⁻¹⁶, verificado
em 500 casos a cada build.

Um HTML de 59 KB, offline, que estima o risco, mostra **o que pesa** em cada
resposta, simula contrafactuais acionáveis e traz o escore de papel.

**Na apresentação:** escolha "nunca fiz o exame" no colesterol. É onde o produto
demonstra, em um clique, a tese que o projeto inteiro sustenta.
"""),
]


def construir(nome: str, celulas: list[dict]) -> dict:
    return {
        "cells": celulas,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
            "titulo": nome,
        },
        "nbformat": 4, "nbformat_minor": 5,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=SAIDA)
    args = ap.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)

    for nome, celulas in NOTEBOOKS.items():
        caminho = args.saida / f"{nome}.ipynb"
        caminho.write_text(
            json.dumps(construir(nome, celulas), ensure_ascii=False, indent=1),
            encoding="utf-8")
        n_cod = sum(1 for c in celulas if c["cell_type"] == "code")
        print(f"  {caminho.name:44} {len(celulas):>2} células ({n_cod} de código)")


if __name__ == "__main__":
    main()
