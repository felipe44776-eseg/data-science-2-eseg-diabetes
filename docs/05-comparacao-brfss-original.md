# Comparação com o BRFSS 2015 original — o que o pré-processamento fez com os dados

> **Pergunta:** o arquivo entregue tem 253.680 respondentes; o BRFSS 2015 original tem
> 441.456. O que foi perdido, quem foi perdido, e quanto isso distorce as conclusões?
>
> Todos os números abaixo foram apurados nesta máquina e são reprodutíveis com
> `python -m diabetes.external.vies_amostral --xpt data/external/brfss2015/LLCP2015.XPT`.

---

## Resumo executivo

Quatro conclusões, em ordem de impacto sobre o trabalho:

| # | Conclusão | Número |
|---|---|---|
| 1 | **O arquivo entregue quase não contém pessoas sem acesso ao sistema de saúde.** 96,3% fizeram exame de colesterol; na população real são 77,9% | **+18,3 p.p.** |
| 2 | **Todo intervalo de confiança calculado no arquivo é metade do que deveria ser** — o efeito de desenho é 4,04 | **IC 2,01× mais largo** |
| 3 | A prevalência de diabetes está superestimada em um terço — e **73% disso vem do peso amostral descartado**, não do descarte de linhas | 13,93% → **10,50%** |
| 4 | Ajustado por idade, o descarte de 42,5% da amostra **quase não enviesa a prevalência de diabetes** — enviesa a composição demográfica | −0,45 p.p. |

O item 1 é o mais grave e o menos óbvio. Detalhe na Etapa 6.

---

## Etapa 1 — Obter a fonte original

**Obstáculo:** `www.cdc.gov` responde **HTTP 403** a acesso automatizado, inclusive com
cabeçalhos de navegador. `ftp.cdc.gov` e `restoredcdc.org` não expõem o arquivo de 2015.

**Solução:** espelho acadêmico da University of Montana, que republica os arquivos federais
do CDC na íntegra.

```
https://topofire.dbs.umt.edu/public_data/federal_public_datasets/
  CDC Behavioral Risk Factor Surveillance System /2015 Annual Survey Data/Data Files/LLCP2015.XPT
```

| | |
|---|---|
| Tamanho | **1.165.490.800 bytes** (bate com o `content-length` anunciado) |
| Formato | SAS Transport (XPT), descompactado |
| Última modificação no espelho | 2025-02-04 |

**Ressalva de proveniência:** é espelho, não a origem. Por isso a integridade não foi assumida
— foi **provada** nas Etapas 2 e 4.

## Etapa 2 — Validar a integridade do arquivo

```
cabeçalho: HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!...
registros: 441.456    colunas: 330    (leitura em 24 s)
```

**441.456 bate exatamente com o número documentado pelo CDC para o LLCP2015.** Primeira
evidência de integridade.

## Etapa 3 — Reconstruir as 22 colunas

Módulo `src/diabetes/external/brfss2015.py`. As regras são **declarativas** (`REGRAS`) e
instrumentadas: cada uma registra quantos respondentes derruba.

| coluna do projeto | variável BRFSS | recodificação | descarta |
|---|---|---|---|
| `diabetes` | `DIABETE3` | 1→2 · 4→1 · 2,3→0 | 7, 9 |
| `hipertensao` | `_RFHYPE5` | 1→0 · 2→1 | 9 |
| `colesterol_alto` | `TOLDHI2` | 2→0 | 7, 9 |
| `exame_colesterol` | `_CHOLCHK` | 2,3→0 | 9 |
| `imc` | `_BMI5` | ÷100, arredonda | — |
| `fumante` | `SMOKE100` | 2→0 | 7, 9 |
| `avc` | `CVDSTRK3` | 2→0 | 7, 9 |
| `doenca_cardiaca` | `_MICHD` | 2→0 | — |
| `atividade_fisica` | `_TOTINDA` | 2→0 | 9 |
| `frutas` / `vegetais` | `_FRTLT1` / `_VEGLT1` | 2→0 | 9 |
| `alcool_excessivo` | `_RFDRHV5` | 1→0 · 2→1 | 9 |
| `acesso_saude` | `HLTHPLN1` | 2→0 | 7, 9 |
| `sem_consulta_por_custo` | `MEDCOST` | 2→0 | 7, 9 |
| `saude_geral` | `GENHLTH` | — | 7, 9 |
| `saude_mental_dias` / `saude_fisica_dias` | `MENTHLTH` / `PHYSHLTH` | 88→0 | 77, 99 |
| `dificuldade_caminhar` | `DIFFWALK` | 2→0 | 7, 9 |
| `sexo` | `SEX` | 2→0 | — |
| `idade_faixa` | `_AGEG5YR` | — | 14 |
| `escolaridade` | `EDUCA` | — | 9 |
| `renda_faixa` | `INCOME2` | — | 77, 99 |

