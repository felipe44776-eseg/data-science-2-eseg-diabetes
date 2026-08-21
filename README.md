# Data Science 2 — Projeto 1 · Diabetes (BRFSS 2015)

ESEG · Prof. Marino Catarino · Felipe Marins

Análise de 253.680 respostas da pesquisa BRFSS 2015 (CDC) para **identificar fatores
associados a diabetes** e **predizer ocorrências**, com validação contra fontes externas
(BRFSS original, NHANES, Vigitel, PNS).

---

## Estado atual

| Camada | Status |
|---|---|
| Ingestão — PDF → CSV bronze | ✅ **pronta e validada** (253.680 linhas, 0 em quarentena) |
| Limpeza — CSV → Parquet silver | ✅ **pronta** (31 colunas, 7 regras rastreadas) |
| Diagnóstico dos dados | ✅ `docs/01-diagnostico-dos-dados.md` |
| Proposta de análise | ✅ `docs/02-proposta-de-analise.md` |
| Fontes externas | ✅ `docs/03-fontes-externas.md` |
| Arquitetura | ✅ `docs/04-arquitetura.md` |
| **Comparação com o BRFSS original** | ✅ **`docs/05-comparacao-brfss-original.md`** |
| **EDA bivariada em base dupla** | ✅ **`docs/06-analise-exploratoria.md`** |
| **Análise explicativa (OR ajustado)** | ✅ **`docs/07-analise-explicativa.md`** |
| **Modelagem preditiva (escada de modelos)** | ✅ **`docs/08-modelagem-preditiva.md`** |
| **Comparação binacional Brasil × EUA** | ✅ **`docs/09-comparacao-binacional.md`** |
| **Figuras** | ✅ `reports/figures/index.html` + 6 SVG |
| **Observabilidade do pipeline** | ✅ `.\tasks.ps1 status` · `.\tasks.ps1 log` |
| Trilha C (decisão, escore, fairness) / causal | ⏳ próximos passos |

---

## Comece por aqui

1. **`docs/01-diagnostico-dos-dados.md`** — o que o dataset realmente é, e os quatro
   problemas que definem o trabalho (vazamento por duplicata, teto de Bayes, viés de
   verificação, truncamento MNAR).
2. **`docs/02-proposta-de-analise.md`** — as três trilhas: explicar, predizer, decidir.
3. **`docs/03-fontes-externas.md`** — as fontes públicas de comparação e o que cada uma resolve.
4. **`docs/04-arquitetura.md`** — camadas de dado e código; por que local-first e não GCP.
5. **`docs/05-comparacao-brfss-original.md`** — o que o pré-processamento fez com os dados,
   etapa por etapa, com a fonte original do CDC ao lado.
6. **`docs/06-analise-exploratoria.md`** — associações com tamanho de efeito, arquivo e
   população lado a lado.
7. **`docs/07-analise-explicativa.md`** — OR ajustado, M1/M2/M3, mediação, e por que o alvo
   não é ordinal.
8. **`docs/08-modelagem-preditiva.md`** — a escada de modelos, e três previsões minhas que
   os dados não confirmaram.
9. **`docs/09-comparacao-binacional.md`** — Vigitel 2015 × BRFSS 2015, mesmo modelo nos dois.
10. **`docs/adr/`** — decisões técnicas com justificativa.

---

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Ver o que já rodou

```powershell
.\tasks.ps1 status   # cada etapa: ok / OBSOLETO / ausente, com hash e idade do artefato
.\tasks.ps1 log      # histórico de execuções, com duração
```

`status` marca **OBSOLETO** quando alguma entrada é mais nova que a saída — o artefato
existe mas não reflete os dados atuais — e aponta a próxima etapa acionável.

## Reproduzir do zero

O PDF fonte (109 MB) não está no git. Coloque-o em `data/raw/Diabetes-2026.csv.pdf` e:

```powershell
.\tasks.ps1 all
```

Reconstrói bronze → silver → gold → relatório. O manifesto em
`data/raw/_manifest_ingestao.json` traz o SHA-256 esperado do CSV reconstruído —
se bater, a extração está correta.

Comandos individuais em `docs/04-arquitetura.md` §3.

---

## Achados de entrada (já apurados)

| | |
|---|---|
| Linhas × colunas | 253.680 × 22 (→ 31 após derivadas) |
| Nulos / valores fora do domínio | **0** |
| Distribuição do alvo | 84,24% sem · **1,83% pré** · 13,93% diabetes |
| Duplicatas exatas | **23.899 (9,4%)** → 13,65% do teste contaminado, mas inflação medida de só 0,1–1,2% (`docs/08` §2.1) |
| Grupos com rótulo contraditório | **1.834** → teto de Bayes de 99,3%: não é a restrição (`docs/08` §2.3) |
| Códigos 77/99 de renda | **0** → amostra truncada, viés MNAR invisível |
| Registros com IMC > 60 | 805 (marcados, não removidos) |
| Base em memória após downcast | 44 MB → **8,6 MB** |

Detalhamento e implicações em `docs/01-diagnostico-dos-dados.md`.

## Confronto com a fonte original do CDC

O arquivo entregue é um derivado de 253.680 linhas de uma pesquisa com **441.456**
respondentes. Reconstruímos as 22 colunas a partir do BRFSS 2015 original e o resultado
bate **100,000000% célula a célula** — o que prova a extração, a derivação e a integridade
do download de uma vez só. A partir daí, o viés fica mensurável:

| | arquivo entregue | população real (ponderada) | viés |
|---|---|---|---|
| Prevalência de diabetes | **13,933%** | **10,500%** | **+3,43 p.p. (+32,7%)** |
| % fez exame de colesterol | **96,27%** | **77,93%** | **+18,34 p.p.** |
| % com plano de saúde | 95,11% | 87,83% | +7,28 p.p. |
| Efeito de desenho (DEFF) | assumido 1 | **4,04** | IC **2,01× mais largo** |

**73% do viés de prevalência vem do peso amostral descartado**, não do descarte de 42,5%
das linhas. E o arquivo é, na prática, uma amostra de pessoas **com** acesso ao sistema de
saúde — o que compromete estruturalmente qualquer análise de desigualdade feita só nele.

Validação final: replicando a metodologia do CDC (mediana entre as 53 jurisdições),
obtivemos **10,04%** contra os **10,0%** publicados. Passo a passo em
`docs/05-comparacao-brfss-original.md`.

---

## Estrutura

```
data/       bronze / interim / silver+gold / external   (conteúdo fora do git; manifestos versionados)
docs/       diagnóstico, proposta, fontes, arquitetura, ADRs, enunciado
src/        schema.py (contrato único) + ingest, clean, features, eda, models, eval, causal, external, viz
notebooks/  vitrine — importam de src/, não contêm lógica
reports/    figuras, tabelas, deck
tests/      pytest — inclui teste de vazamento por duplicata
```

## Convenções

- **`src/diabetes/schema.py` é a única fonte de verdade** para nome, tipo, domínio e
  semântica de coluna. Nenhum nome de coluna literal fora dele.
- Dado não é versionado; **manifesto com hash é**.
- Notebook mostra resultado, não contém lógica.
- Acurácia não é reportada (ADR 0005).

---

## Fonte dos dados

Pesquisa **BRFSS 2015** do CDC, 253.680 respostas, 21 atributos + alvo `Diabetes`
(0 sem diabetes · 1 pré-diabetes · 2 diabetes). Dicionário original em
`docs/enunciado/Mapa-dos-dados.txt`; enunciado em `docs/enunciado/`.
