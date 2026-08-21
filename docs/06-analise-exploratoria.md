# Análise exploratória — em base dupla

> Toda estimativa aparece em par. **A diferença entre as duas colunas é o resultado**:
> mostra o que o pré-processamento fez com cada conclusão, variável a variável.
>
> **base A** — arquivo entregue · 253.680 linhas · sem peso · *o que o trabalho usaria por padrão*
> **base B** — BRFSS 2015 completo · 441.456 linhas · ponderado por `_LLCPWT` · exclusão par a par
>
> Reproduzir: `python -m diabetes.eda.comparativo --xpt data/external/brfss2015/LLCP2015.XPT`
> Saída bruta: `data/processed/gold/_eda_comparativa.json`

---

## 0. Regra que governa esta análise

Com n = 253.680, **todo p-valor dá zero**. Ele não distingue nada nesta escala e não
aparece nas tabelas. O que reportamos é **tamanho de efeito** (V de Cramér, OR, δ de Cliff)
e **intervalo de confiança** — este último corrigido pelo efeito de desenho.

**DEFF = 4,04** → n efetivo de Kish 107.736 de 435.424. Todo IC calculado como amostra
aleatória simples é **2,01× mais estreito** que o correto. Nas tabelas ponderadas abaixo,
a inferência já usa o n efetivo.

---

## 1. O desfecho

| classe | base A (sem peso) | base B (ponderada) |
|---|---|---|
| 0 — sem diabetes | 84,241% | **87,901%** |
| 1 — pré-diabetes | 1,826% | **1,599%** |
| 2 — diabetes | 13,933% | **10,500%** |

Nas seções seguintes o desfecho é **diabetes diagnosticado (classe 2) vs. resto**.
Pré-diabetes é analisado separadamente em `docs/07` — e a razão para separá-lo é um
achado, não uma conveniência.

---

## 2. Variáveis binárias — OR bruto nas duas bases

Ordenado pelo OR populacional. `Δ exposição` = quanto a prevalência da exposição no arquivo
difere da população. `Δ OR` = quanto o arquivo distorce a associação.

| variável | A % expost. | B % expost. | **Δ expos.** | A OR | **B OR** | IC 95% (B) | **Δ OR** | V (B) | efeito |
|---|---|---|---|---|---|---|---|---|---|
| `exame_colesterol` | 96,27 | 77,95 | **+18,32** | 6,43 | **7,11** | [6,48; 7,80] | −9,6% | 0,148 | pequeno |
| `hipertensao` | 42,90 | 31,98 | **+10,92** | 5,04 | **6,81** | [6,53; 7,11] | **−26,1%** | **0,293** | pequeno |
| `doenca_cardiaca` | 9,42 | 6,41 | +3,01 | 3,62 | **5,07** | [4,80; 5,36] | **−28,6%** | 0,194 | pequeno |
| `dificuldade_caminhar` | 16,82 | 13,72 | +3,10 | 3,77 | **4,79** | [4,58; 5,00] | −21,2% | 0,233 | pequeno |
| `avc` | 4,06 | 3,03 | +1,03 | 3,07 | **3,94** | [3,65; 4,26] | −22,3% | 0,114 | pequeno |
| `colesterol_alto` | 42,41 | 36,48 | +5,93 | 3,26 | **3,88** | [3,72; 4,04] | −16,0% | 0,226 | pequeno |
| `acesso_saude` | 95,11 | 87,86 | +7,25 | 1,27 | **1,81** | [1,68; 1,94] | **−30,1%** | 0,049 | desprezível |
| `fumante` | 44,32 | 41,33 | +2,99 | 1,42 | **1,59** | [1,52; 1,65] | −10,4% | 0,071 | desprezível |
| `sem_consulta_por_custo` | 8,42 | 13,23 | **−4,81** | 1,35 | **1,15** | [1,08; 1,21] | **+17,6%** | 0,015 | desprezível |
| `sexo` (masculino) | 44,03 | 48,66 | −4,63 | 1,20 | **1,10** | [1,05; 1,14] | +9,4% | 0,014 | desprezível |
| `frutas` | 63,43 | 59,69 | +3,74 | 0,79 | **0,87** | [0,83; 0,90] | −9,1% | 0,022 | desprezível |
| `vegetais` | 81,14 | 77,94 | +3,20 | 0,68 | **0,78** | [0,74; 0,81] | −12,4% | 0,034 | desprezível |
| `atividade_fisica` | 75,65 | 73,88 | +1,77 | 0,49 | **0,52** | [0,49; 0,54] | −4,9% | 0,100 | desprezível |
| `alcool_excessivo` | 5,62 | 5,78 | −0,16 | 0,37 | **0,40** | [0,35; 0,45] | −6,8% | 0,048 | desprezível |

