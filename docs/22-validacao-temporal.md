> Reproduzir: `.\tasks.ps1 temporal` · saída `data/processed/gold/_validacao_temporal.json`

# Validação temporal — o modelo de 2015 funciona em 2023?

Todo holdout deste projeto é **aleatório dentro de 2015**. Isso mede generalização
para *pessoas* novas, não para um *mundo* novo. Um modelo de saúde que será usado
hoje precisa sobreviver a oito anos — incluindo uma pandemia no meio.

**Este é o teste mais duro que o projeto faz.**

**Dados:** BRFSS 2015 (432.968) e BRFSS 2023 (421.745), o mesmo instrumento
aplicado com oito anos de diferença.

---

## 1. O obstáculo prático: o BRFSS renomeia tudo

Entre 2015 e 2023 o CDC reformulou perguntas e trocou sufixos:

| 2015 | 2023 |
|---|---|
| `DIABETE3` | `DIABETE4` |
| `_RFHYPE5` | `_RFHYPE6` |
| `TOLDHI2` | `TOLDHI3` |
| `CHCKIDNY` | `CHCKDNY2` |
| `ADDEPEV2` | `ADDEPEV3` |
| `INCOME2` | `INCOME3` |
| `SEX` | `SEXVAR` |
| `_RFDRHV5` | `_RFDRHV8` |

Não há atalho: o mapeamento está declarado em `EQUIVALENCIAS`, e o módulo
**falha** se não encontrar equivalente — em vez de treinar silenciosamente com a
coluna virando `NaN`.

| | |
|---|---|
| variáveis com equivalente em 2023 | **43 de 47** |
| sem equivalente de nome | `USEEQUIP`, `QLACTLM2`, `_FRTLT1`, `_VEGLT1` |
| fora por construto (módulos descontinuados) | 14 |
| **variáveis de risco comuns aos dois anos** | **42 de 60** |

O módulo de frutas e vegetais foi descontinuado — daí `_FRTLT1` e `_VEGLT1`
saírem. Os dois modelos comparados usam **as mesmas 42 variáveis**, então a
comparação é limpa.

---

## 2. O resultado

| | ROC-AUC | ECE | prevalência |
|---|---|---|---|
| holdout **2015** (interno) | **0,8495** | 0,0038 | 13,47% |
| **BRFSS 2023** (externo) | **0,8376** | 0,0070 | 14,18% |
| modelo **treinado em 2023** | 0,8396 | 0,0022 | 14,27% |

> ### O modelo de 2015 perde 11,9 milésimos em oito anos.
> E chega a **2 milésimos** de um modelo treinado nos próprios dados de 2023 —
> **99,8% do desempenho nativo**.

Traduzindo: se alguém treinasse o modelo do zero com dados de 2023, ganharia
**0,002 de ROC-AUC**. O modelo de 2015 já está praticamente ótimo para 2023.

---

## 3. Que tipo de deslocamento aconteceu

A decomposição padrão de *dataset shift* separa três casos, e o diagnóstico
importa mais que a métrica:

| tipo | o que muda | o que resolve |
|---|---|---|
| **covariate shift** | P(X) | reponderação |
| **label shift** | P(y) | recalibração |
| **concept drift** | **P(y\|X)** | **nada — precisa retreinar** |

### Covariate shift: **forte**

Um classificador que tenta distinguir 2015 de 2023 **só pelas covariáveis**
atinge **AUC 0,8237**. A população mudou bastante:

| variável | 2015 | 2023 | dif. padronizada |
|---|---|---|---|
| `INCOME2` (faixa de renda) | 5,83 | 7,01 | **+0,52** |
| `EDUCA` | 4,91 | 5,05 | +0,14 |
| **`MENTHLTH`** (dias ruins de saúde mental) | 3,29 | **4,33** | **+0,13** |
| `_SMOKER3` | 3,32 | 3,43 | +0,12 |
| `SMOKE100` | 1,57 | 1,61 | +0,10 |
| `EMPLOY1` | 2,54 | 2,32 | −0,10 |

A renda nominal subiu (inflação e mudança de faixas), a escolaridade subiu, o
tabagismo caiu — e **os dias ruins de saúde mental subiram 32%**, de 3,29 para
4,33 por mês. É a marca da pandemia nos dados.

