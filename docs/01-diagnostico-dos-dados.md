# Diagnóstico dos dados — o que o dataset realmente é

> Números apurados em `data/processed/_relatorio_limpeza.json`, gerados por
> `src/diabetes/ingest/pdf_to_csv.py` + `src/diabetes/clean/pipeline.py`.
> Nada aqui é estimativa: é contagem sobre as 253.680 linhas.

## 0. O dado não veio como dado

O professor entregou `Diabetes-2026.csv.pdf` — **109 MB, 4.374 páginas de PDF**, um CSV
renderizado como tabela. Isso não é detalhe operacional, é a primeira decisão de arquitetura:
extrair por ordem de leitura de texto é frágil (a ordem dos tokens em PDF não é garantida
pela especificação). A ingestão reconstrói as linhas **por coordenada de bounding box**,
não por ordem de fluxo.

| Verificação | Resultado |
|---|---|
| Páginas processadas | 4.374 |
| Linhas reconstruídas | **253.680** — bate exatamente com o enunciado |
| Colunas | **22** (alvo + 21 atributos) |
| Linhas em quarentena (cardinalidade ≠ 22 ou não-numérico) | **0** |
| Valores fora do domínio do dicionário | **0** |
| Nulos | **0** |
| SHA-256 do CSV reconstruído | `e2b5c90b37b68f...99c3ea57` |

Extração validada. O restante do projeto parte de um artefato com hash conhecido.

---

## 1. Os quatro problemas que definem o trabalho

Estes não são detalhes de limpeza. São as características que separam uma análise
séria de mais um notebook de Kaggle sobre este dataset.

### 1.1 — 23.899 duplicatas exatas (9,4% da base)

| Métrica | Contagem |
|---|---|
| Linhas idênticas em todas as 22 colunas | **23.899** |
| Linhas idênticas nas 21 features (ignorando o alvo) | **25.772** |

**Consequência:** `train_test_split` aleatório coloca a **mesma linha** em treino e teste.
O modelo memoriza e o AUC de teste sobe artificialmente. A maioria dos notebooks públicos
sobre `diabetes_012_health_indicators_BRFSS2015` comete exatamente isso.

**Magnitude medida** (`src/diabetes/features/split.py`, seed 42, teste 20%):

| Estratégia | Linhas de teste com gêmea idêntica no treino |
|---|---|
| `train_test_split` aleatório estratificado | **6.923 de 50.736 — 13,65%** |
| `StratifiedGroupKFold` por hash das features | **0** (auditado em CI) |

Um em cada sete registros de teste já teria sido visto no treino. Não é margem de erro:
é a diferença entre medir generalização e medir memorização.

**Mitigação adotada:** partição por grupo — chave = `blake2b` das 21 features.
227.908 grupos distintos; holdout de 19,86% separado por grupo antes de tudo.
Reportamos os dois números (com e sem vazamento) para dimensionar o efeito.

### 1.2 — 1.834 grupos com rótulo contraditório → teto de Bayes mensurável

**1.834 combinações de features aparecem com mais de um valor de `diabetes`** (6.120 linhas
envolvidas). Duas pessoas com respostas idênticas nas 21 perguntas, uma diabética e outra não.

Isso é **ruído irredutível de rótulo**, e é uma oportunidade rara: permite calcular
empiricamente um **limite superior de acurácia** (erro de Bayes na região observada).
Qualquer modelo que ultrapasse esse teto está ajustando ruído — não generalizando.

> É o argumento mais forte do trabalho: em vez de perseguir a terceira casa decimal do AUC,
> mostramos *onde fica o teto* e quanto do gap restante é irredutível.

### 1.3 — Desbalanceamento severo e assimétrico

| Classe | n | % |
|---|---|---|
| 0 — sem diabetes | 213.703 | **84,24%** |
| 1 — pré-diabetes | 4.631 | **1,83%** |
| 2 — diabetes | 35.346 | **13,93%** |