Descartadas junto, e é isto que dói: **`_LLCPWT`** (peso de pós-estratificação),
**`_STSTR`** (estrato) e **`_PSU`** (unidade primária de amostragem).

### Cascata de exclusões

| etapa | variável | critério | excluídos | restantes |
|---|---|---|---|---|
| 0 | *(qualquer)* | **valor ausente** | **97.850** | 343.606 |
| 1 | `DIABETE3` | 7, 9 | 374 | 343.232 |
| 2 | `_RFHYPE5` | 9 | 693 | 342.539 |
| 3 | `TOLDHI2` | 7, 9 | 2.707 | 339.832 |
| 4 | `_CHOLCHK` | 9 | 4.342 | 335.490 |
| 6 | `SMOKE100` | 7, 9 | 1.961 | 333.529 |
| 7 | `CVDSTRK3` | 7, 9 | 728 | 332.801 |
| 9 | `_TOTINDA` | 9 | **15.397** | 317.404 |
| 10 | `_FRTLT1` | 9 | 7.636 | 309.768 |
| 11 | `_VEGLT1` | 9 | 7.608 | 302.160 |
| 12 | `_RFDRHV5` | 9 | 3.523 | 298.637 |
| 13 | `HLTHPLN1` | 7, 9 | 492 | 298.145 |
| 14 | `MEDCOST` | 7, 9 | 436 | 297.709 |
| 15 | `GENHLTH` | 7, 9 | 515 | 297.194 |
| 16 | `MENTHLTH` | 77, 99 | 3.092 | 294.102 |
| 17 | `PHYSHLTH` | 77, 99 | 3.629 | 290.473 |
| 18 | `DIFFWALK` | 7, 9 | 775 | 289.698 |
| 20 | `_AGEG5YR` | 14 | 1.439 | 288.259 |
| 21 | `EDUCA` | 9 | 328 | 287.931 |
| 22 | `INCOME2` | **77, 99** | **34.251** | **253.680** |
| | | **total** | **187.776 (42,5%)** | **253.680** |

Duas exclusões dominam: **valores ausentes (97.850 · 52,1%)** e **renda não declarada
(34.251 · 18,2%)**.

## Etapa 4 — Provar que a reconstrução é a mesma

Teste definitivo: comparar célula a célula com o arquivo extraído do PDF do professor.

```
shapes                    (253.680, 22)  (253.680, 22)
células iguais            100,000000 %
linhas 100% iguais        253.680 de 253.680
colunas divergentes       nenhuma
multiconjunto idêntico    True
```

**Identidade perfeita, inclusive na ordem das linhas.** Isso prova quatro coisas de uma vez:

1. a extração do PDF (4.374 páginas → CSV) está correta;
2. as regras de derivação reconstruídas são exatamente as que geraram o arquivo entregue;
3. o espelho de download está íntegro — qualquer corrupção quebraria a igualdade;
4. o arquivo do professor preserva a ordem original de linhas do BRFSS.

Congelado como teste de regressão em `tests/test_brfss_reconstrucao.py`.

## Etapa 5 — Prevalência: quatro estimativas

| | estimativa | n | n efetivo | sem diabetes | pré | **diabetes** | IC 95% |
|---|---|---|---|---|---|---|---|
| **a** | arquivo entregue, **sem** peso | 253.680 | 253.680 | 84,241% | 1,826% | **13,933%** | [13,80; 14,07] |
| **b** | BRFSS completo, **sem** peso | 440.658 | 440.658 | 85,262% | 1,745% | **12,993%** | [12,89; 13,09] |
| **c** | BRFSS completo, **com `_LLCPWT`** | 440.658 | 109.019 | 87,901% | 1,599% | **10,500%** | [10,32; 10,68] |
| **d** | subamostra analítica, com peso | 253.680 | 64.117 | 85,933% | 1,786% | **12,280%** | [12,03; 12,53] |

### Decomposição do viés

```
(a) 13,933 %   arquivo entregue, sem peso
     │
     │  −0,94 p.p.   efeito do DESCARTE de 42,5% da amostra ......  27% do viés
     ▼
(b) 12,993 %   BRFSS completo, sem peso
     │
     │  −2,49 p.p.   efeito do PESO amostral descartado .........  73% do viés
     ▼
(c) 10,500 %   estimativa populacional correta
```

**Viés total: +3,43 pontos percentuais — superestimação de 32,7%.**