### Label shift: **moderado**

Prevalência de diabetes diagnosticado: **13,22% → 14,18%**, um aumento de
**7,2%** em oito anos.

### Concept drift: **praticamente ausente**

É a conclusão que a distância de 2 milésimos para o modelo nativo sustenta:
**P(y|X) quase não mudou.** As mesmas variáveis, com os mesmos pesos, continuam
descrevendo quem tem diabetes.

---

## 4. Recalibrar resolve — e é barato

Recalibração de intercepto e inclinação, usando **20% dos dados de 2023**:

| | ROC-AUC | **ECE** | risco médio previsto |
|---|---|---|---|
| modelo de 2015, cru | 0,8376 | **0,00699** | 13,48% |
| **recalibrado** | 0,8373 | **0,00207** | **14,25%** |
| *(prevalência real de 2023)* | | | *14,18%* |

**O erro de calibração cai 4×** e o risco médio previsto passa de 13,50% para
14,25%, praticamente sobre a prevalência real de 14,18%.

A discriminação não muda (é a mesma ordenação); o que se corrige é o **nível** —
exatamente o mesmo padrão que `docs/18` encontrou na transposição para o Brasil.

> **Padrão que se repete no projeto:** quando o mundo muda — outro país, outro
> ano — a **ordem** transfere e o **nível** não. Discriminação é robusta,
> calibração é frágil. E recalibrar é barato: bastam 20% de dados novos.

---

## 5. Síntese

| # | Achado | Consequência |
|---|---|---|
| 1 | Perda de **11,9 milésimos** de ROC-AUC em 8 anos | O modelo envelhece bem |
| 2 | **2 milésimos** de distância para o modelo nativo de 2023 | Retreinar quase não ganha |
| 3 | Covariate shift **forte** (AUC do detector 0,824) | A população mudou muito |
| 4 | Label shift moderado: prevalência **+7,2%** | Diabetes cresceu |
| 5 | **Concept drift praticamente ausente** | A relação risco→doença é estável |
| 6 | Recalibrar corta o ECE em **4×** com 20% de dados novos | Manutenção barata |
| 7 | Dias ruins de saúde mental **+32%** (3,29 → 4,33) | A pandemia aparece nos dados |
| 8 | 42 de 60 variáveis sobrevivem à renomeação do BRFSS | Instrumento muda mais que a doença |

---

## 6. O que isso significa para o produto

A calculadora de `docs/17` usa o modelo de 2015. Esta frente diz o que fazer:

1. **Não é preciso retreinar.** O ganho seria de 2 milésimos.
2. **É preciso recalibrar.** Sem isso, ela subestima o risco em ~0,7 p.p. na
   população de hoje.
3. **A recalibração é trivial de aplicar** — um deslocamento de intercepto sobre
   o logit, que cabe na mesma tabela de consulta já exportada.

Fica como o próximo passo mais barato e de maior retorno do produto.

## 7. Limitações

0. **A comparação de renda entre anos exigiu correção.** `INCOME3` (2023) tem 7 =
   50-75k **e 9 = 100-150k**; `INCOME2` (2015) tem 7 = 50-75k. A máscara antiga
   apagava o código 7 nos dois e o 9 só em 2023, abrindo buracos **diferentes** em
   cada ano — o deslocamento medido era em parte artefato. Corrigido (auditoria):
   o `+0,38` publicado passou a **+0,52**, agora comparando as duas colunas
   íntegras. Ver `docs/10`.
1. **Duas fotos, não uma série.** Com 2015 e 2023 apenas, não dá para separar
   tendência de choque pandêmico. Os anos intermediários resolveriam.
2. **42 das 60 variáveis.** O modelo comparado é mais fraco que o de `docs/10`
   (0,8494 contra 0,8539 no mesmo holdout) porque usa menos variáveis.
3. **O alvo continua sendo diagnóstico autorrelatado** nos dois anos — e o
   rastreamento aumentou no período, então parte do +7,2% de prevalência é mais
   diagnóstico, não mais doença.
4. **A recalibração usa 20% de 2023**, o que na prática exige coletar dados
   novos. Não é gratuita, é só barata.
