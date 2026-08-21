# Diabetes — BRFSS 2015

**Data Science 2 · Projeto 1 · ESEG · Prof. Marino Catarino**

Análise de 253.680 respostas da pesquisa BRFSS 2015 (CDC) para identificar
fatores associados a diabetes e predizer ocorrências — com validação contra
**cinco bases externas** e um **produto** aplicável.

---

## 🎯 Comece por aqui

**Se você vai apresentar:** abra `reports/deck/apresentacao.html` — 19 slides,
navegação por `←` `→`, e `Ctrl+P` exporta em PDF (paisagem, sem margens).

**Se você tem 2 minutos:** abra `reports/produto/index.html` (duplo clique,
funciona offline). É a calculadora de risco — o produto do trabalho.

**Se você quer ver a análise em Python:** `notebooks/` — seis notebooks
executados, com as saídas gravadas.

**Se você vai mexer no código:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

.\tasks.ps1 status      # o que já rodou, o que está desatualizado, o que falta
```

`status` é o mapa vivo do projeto: mostra cada etapa como **ok / OBSOLETO /
ausente**, com hash e idade de cada artefato, e aponta a próxima etapa acionável.

---

## Os 8 achados que definem o trabalho

| # | Achado | Onde |
|---|---|---|
| 1 | **Os dados vieram como PDF de 4.374 páginas.** Reconstruímos por coordenada de bounding box: 253.680 linhas, 0 em quarentena | [`docs/01`](docs/01-diagnostico-dos-dados.md) |
| 2 | **O arquivo entregue é um derivado enviesado.** Reconstruímos as 22 colunas do BRFSS original e batemos **100,000000%** célula a célula — e daí medimos: prevalência superestimada em **+3,26 p.p.** | [`docs/05`](docs/05-comparacao-brfss-original.md) |
| 3 | **96,3% do arquivo fez exame de colesterol, contra 77,9% da população.** É uma amostra de quem tem acesso ao sistema de saúde | [`docs/05` §6.3](docs/05-comparacao-brfss-original.md) |
| 4 | **Pré-diabetes não é o mesmo continuum.** Nove variáveis divergem, duas invertem de direção → modelo multinomial, não ordinal | [`docs/07` §3](docs/07-analise-explicativa.md) |
| 5 | **Brasil × EUA: 6 de 8 fatores convergem.** Hipertensão 3,136 vs 3,146 — coincidem na 3ª decimal. Mas o **IMC pesa 16% menos no Brasil** | [`docs/09`](docs/09-comparacao-binacional.md) |
| 6 | **O ganho de variáveis novas é inteiramente das minorias**: brancos −0,45 pp de recall, negros +10,6, hispânicos +10,8 | [`docs/10`](docs/10-frente1-variaveis-expandidas.md) |
| 7 | **Duas fontes independentes concordam sobre o subdiagnóstico**: BBE dá c = 0,7283, NHANES dá 0,7240. Prevalência real: **14,29%** contra 10,67% diagnosticada | [`docs/12`](docs/12-frente2-positive-unlabeled.md) |
| 8 | **Cinco perguntas batem o FINDRISC** (padrão internacional desde 2003) em +37,7 milésimos de ROC-AUC | [`docs/16`](docs/16-trilhaC-escore-decisao-equidade.md) |

---

## 🧮 O produto: calculadora de risco

`reports/produto/index.html` — **59 KB, autocontido, offline.**

12 perguntas → risco estimado, percentil populacional, comparação com 3 bases,
explicação de cada resposta, contrafactuais e o escore de papel de 5 perguntas.

**A garantia:** o EBM é aditivo, então exportamos as tabelas de consulta e a
predição roda em JavaScript com o **mesmo número** do Python.

```
casos verificados      500
erro máximo Py ↔ JS    1,110 × 10⁻¹⁶
casos com ausente      290 (todos válidos)
```

Verificado no build e na suíte de testes. Detalhe em [`docs/17`](docs/17-produto-calculadora.md).

---

## 📚 Mapa dos documentos — por pergunta

| Se a sua pergunta é… | Leia |
|---|---|
| O que é este dataset, de verdade? | [`docs/01`](docs/01-diagnostico-dos-dados.md) diagnóstico |
| Qual foi o plano de análise? | [`docs/02`](docs/02-proposta-de-analise.md) proposta |
| Com o que comparamos? | [`docs/03`](docs/03-fontes-externas.md) fontes externas |
| Como o projeto está organizado? | [`docs/04`](docs/04-arquitetura.md) arquitetura |
| O que o pré-processamento fez com os dados? | [`docs/05`](docs/05-comparacao-brfss-original.md) BRFSS original |
| Quais fatores se associam a diabetes? | [`docs/06`](docs/06-analise-exploratoria.md) EDA · [`docs/07`](docs/07-analise-explicativa.md) OR ajustado |
| Quão bem dá para predizer? | [`docs/08`](docs/08-modelagem-preditiva.md) escada de modelos |
| Vale para o Brasil? | [`docs/09`](docs/09-comparacao-binacional.md) Vigitel × BRFSS |
| O que mais dava para extrair? | [`docs/15`](docs/15-sintese-das-expansoes.md) síntese · detalhe em [`10`](docs/10-frente1-variaveis-expandidas.md)–[`14`](docs/14-frente4-medicaid-experimento-natural.md) |
| Como isso vira decisão e orçamento? | [`docs/16`](docs/16-trilhaC-escore-decisao-equidade.md) escore, custo e equidade |
| Como o produto funciona? | [`docs/17`](docs/17-produto-calculadora.md) |
| O que cada variável significa? | [`docs/dicionario-dados.md`](docs/dicionario-dados.md) |
| Por que decidimos X? | [`docs/adr/`](docs/adr/) — 5 decisões registradas |

---

## ⚙️ Reproduzir

O PDF fonte (109 MB) e o XPT do BRFSS (1,17 GB) **não estão no git** — URLs,
hashes e prova de integridade em [`data/external/FONTES.md`](data/external/FONTES.md).

```powershell
.\tasks.ps1 all          # tudo: do PDF ao produto
```

Ou etapa por etapa:

| comando | o que faz | precisa do XPT? |
|---|---|---|
| `.\tasks.ps1 ingest` | PDF → CSV (por coordenada) | não |
| `.\tasks.ps1 clean` | CSV → Parquet validado | não |
| `.\tasks.ps1 folds` | partição à prova de vazamento | não |
| `.\tasks.ps1 modelos` | escada de modelos preditivos | não |
| `.\tasks.ps1 external` | reconstrução do BRFSS + viés | **sim** |
| `.\tasks.ps1 eda` | EDA em base dupla | **sim** |
| `.\tasks.ps1 explicativo` | M1/M2/M3, odds ratio | **sim** |
| `.\tasks.ps1 expandido` | 69 variáveis + auditoria racial | **sim** |
| `.\tasks.ps1 pesos` | pesos publicáveis por raking | **sim** |
| `.\tasks.ps1 pu` | Positive-Unlabeled | **sim** |
| `.\tasks.ps1 glassbox` | EBM + predição conforme | **sim** |
| `.\tasks.ps1 trilhac` | escore, decisão, equidade | **sim** |
| `.\tasks.ps1 produto` | calculadora HTML | **sim** |
| `.\tasks.ps1 vigitel` | comparação binacional | não (baixa sozinho) |
| `.\tasks.ps1 medicaid` | DiD do Medicaid | não (usa API do CDC) |
| `.\tasks.ps1 figuras` | 6 SVG + página | não |
| `.\tasks.ps1 test` | ruff + pytest | não |
| `.\tasks.ps1 status` | **o que rodou, o que está velho** | não |
| `.\tasks.ps1 log` | histórico de execuções | não |

---

## 👥 Para o grupo — onde cada um pode pegar

O projeto está modular. Estas frentes são **independentes** e podem ser tocadas
em paralelo sem conflito:

| frente | arquivos | pré-requisito | estado |
|---|---|---|---|
| **Revisar o roteiro do deck** | `src/diabetes/produto/deck.py` | — | ✅ 19 slides prontos |
| **Revisar os notebooks** | `src/diabetes/produto/notebooks.py` | — | ✅ 6 executados |
| **Análise causal (DAG, E-value)** | `src/diabetes/causal/` | `docs/07` §5 | ⏳ não iniciado |
| **Não supervisionada (MCA, fenótipos)** | `src/diabetes/eda/` | base silver | ⏳ não iniciado |
| **Pré-diabetes como problema próprio** | `src/diabetes/models/` | `docs/07` §3.3 | ⏳ não iniciado |
| **Validação temporal 2015→2023** | `src/diabetes/external/` | baixar BRFSS 2023 | ⏳ não iniciado |
| **Recalibração do escore para o Brasil** | `src/diabetes/eval/` | Vigitel já baixado | ⏳ não iniciado |

**Como não pisar no pé do outro:**

1. `git pull` antes de começar, sempre;
2. crie um branch por frente: `git checkout -b frente/notebooks`;
3. rode `.\tasks.ps1 status` — se algo estiver **OBSOLETO**, avise o grupo antes
   de regerar (pode invalidar o trabalho de outro);
4. `.\tasks.ps1 test` antes de commitar. O CI roda o mesmo.

---

## 🧭 Convenções — as regras que sustentam o projeto

Nenhuma é estética; cada uma evita um erro concreto que já apareceu.

| # | Regra | Por quê |
|---|---|---|
| 1 | `src/diabetes/schema.py` é a **única fonte de verdade** de nome, tipo e domínio de coluna | notebook que escreve `df["IMC"]` na mão está errado por construção |
| 2 | **Nenhuma linha some em silêncio** — toda remoção vai para quarentena com o motivo | foi assim que descobrimos os 187.776 excluídos |
| 3 | **Nunca `train_test_split` aleatório** — use `features/split.py` | 23.899 duplicatas exatas contaminam 13,65% do teste |
| 4 | **Acurácia não é reportada** | responder sempre "não" acerta 84,2% |
| 5 | **Cost-sensitive, nunca SMOTE** | medido: reponderar piora o ECE em 67× |
| 6 | **Dado não é versionado; manifesto com hash é** | reprodutibilidade sem repositório de 1 GB |
| 7 | **Notebook mostra resultado, não contém lógica** | lógica em notebook não é testável nem reutilizável |
| 8 | **Toda prevalência sai em par**: não ponderada e ponderada | sozinha, a não ponderada superestima em 32,7% |
| 9 | **Comparação sempre na mesma amostra** | comparar escores em amostras diferentes já nos enganou uma vez |

---

## 📁 Estrutura

```
data/          bronze / interim / silver+gold / external   (conteúdo fora do git)
docs/          17 documentos + ADRs + dicionário + enunciado
src/diabetes/  6.500+ linhas em 33 módulos
  schema.py      contrato único de dados
  ingest/        PDF → CSV por coordenada
  clean/         7 regras rastreadas
  features/      partição sem vazamento, conjunto expandido
  eda/           associação com tamanho de efeito
  models/        escada, explicativo, PU, EBM, conforme
  eval/          escore, curva de decisão, equidade
  external/      BRFSS, Vigitel, Medicaid, pesos
  produto/       exportação do modelo e página
  viz/           figuras SVG
  pipeline/      observabilidade (status, log)
reports/
  produto/       🧮 a calculadora
  figures/       6 SVG + página com tabelas
  deck/          🎤 apresentacao.html — 19 slides, exporta em PDF
notebooks/       6 notebooks executados, com saídas
tests/           97 testes, incl. paridade Python↔JavaScript
```

---

## ✅ Estado

| | |
|---|---|
| Pipeline | **18/18 etapas coerentes** (`.\tasks.ps1 status`) |
| Testes | **100**, incluindo teste de vazamento e paridade Py↔JS |
| Lint | `ruff` limpo |
| CI | GitHub Actions verde a cada push |
| Documentos | 17 + 5 ADRs · 6 notebooks · 19 slides |
| Bases externas | BRFSS 2015 · Vigitel 2015/2023 · NHANES (prior) · CDC Open Data · painel Medicaid |

---

## Fonte dos dados

Pesquisa **BRFSS 2015** do CDC — 253.680 respostas no arquivo entregue,
**441.456** no original. Alvo `Diabetes`: 0 sem diabetes · 1 pré-diabetes ·
2 diabetes. Enunciado e dicionário original em [`docs/enunciado/`](docs/enunciado/).

**Aviso:** este é um trabalho acadêmico. Nada aqui é orientação clínica.
