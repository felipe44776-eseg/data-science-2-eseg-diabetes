> Reproduzir: `.\tasks.ps1 trilhac` · saídas em `data/processed/gold/_trilhaC_*.json`

# Trilha C — do modelo à decisão

O enunciado pede *"identificar informações relevantes que possam **agregar algo de
valor**"*. Esta trilha é a resposta: transforma 16 documentos de análise em um
**instrumento aplicável** e no orçamento que ele implica.

---

## 1. O escore de 5 perguntas

`docs/08` §4 mediu que cinco variáveis entregam 89,2% do modelo de 21; `docs/13`
que o EBM de 12 entrega 94,4% do boosting de 60. Se o ganho de um modelo complexo
é de poucos pontos, o entregável correto é o que **roda numa unidade básica de
saúde sem computador**.

### A tabela de pontos

| pergunta | resposta | pontos |
|---|---|---|
| **Idade** | menos de 35 | 0 |
| | 35 a 44 | **+8** |
| | 45 a 54 | **+12** |
| | 55 a 64 | **+15** |
| | 65 ou mais | **+17** |
| **IMC** (peso ÷ altura²) | abaixo de 25 | 0 |
| | 25 a 29 | **+3** |
| | 30 a 34 | **+5** |
| | 35 ou mais | **+9** |
| **Como você avalia sua saúde?** | excelente ou muito boa | 0 |
| | boa | **+6** |
| | regular ou ruim | **+11** |
| **Já lhe disseram que tem pressão alta?** | não | 0 |
| | sim | **+7** |
| **Sexo** | feminino | 0 |
| | masculino | **+1** |

**Total: 0 a 45 pontos.**

### Do total de pontos ao risco

Os pontos são mapeados de volta para o **risco observado** na faixa — o que
recalibra o erro do arredondamento, em vez de herdá-lo:

| pontos | risco de diabetes |
|---|---|
| 0 – 9 | **0,54%** |
| 10 – 15 | 1,76% |
| 16 – 18 | 3,42% |
| 19 – 23 | 6,54% |
| 24 – 27 | 12,94% |
| 28 – 30 | 18,51% |
| 31 – 35 | 28,56% |
| **36 – 45** | **45,49%** |

Da faixa mais baixa à mais alta, o risco multiplica por **84×**.

### Como os pontos foram construídos

1. Logística **ponderada** (`_LLCPWT`) sobre as variáveis em **faixas clínicas**,
   não em quantis — os cortes de IMC são os da OMS e os de idade são os do
   rastreamento recomendado pela ADA;
2. cada coeficiente dividido pelo menor coeficiente positivo e arredondado,
   preservando a razão entre efeitos;
3. a soma mapeada para risco observado por faixa (passo 2 acima).

---

## 2. A decisão que define o escore: tirar o proxy de acesso

Testamos duas versões. A diferença é o argumento central do projeto aplicado ao
produto.

| escore | perguntas | ROC-AUC | PR-AUC |
|---|---|---|---|
| **A · completo** (inclui "tem colesterol alto?") | 6 | 0,8082 | 0,3671 |
| **B · sem proxy de acesso** | **5** | **0,8040** | 0,3595 |
| | | **−4,2 milésimos** | **−2,07%** |

*Ambos avaliados na **mesma amostra** de 62.294 pessoas do holdout. Na primeira
versão desta análise eles foram comparados em amostras diferentes — o escore A
exige colesterol não-nulo, o que já filtra por acesso. Comparar assim é
exatamente o viés que este projeto combate, e foi corrigido.*

> ### Decisão: o escore adotado é o **B**.
> "Você tem colesterol alto?" só é respondível por quem **já fez um exame de
> sangue**. `docs/05` §6.3 mostrou que o arquivo entregue tem 96,3% dessas pessoas
> contra 77,9% na população; `docs/12` mostrou que os prováveis diabéticos não
> diagnosticados são justamente os que **não fizeram exame**.
>
> Um escore que exige exame prévio **não alcança quem mais precisa dele**.
> Custa 2% de PR-AUC. É barato.

As cinco perguntas do escore B podem ser respondidas por alguém que **nunca viu
um médico** — o que é o requisito, não um detalhe.

---

## 3. Comparação com o padrão internacional

| instrumento | ROC-AUC | PR-AUC |
|---|---|---|
| **Nosso escore (5 perguntas)** | **0,8040** | **0,3595** |
| FINDRISC aproximado (5 de 8 itens) | 0,7663 | 0,3195 |
| | **+37,7 milésimos** | **+12,5%** |

**O escore de 5 perguntas bate o FINDRISC** — o instrumento de referência
internacional desde 2003 — por 37,7 milésimos de ROC-AUC, na mesma amostra.