### 2.1 · O arquivo entregue **atenua** as associações

O sinal de `Δ OR` é negativo em 11 das 14 variáveis, e a atenuação chega a **30%**:

| variável | OR no arquivo | OR na população | subestimação |
|---|---|---|---|
| `acesso_saude` | 1,27 | 1,81 | **−30,1%** |
| `doenca_cardiaca` | 3,62 | 5,07 | **−28,6%** |
| `hipertensao` | 5,04 | 6,81 | **−26,1%** |
| `avc` | 3,07 | 3,94 | −22,3% |
| `dificuldade_caminhar` | 3,77 | 4,79 | −21,2% |

**Mecanismo:** a amostra entregue é mais homogênea. Ao remover 42,5% dos respondentes —
concentrados entre os de menor acesso e menor renda —, o contraste entre expostos e não
expostos encolhe. Quem analisar só o arquivo entregue **subestima o efeito da hipertensão
em um quarto**.

Duas variáveis vão na direção oposta e o motivo é o mesmo: `sem_consulta_por_custo`
(+17,6%) e `sexo` (+9,4%) são justamente aquelas cuja *exposição* está sub-representada
no arquivo (Δ negativo).

### 2.2 · Nenhum fator isolado é forte

O maior V de Cramér é **0,293** (hipertensão) — ainda dentro de "pequeno" pela convenção de
Cohen. Onze das quatorze são "desprezíveis".

Isso não é um resultado fraco; é **o** resultado: **diabetes é multifatorial e nenhuma
variável isolada o explica.** Justifica o modelo multivariado e desqualifica de antemão
qualquer conclusão do tipo "o fator X é a causa".

### 2.3 · Três armadilhas nesta tabela

**`exame_colesterol` — OR 7,11, o maior de todos.** Não é fator de risco. Quem faz exame
descobre; quem não faz permanece na classe 0. É **detecção pura**, e no arquivo entregue a
variável tem 96,3% de um único valor (§6.3 de `docs/05`). Deve sair do modelo explicativo.

**`alcool_excessivo` — OR 0,40, aparentemente protetor.** Consumo excessivo de álcool não
protege contra diabetes. Duas explicações plausíveis e não distinguíveis com dados
transversais: (i) **causalidade reversa** — quem recebe o diagnóstico reduz o consumo;
(ii) **confundimento** — o bebedor pesado da amostra é mais jovem e mais magro. É o exemplo
canônico para o relatório de por que associação não é causa.

**`dificuldade_caminhar`, `saude_geral`, `saude_fisica_dias` — OR alto, direção invertida.**
São plausivelmente **consequência** do diabetes. O OR mede a associação; não diz quem veio
antes. Tratados formalmente em `docs/07`.

---

## 3. Variáveis ordinais — gradientes

### 3.1 · Idade: o gradiente mais forte, e o arquivo o comprime pela metade

Prevalência de diabetes (%) por faixa etária BRFSS:

| faixa | 1<br>18-24 | 2 | 3 | 4 | 5 | 6 | 7<br>50-54 | 8 | 9 | 10 | 11 | 12<br>75-79 | 13<br>80+ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** | 1,37 | 1,84 | 2,82 | 4,53 | 6,50 | 8,79 | 11,74 | 13,83 | 17,25 | 20,37 | 21,85 | 21,30 | 18,48 |
| **B** | **0,82** | 1,43 | 2,10 | 3,69 | 6,79 | 9,13 | 11,74 | 15,53 | 19,72 | 22,73 | 24,60 | **24,66** | 19,67 |

| | razão extremos |
|---|---|
| base A (arquivo) | **15,96×** |
| base B (população) | **30,02×** |

**O arquivo entregue comprime o gradiente etário quase pela metade** — porque achata as duas
pontas: superestima os jovens (1,37 vs 0,82) e subestima os mais velhos (21,85 vs 24,60).

**Não é monotônica:** a prevalência sobe até 75–79 anos (24,66%) e **cai em 80+ (19,67%)**.
Isso é **mortalidade seletiva** — diabéticos têm menor probabilidade de chegar aos 80. Não é
proteção da idade avançada, é sobrevivência diferencial. Modelar idade como linear ignora
essa inflexão; é argumento direto para spline ou GAM (Trilha B, modelo 3).

### 3.2 · Renda: gradiente forte, com inversão reveladora na base

| faixa (USD/ano) | 1<br><10k | 2<br>10-15k | 3 | 4 | 5 | 6 | 7 | 8<br>≥75k |
|---|---|---|---|---|---|---|---|---|
| **A** | 24,29 | **26,19** | 22,31 | 20,13 | 17,40 | 14,51 | 12,18 | 7,96 |
| **B** | 15,20 | **17,75** | 14,87 | 14,08 | 12,03 | 10,27 | 9,33 | 6,61 |