A classe 1 tem 1,8%. Um classificador que sempre responde "0" acerta 84,2%.
**Acurácia é uma métrica inútil aqui** e será rejeitada explicitamente no relatório.

### 1.4 — Códigos 77/99 já foram removidos → viés MNAR invisível

O `Mapa-dos-dados.txt` documenta `77 = não tem certeza` e `99 = recusou-se a responder`
para Renda. **Não há nenhum 77 ou 99 na base.** Ou seja: quem não declarou renda foi
excluído antes de o arquivo chegar. Não é dado limpo — é dado **truncado**.

Quem se recusa a informar renda não é aleatório (concentra extremos e desconfiança
institucional). O viés é *Missing Not At Random* e é **invisível** no arquivo entregue.
Só é mensurável comparando com o BRFSS original — **o que foi feito**.

> ✅ **MEDIDO** (`docs/05-comparacao-brfss-original.md`): **34.251 respondentes foram
> excluídos exatamente por isso**, e **40,58% de todos os 187.776 excluídos** não declararam
> renda. Eles são mais pobres (renda média 5,26 vs 6,05) e o dobro deles não completou o
> ensino médio (10,95% vs 5,40%). A hipótese está confirmada com número.

### 1.5 — Outros achados

- **IMC**: mediana 27, máximo 98, **805 registros com IMC > 60**. BRFSS trunca em 98.
  Peso/altura são autorrelatados → viés conhecido de subdeclaração de peso.
  **Marcamos com flag, não imputamos nem removemos.**
- **Todos os valores são inteiros** armazenados como `float64`. Downcast para `uint8`
  reduz a base de 44 MB para **8,6 MB em memória** — a base inteira cabe em cache L3.
- `saude_mental_dias` e `saude_fisica_dias` são **contagens zero-infladas** (0 a 30 dias).
  Tratar como contínuas é errado: exigem modelo de contagem ou binarização em faixas.

---

## 2. O que o rótulo realmente mede

Esta é a limitação conceitual central e precisa estar na primeira página do relatório final.

`Diabetes` **não mede quem tem diabetes.** Mede **quem respondeu, por telefone, que um
profissional de saúde já lhe disse que tinha diabetes.** Três vieses embutidos:

1. **Viés de verificação (ascertainment bias).** Diabetes tipo 2 é assintomática por anos.
   Segundo o NHANES (NCHS Data Brief 516, ago/2021–ago/2023), **27,6% dos adultos com
   diabetes nos EUA não sabem que têm** — ≈ 11,0 milhões de pessoas.
   Logo, a classe "0" contém positivos ocultos. Formalmente isto não é classificação
   supervisionada limpa: é **Positive-Unlabeled learning**.

2. **Pré-diabetes é quase puro artefato de acesso.** Ninguém descobre pré-diabetes sem
   exame de sangue. A classe 1 (1,8%) é, em boa medida, *"quem tem plano de saúde e fez
   check-up"*. Um modelo ingênuo para a classe 1 aprende **acesso ao sistema**, não fisiologia.

3. **Viés de autorrelato.** Peso subdeclarado, altura superdeclarada → IMC subestimado,
   especialmente em mulheres e em faixas de IMC alto.

**Implicação de modelagem:** `exame_colesterol`, `acesso_saude` e `sem_consulta_por_custo`
não são fatores de risco — são **marcadores de detecção**. Entram em bloco separado
(`schema.PROXIES_DE_ACESSO`) e o modelo é reportado com e sem eles.

---

## 3. Variáveis que são consequência, não causa

`saude_geral`, `dificuldade_caminhar` e `saude_fisica_dias` são plausivelmente
**consequência** do diabetes, não antecedente. Como os dados são **transversais**
(uma foto, sem eixo temporal), não há como distinguir.

- Em **modelo preditivo**: incluir é legítimo e melhora a performance.
- Em **modelo causal ou explicativo**: incluir é erro (condicionar em mediador/colisor).

Por isso o projeto separa formalmente **os dois modelos** — ver `docs/02-proposta-de-analise.md`.