**Ressalva honesta:** o FINDRISC original tem 8 itens e o BRFSS 2015 só permite
5 — faltam circunferência abdominal, histórico familiar e glicemia elevada
prévia. O FINDRISC completo provavelmente supera o nosso. O que a comparação
mostra é que **com o mesmo número de perguntas, nosso escore discrimina melhor**.

---

## 4. Curva de decisão — vale usar?

*Net benefit* (Vickers & Elkin, 2006) contra as duas estratégias triviais:
**rastrear todos** e **rastrear ninguém**.

| candidato | supera as triviais entre | melhor ganho |
|---|---|---|
| modelo completo (60 vars) | limiar 2% – **50%** | 0,0644 |
| **escore de 5 perguntas** | limiar 2% – **45%** | 0,0592 |
| FINDRISC aproximado | limiar 2% – 43% | 0,0518 |

Os três superam as estratégias triviais em toda a faixa clinicamente plausível de
limiar. O escore de 5 perguntas captura **92%** do ganho do modelo de 60
variáveis — e o FINDRISC, 80%.

---

## 5. Quantos testar, quantos achar, a que custo

Custo do HbA1c: **R$ 25 – 40** (faixa da tabela SUS/AMB; três valores em vez de
um, para não fingir precisão que a tabela não tem).

| % da população testada | modelo completo | **escore 5 perguntas** | FINDRISC |
|---|---|---|---|
| 5% | 26,6% dos casos · NNS 1,76 | 21,0% · NNS 2,23 | 18,4% · NNS 2,55 |
| **10%** | **46,2% · NNS 2,03** | **40,3% · NNS 2,33** | 34,3% · NNS 2,73 |
| 15% | 60,4% · NNS 2,33 | 54,4% · NNS 2,59 | 47,2% · NNS 2,98 |
| 20% | 71,2% · NNS 2,64 | 65,4% · NNS 2,87 | 58,2% · NNS 3,22 |
| 25% | 78,6% · NNS 2,98 | 73,6% · NNS 3,19 | 66,9% · NNS 3,51 |
| 30% | 85,1% · NNS 3,31 | 79,2% · NNS 3,55 | 74,2% · NNS 3,79 |

### Por faixa do escore — a tabela que um gestor usa

| faixa | risco | NNS | **custo por caso (R$ 32)** | % dos casos totais nesta faixa |
|---|---|---|---|---|
| 1 (0–9 pts) | 0,89% | 112,3 | R$ 3.593 | 3,4% |
| 2 | 4,05% | 24,7 | R$ 790 | 4,0% |
| 3 | 5,31% | 18,8 | R$ 603 | 6,5% |
| 4 | 12,49% | 8,0 | R$ 256 | 12,8% |
| 5 | 18,81% | 5,3 | R$ 170 | 12,8% |
| 6 | 29,31% | 3,4 | R$ 109 | **25,9%** |
| **7 (topo)** | **46,52%** | **2,1** | **R$ 69** | **34,6%** |

**Leitura operacional:** as duas faixas superiores concentram **60,5% dos casos**
e custam **R$ 69 a 109** por caso encontrado. A faixa mais baixa custa **R$ 3.593**
por caso — **52× mais**. Rastrear por ordem de escore não é refinamento: é a
diferença entre um programa viável e um inviável.

---

## 6. Equidade — e o problema de auditar um rótulo enviesado

Limiar **global** na especificidade de 90% (`0,2893`), que é como um programa
seria operado.

### 6.1 · Raça/etnia

| grupo | prevalência | taxa de seleção | **recall** | precisão | calibração |
|---|---|---|---|---|---|
| branco não-hispânico | 9,96% | 10,57% | 0,4815 | 0,4536 | −0,32 pp |
| **negro não-hispânico** | **14,24%** | **19,26%** | **0,6592** | 0,4876 | −0,35 pp |
| multirracial | 8,89% | 16,00% | 0,6111 | 0,3398 | +2,34 pp |
| hispânico | 10,74% | 13,67% | 0,6002 | 0,4714 | +0,02 pp |
| outro não-hispânico | 9,15% | 7,86% | **0,4078** | 0,4744 | −1,45 pp |

**Calibração é excelente em todos os grupos** (desvio máximo 2,34 pp) e a
**precisão é quase igual** (0,34 a 0,49) — quem o modelo seleciona tem
aproximadamente a mesma chance de ter a doença, independente do grupo.

O recall varia (amplitude 0,251) e, ao contrário do padrão temido, **favorece as
minorias**: o modelo com raça ajusta o risco basal e seleciona mais quem tem mais
prevalência. É `docs/10` §4 aparecendo na métrica formal.