E o resultado contraintuitivo: **a maior parte do viés não vem de terem jogado fora
187.776 pessoas. Vem de terem jogado fora três colunas.** O peso é o problema.

## Etapa 6 — Quem foi descartado

| indicador | mantidos (253.680) | excluídos (187.776) | diferença |
|---|---|---|---|
| % renda não declarada (77/99) | 0,00 | **40,58** | +40,58 |
| % sem ensino médio completo | 5,40 | **10,95** | **+5,55** (dobro) |
| % saúde regular ou ruim | 17,21 | 20,50 | +3,29 |
| renda média (escala 1–8) | 6,05 | 5,26 | −0,79 |
| escolaridade média (1–6) | 5,05 | 4,70 | −0,35 |
| % masculino | 44,03 | 40,06 | −3,97 |
| faixa etária média (1–13) | 8,03 | 7,30 | −0,73 |
| IMC médio | 28,40 | 27,45 | −0,95 |
| % hipertensão | 42,90 | 36,94 | −5,96 |
| % diabetes | 13,93 | 11,67 | −2,27 |

Perfil dos excluídos: **mais pobres, menos escolarizados, com pior saúde autorrelatada, mais
jovens** — e com **menos diagnóstico** de diabetes e hipertensão. Menos doença registrada,
não menos doença.

### 6.1 · Ajuste por idade — corrigindo a leitura ingênua

Os excluídos são mais jovens, então parte da menor prevalência é composição, não seleção.
Padronizando pela estrutura etária dos mantidos:

| | bruta | **padronizada por idade** |
|---|---|---|
| mantidos | 13,93% | 13,93% |
| excluídos | 11,75% | **13,49%** |
| **diferença** | **−2,19 p.p.** | **−0,45 p.p.** |

**80% da diferença era efeito de idade.** Ajustado, o descarte quase não enviesa a
prevalência de diabetes. Ele enviesa a **composição socioeconômica** — que é o que importa
para qualquer análise de desigualdade.

### 6.2 · O mecanismo: um salto de questionário

A maior exclusão isolada são os **59.154 nulos em `TOLDHI2`** (colesterol alto) — 31,5% de
todas as exclusões. Investigando o motivo:

| `_CHOLCHK` entre os que têm `TOLDHI2` nulo | % |
|---|---|
| **3 — nunca fez exame de colesterol** | **84,0%** |
| 9 — não sabe / recusou | 16,0% |

**Não é recusa. É salto de questionário:** quem nunca fez exame de colesterol nunca é
perguntado se tem colesterol alto. O `dropna()` do pré-processamento removeu, portanto,
**precisamente quem nunca fez exame** — a população de menor acesso.

| | `TOLDHI2` nulo | `TOLDHI2` preenchido |
|---|---|---|
| % com plano de saúde | 78,2% | 94,5% |
| % deixou de consultar por custo | **17,6%** | 8,7% |

### 6.3 · O resultado mais grave do trabalho

| indicador de acesso | **arquivo entregue** | **população real (ponderada)** | viés |
|---|---|---|---|
| % fez exame de colesterol nos últimos 5 anos | **96,27%** | **77,93%** | **+18,34 p.p.** |
| % com plano de saúde | 95,11% | 87,83% | +7,28 p.p. |
| % deixou de consultar por custo | 8,42% | 13,27% | −4,85 p.p. |

**O arquivo entregue é uma amostra de pessoas com acesso ao sistema de saúde.** Quase um
em cada quatro americanos nunca fez exame de colesterol; no arquivo, é um em vinte e sete.

Consequências diretas, e elas reescrevem o plano de análise:

- **`exame_colesterol` é quase constante (96,3%)** — tem pouquíssima variância e o pouco que
  resta não representa a população. Como preditor, é inútil; como variável de análise de
  acesso, é enganosa. Confirma e reforça `schema.PROXIES_DE_ACESSO`.
- **Qualquer conclusão sobre desigualdade de acesso feita neste arquivo está
  estruturalmente comprometida.** A variação de acesso foi removida da amostra.
- **A classe pré-diabetes (1,83%) fica ainda mais suspeita.** Pré-diabetes só se descobre
  com exame; num arquivo onde 96,3% fizeram exame, a classe mede um subgrupo já filtrado.
- Reforça a formulação **Positive-Unlabeled**: o arquivo é enriquecido em pessoas com maior
  chance de diagnóstico, então a taxa de positivos ocultos *dentro dele* é menor que os
  27,6% do NHANES — mas a **população** que ele deveria representar tem mais.

## Etapa 7 — Efeito de desenho: o IC está pela metade

```
DEFF (Kish, pelos pesos) = 4,04
n efetivo                = 107.736  de  435.424 registros
IC verdadeiro            = 2,01 × mais largo que o ingênuo
```