Razão extremos: A **3,29×** · B **2,69×**. Gradiente socioeconômico inequívoco.

**A inversão no nível 1 é o achado.** Os mais pobres (< 10 mil USD) têm *menos* diabetes
diagnosticado que a faixa imediatamente acima — nas duas bases. A leitura fisiológica seria
absurda. A leitura correta é **subdiagnóstico**: quem tem a menor renda tem o menor acesso e
menor chance de receber o diagnóstico. É o viés de verificação aparecendo diretamente no
gradiente.

### 3.3 · Escolaridade: monotônica decrescente

| nível | 1<br>nenhuma | 2<br>fundamental | 3 | 4<br>médio | 5 | 6<br>superior |
|---|---|---|---|---|---|---|
| **A** | 27,01 | 29,26 | 24,22 | 17,64 | 14,81 | 9,69 |
| **B** | 20,06 | 20,15 | 14,75 | 11,41 | 9,88 | **6,92** |

Razão extremos: A 3,02× · B 2,91×. Mesma leve inversão nos dois níveis mais baixos (n pequeno).

### 3.4 · Saúde geral autoavaliada: o único gradiente perfeitamente monotônico

| nível | 1 excelente | 2 muito boa | 3 boa | 4 regular | 5 ruim |
|---|---|---|---|---|---|
| **A** | 2,52 | 7,16 | 17,79 | 31,01 | 37,89 |
| **B** | **1,87** | 5,12 | 11,87 | 24,09 | **34,39** |

Razão extremos: A 15,06× · B **18,39×**. Monotônica em ambas.

Uma única pergunta subjetiva separa 1,87% de 34,39% de prevalência. É o preditor isolado
mais forte da base — **e é o mais problemático**: quem já sabe que tem diabetes tende a
avaliar a própria saúde pior. Ver `docs/07` §3.

---

## 4. IMC

| | base A | base B (ponderada) |
|---|---|---|
| IMC médio — com diabetes | 31,94 | 31,58 |
| IMC médio — sem diabetes | 27,81 | 27,38 |
| diferença | **+4,13** | **+4,20** |
| δ de Cliff (base A) | **0,373** — efeito **médio** | |

δ = 0,373 significa: sorteando uma pessoa com diabetes e uma sem, há **37 pontos percentuais**
mais chance de a primeira ter IMC maior. É o maior tamanho de efeito individual da base
— maior que qualquer V de Cramér.

Prevalência de diabetes por faixa da OMS:

| faixa | base A | base B (ponderada) |
|---|---|---|
| baixo peso (<18,5) | 5,40 | 3,21 |
| eutrófico (18,5–25) | 5,70 | 4,36 |
| sobrepeso (25–30) | 11,40 | 9,38 |
| obesidade I (30–35) | 19,23 | 15,36 |
| obesidade II (35–40) | 27,44 | 21,20 |
| **obesidade III (≥40)** | **33,54** | **27,48** |

Gradiente de **6,3×** entre eutrófico e obesidade III na população. Monotônico a partir do
eutrófico — o baixo peso quebra a monotonicidade (curva em J), coerente com a literatura:
inclui diabetes tipo 1 e perda de peso por doença.

---

## 5. Síntese — o que levar para a modelagem

| # | Achado | Consequência |
|---|---|---|
| 1 | OR bruto é **atenuado em até 30%** no arquivo entregue | Reportar toda associação bruta nas duas bases |
| 2 | Nenhum fator isolado passa de V = 0,29 | Modelo multivariado é obrigatório; nenhuma conclusão monocausal |
| 3 | Gradiente etário 30× na população, 16× no arquivo, **com inflexão em 80+** | Idade entra com spline/GAM, não linear |
| 4 | Renda e escolaridade invertem no nível mais baixo | Sinal de subdiagnóstico — não interpretar como proteção |
| 5 | `exame_colesterol` OR 7,11 é **detecção**, não risco | Fora do modelo explicativo (confirma `PROXIES_DE_ACESSO`) |
| 6 | `alcool_excessivo` OR 0,40 "protetor" | Caso didático de causalidade reversa; nunca reportar como efeito |
| 7 | `saude_geral` separa 1,87% de 34,39% | Preditor mais forte, mas suspeito de ser consequência |
| 8 | IMC δ = 0,373, gradiente 6,3× | Maior efeito individual; variável central de qualquer escore |

Continuação: **`docs/07-analise-explicativa.md`** — o que sobra de cada associação depois do
ajuste multivariado.