### 6.2 · Renda e idade — onde estão as disparidades reais

| eixo | amplitude de recall |
|---|---|
| sexo | **0,0088** — praticamente perfeito |
| raça | 0,2514 |
| renda | 0,2750 |
| **idade** | **0,3501** |

A maior disparidade é **etária**: recall 0,249 em 18-44 contra 0,599 em 65+. É
consequência direta do limiar global com prevalência de 2,93% contra 23,50% —
poucos jovens ultrapassam o corte. Um programa que queira alcançar jovens em
risco precisa de **limiar por faixa etária**, e essa é uma decisão de política.

### 6.3 · A auditoria da auditoria

**Toda métrica de justiça calculada sobre um rótulo enviesado é ela mesma
enviesada.** O rótulo é *diagnóstico*, e `docs/12` mostrou que o subdiagnóstico é
maior nos grupos de menor acesso. Recalculamos tudo com o rótulo corrigido pelo PU:

| eixo | amplitude observada | **corrigida pelo PU** | direção |
|---|---|---|---|
| **raça** | 0,2514 | **0,2274** | **melhora** — parte da disparidade era artefato do rótulo |
| sexo | 0,0088 | 0,0062 | melhora |
| **renda** | 0,2750 | **0,2935** | **piora** — a disparidade real é maior |
| **idade** | 0,3501 | **0,3703** | **piora** |

> Corrigir pelo subdiagnóstico **muda a leitura da equidade — e não na mesma
> direção em todos os eixos**. Em raça, parte da disparidade aparente era
> artefato do rótulo. Em renda e idade, a disparidade **real é maior** que a
> medida, porque os grupos com pior recall também são os mais subdiagnosticados.
>
> Uma auditoria de justiça que ignora o viés de verificação **subestima a
> injustiça exatamente onde ela é pior**.

### 6.4 · A escolha normativa, declarada

Paridade demográfica, igualdade de oportunidade e calibração **não podem ser
satisfeitas simultaneamente** quando a prevalência difere entre grupos
(Kleinberg–Mullainathan–Raghavan 2016; Chouldechova 2017). A escolha é normativa,
não técnica.

**O projeto prioriza calibração e precisão iguais**, e aceita taxa de seleção
desigual. Justificativa: num programa de rastreamento, calibração igual significa
que *"risco de 30%" quer dizer a mesma coisa para todos*, e precisão igual
significa que *ninguém é testado à toa mais que os outros*. Taxa de seleção
desigual é **apropriada** quando a prevalência é desigual — selecionar negros a
19,3% e brancos a 10,6% reflete prevalência de 14,2% contra 9,96%.

---

## 7. Síntese

| # | Achado | Consequência |
|---|---|---|
| 1 | Escore de **5 perguntas**, 0–45 pontos, risco de 0,54% a 45,49% | O entregável aplicável em papel |
| 2 | Remover o proxy de acesso custa **2,07%** de PR-AUC | Barato — e o escore passa a alcançar quem nunca viu médico |
| 3 | **Bate o FINDRISC** em +37,7 milésimos com o mesmo nº de itens | Instrumento competitivo com o padrão internacional |
| 4 | Supera "rastrear todos/ninguém" entre limiar 2% e 45% | Usar o escore é melhor que não usar, em toda faixa plausível |
| 5 | Duas faixas superiores: **60,5% dos casos a R$ 69–109** | Programa viável |
| 6 | Faixa inferior: R$ 3.593 por caso, **52× mais** | Rastrear por escore é o que torna viável |
| 7 | Calibração e precisão **iguais** entre grupos raciais | O que o projeto escolheu priorizar |
| 8 | Maior disparidade é **etária** (0,3501), não racial | Limiar por faixa etária é decisão de política |
| 9 | Corrigir pelo PU **melhora** a leitura em raça e **piora** em renda/idade | Auditar sem corrigir o rótulo subestima a injustiça |

## 8. Limitações

1. **Custo em reais é ilustrativo** — faixa de tabela, não custo de programa
   (convocação, logística, perda de seguimento, confirmação diagnóstica).
2. **Escore treinado e validado nos EUA.** `docs/09` mostrou que o IMC pesa **16%
   menos no Brasil** — recalibração local é requisito, não refinamento.
3. **`saude_geral` é a variável mais forte e a mais problemática** — quem já sabe
   do diagnóstico avalia a própria saúde pior. O escore prediz bem; não explica.
4. **Sem análise de custo-efetividade completa** — falta o modelo de Markov de
   progressão da doença para converter casos encontrados em QALY.
5. **A correção PU da auditoria usa reponderação**, não rótulos verdadeiros. Só o
   NHANES individual com HbA1c permitiria a auditoria definitiva.