BRFSS é amostra complexa: estratificada, com raking de pós-estratificação. Tratá-la como
amostra aleatória simples **subestima a variância por um fator de 4**.

**Regra operacional do projeto:** todo intervalo de confiança calculado sobre o arquivo
entregue deve ser reportado com a ressalva de que o IC populacional correto é **≈2× mais
largo**. Sem isso, a análise afirma precisão que não tem.

## Etapa 8 — Validação final contra o número publicado pelo CDC

O CDC publica, via `data.cdc.gov` (dataset `dttw-5yxu`), para 2015 / `US` / *Crude Prevalence*:

| resposta | CDC publicado |
|---|---|
| Sim (diabetes) | **10,0%** |
| Não, pré-diabetes ou borderline | 1,3% |
| Sim, gestacional | 0,8% |
| Não | 87,4% |

Nossa estimativa nacional ponderada deu **10,50%** — 0,5 p.p. acima. A explicação está no
campo `sample_size: 53` do próprio registro: **53 são jurisdições, não respondentes.**
A linha "US" do CDC é agregação entre estados, não estimativa nacional *pooled*.

Replicando a metodologia deles:

| método | resultado |
|---|---|
| **mediana entre as 53 jurisdições** | **10,04%** ← CDC publica **10,0%** |
| média entre as 53 jurisdições | 10,27% |
| *pooled* ponderado nacional | 10,50% |
| amplitude entre jurisdições | 6,8% a 16,5% |

**Reprodução exata do número oficial**, dentro do arredondamento. A pipeline está validada
de ponta a ponta: PDF → CSV → silver → BRFSS original → estimativa publicada pelo CDC.

*(A diferença entre 10,04% e 10,50% não é erro de ninguém: é a diferença entre "o estado
mediano" e "a população". Vale registrar — é o tipo de detalhe que faz uma comparação
externa ser levada a sério.)*

---

## O que muda no plano de análise

| Documento | Ajuste |
|---|---|
| `02-proposta-de-analise.md` — Trilha A | Todo IC reportado com a ressalva de DEFF ≈ 4. Análise de desigualdade de acesso **não pode** ser feita só no arquivo entregue — precisa do BRFSS completo |
| `02` — Trilha A3 (M1/M2/M3) | `exame_colesterol` sai do modelo: 96,3% de constante, sem variância útil e não representativa |
| `02` — Trilha B5 (Positive-Unlabeled) | O prior de 27,6% do NHANES é da **população**; dentro do arquivo (enriquecido em acesso) a taxa é menor. Estimar o prior condicional, não usar o valor bruto |
| `02` — Trilha B7 (fairness) | A auditoria por renda tem de rodar **também** no BRFSS completo. No arquivo entregue, os grupos de menor acesso foram removidos da amostra |
| `01-diagnostico-dos-dados.md` §1.4 | O viés MNAR de renda deixa de ser hipótese: **40,58% dos excluídos não declararam renda**, e eles são mais pobres e menos escolarizados |
| **Novo** | Toda prevalência do relatório final é reportada em par: **não ponderada (arquivo) e ponderada (BRFSS)** |

---

## Reprodução

```powershell
# 1. baixar (1,17 GB) — CDC bloqueia acesso automatizado; espelho UMT
curl -L -o data/external/brfss2015/LLCP2015.XPT "<url do espelho, em data/external/FONTES.md>"

# 2. reconstruir as 22 colunas + cascata de exclusões
python -m diabetes.external.brfss2015 --xpt data/external/brfss2015/LLCP2015.XPT

# 3. análise de viés (prevalência + perfil dos excluídos)
python -m diabetes.external.vies_amostral --xpt data/external/brfss2015/LLCP2015.XPT

# 4. teste de regressão: a reconstrução tem de bater 100% com o arquivo entregue
pytest tests/test_brfss_reconstrucao.py
```

Saídas: `data/external/brfss2015/_cascata_exclusoes.json` e `_analise_vies.json`.

## Fontes

- [CDC — 2015 BRFSS Survey Data and Documentation](https://www.cdc.gov/brfss/annual_data/annual_2015.html) (bloqueia acesso automatizado; consultado via espelho)
- [CDC Open Data — BRFSS Prevalence Data 2011–present, dataset `dttw-5yxu`](https://data.cdc.gov/resource/dttw-5yxu.json)
- [CDC — BRFSS Prevalence & Trends Data](https://www.cdc.gov/brfss/brfssprevalence/index.html)
- Espelho do XPT: University of Montana, `topofire.dbs.umt.edu` — URL completa em `data/external/FONTES.md`
