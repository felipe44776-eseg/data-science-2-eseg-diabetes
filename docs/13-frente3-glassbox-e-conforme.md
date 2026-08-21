> Reproduzir: `.\tasks.ps1 glassbox` · saída `data/processed/gold/_frente3_glassbox.json`

# Frente 3 — modelo auditável e garantia de cobertura

Duas peças que resolvem problemas diferentes do mesmo entregável clínico: um
modelo que um médico pode **conferir**, e uma saída que um gestor pode **contratar**.

---

## 1. Restrições de monotonicidade — praticamente grátis

Impor a direção conhecida *a priori* no gradient boosting (`monotonic_cst`):

| | ROC-AUC | PR-AUC |
|---|---|---|
| sem restrição | 0,8534 | 0,4724 |
| **com restrição** | 0,8529 | 0,4703 |
| **custo** | −0,5 milésimos | **−0,44%** |

**Meio por cento de PR-AUC compra um modelo que não pode contradizer a fisiologia.**
Sem a restrição, nada impede o boosting de aprender, numa região rala do espaço,
que IMC maior reduz o risco — e é isso que destrói a confiança de um clínico.

Restrições impostas: `_BMI5` ↑, `_RFHYPE5` ↑, `TOLDHI2` ↑, `GENHLTH` ↑, `CHCKIDNY` ↑.

**`_AGE80` ficou deliberadamente sem restrição**, porque `docs/06` §3.1 mediu que
a prevalência **cai em 80+**. Impor monotonicidade na idade seria impor uma
crença falsa — e é o tipo de erro que a prática de "restringir tudo que parece
óbvio" produz.

---

## 2. EBM — o modelo que se pode desenhar

`logit P(y) = intercepto + Σ f_j(x_j) + Σ f_jk(x_j, x_k)`

Cada `f_j` é uma função de forma auditável. **Não é aproximação post hoc como o
SHAP: é o próprio modelo.**

| | valor |
|---|---|
| variáveis | **12** (contra 60 do boosting) |
| termos (incl. 8 interações) | 20 |
| ROC-AUC | 0,8421 |
| PR-AUC | **0,4460** |
| ECE | **0,00264** |

**O EBM com 12 variáveis atinge 94,4% do PR-AUC do boosting de 60** (0,4460 vs
0,4724), com calibração igualmente boa e interpretabilidade total.

### Importância dos termos

| termo | importância |
|---|---|
| `_AGE80` | 0,606 |
| `GENHLTH` | 0,523 |
| `_BMI5` | 0,434 |
| `_RFHYPE5` | 0,343 |
| `TOLDHI2` | 0,302 |
| **`_RACEGR3`** | **0,159** |
| `SEX` | 0,115 |
| **`TOLDHI2 & _AGE80`** | 0,112 |
| `INCOME2` | 0,084 |
| `_AGE80 & SEX` | 0,080 |

As quatro interações mais fortes **todas envolvem idade** — o efeito de
colesterol, sexo, saúde percebida e hipertensão depende da faixa etária. Nenhum
modelo aditivo puro captura isso; nenhum modelo de caixa-preta mostra isso.

### Função de forma da idade — a inflexão aparece sozinha

Contribuição ao logit:

```
 18,8   −1,387
 24,0   −1,697   ← mínimo
 32,0   −1,198
 44,0   −0,347
 52,0   −0,019   ← cruza zero
 64,0   +0,532
 72,0   +0,727
 76,0   +0,741   ← PICO
 79,8   +0,608   ← CAI
```

> **O EBM descobriu sozinho a queda em 80+** que `docs/06` §3.1 tinha medido na
> prevalência bruta e atribuído a mortalidade seletiva. É uma confirmação
> independente: a inflexão sobrevive ao ajuste por 11 outras variáveis.

Um termo linear em idade — usado em `docs/07` e em praticamente toda a literatura
de escore de risco — **superestima o risco dos mais velhos** exatamente na faixa
em que o rastreamento é mais caro.

### Função de forma do IMC — e uma correção ao que escrevemos antes

```
 15,3   −1,001   ← baixo peso: MENOR risco
 22,9   −0,538
 27,4   −0,029   ← cruza zero
 32,3   +0,549
 45,0   +1,131
```

Monotônica crescente, **sem curva em J**. Isso **corrige** o que `docs/06` §4
sugeriu: a J observada lá era artefato do arquivo entregue (baixo peso 5,40% vs.
eutrófico 5,70%). Na base ponderada os valores já eram 3,21% vs. 4,36% — sem J —
e após ajuste multivariado o baixo peso é claramente o menor risco.

`docs/06` §4 fica corrigido: a curva em J não sobrevive ao ajuste.

---

## 3. Predição conforme Mondrian — cobertura garantida por classe

Em vez de probabilidade pontual, **conjuntos de predição** com cobertura garantida
sem suposição distribucional. Mondrian = quantil calculado **por classe**, o que
importa sob 87/13: o conforme marginal entregaria cobertura quase perfeita na
classe majoritária e ruim na minoritária — exatamente onde ela importa.

| α | alvo | cobertura classe 0 | cobertura classe 1 | conjuntos ambíguos |
|---|---|---|---|---|
| 0,05 | 95% | **0,9476** | **0,9518** | 46,0% |
| 0,10 | 90% | **0,8962** | **0,9024** | 28,7% |
| 0,20 | 80% | **0,7963** | **0,8039** | 5,2% |

A garantia se cumpre nas duas classes, em todos os níveis. E o preço é explícito:
para 95% de cobertura, **46% dos casos ficam ambíguos** — o modelo diz "não sei".

> **Essa é a virtude, não o defeito.** Um classificador comum sempre responde. O
> conforme separa "sei" de "não sei", e o tamanho da região ambígua é a medida
> honesta de quanto o questionário não resolve — o mesmo teto de informação de
> `docs/08` §2.3, agora quantificado como fração de indecisão.

---

## 4. Controle de risco conforme — a resposta para o gestor

"Quero encontrar X% dos casos. Quantas pessoas preciso testar?"

| recall alvo | recall obtido | **% da população a testar** | precisão | **NNS** |
|---|---|---|---|---|
| 70% | 0,7026 | **25,0%** | 0,3685 | **2,7** |
| 80% | 0,8039 | **32,5%** | 0,3243 | **3,1** |
| 90% | 0,9019 | **44,7%** | 0,2650 | **3,8** |

O recall obtido bate o alvo nos três níveis — a calibração do limiar é feita fora
da amostra de avaliação, como o método exige.

**Leitura direta:** testando **um quarto** da população adulta encontramos **70%**
dos casos, com 2,7 testes por caso encontrado. Para chegar a 90%, é preciso testar
**quase metade** — e o NNS sobe 41%.

Com HbA1c a R$ 25–40 (tabela SUS/AMB), o custo por caso encontrado sai de
**R$ 68–108** (recall 70%) para **R$ 95–152** (recall 90%). É a curva que a
Trilha C precisava para transformar modelo em orçamento.

---

## Síntese

| # | Achado | Consequência |
|---|---|---|
| 1 | Monotonicidade custa **0,44%** de PR-AUC | Adotar por padrão — auditabilidade quase grátis |
| 2 | Impor monotonicidade na **idade seria errado** | A restrição precisa de evidência, não de intuição |
| 3 | **EBM com 12 vars = 94,4%** do boosting com 60 | O entregável clínico é o EBM |
| 4 | O EBM **redescobre a inflexão em 80+** | Confirma mortalidade seletiva após ajuste |
| 5 | **Não há curva em J no IMC** após ajuste | Corrige `docs/06` §4 |
| 6 | As 4 interações mais fortes envolvem idade | Efeito de todos os fatores é modificado pela idade |
| 7 | Conforme entrega cobertura em **ambas** as classes | Garantia contratável, e mede a indecisão |
| 8 | **Testar 25% acha 70%; testar 45% acha 90%** | Insumo direto da análise de decisão |

## Limitações

1. **EBM em 12 variáveis** — escolhidas por `docs/08` §4 e `docs/10`. Com 60 o
   modelo fica ilegível, que é o oposto do objetivo.
2. **Conforme supõe permutabilidade** entre calibração e teste. Vale aqui (mesma
   amostra, split aleatório); **não vale** para validação temporal 2015 → 2023.
3. **Custo em reais é ilustrativo** — usa faixa de tabela, não custo real de
   programa (logística, convocação, perda de seguimento).
4. **`_RACEGR3` no EBM** carrega a discussão de `docs/10` §4b. A função de forma
   dela deve ser lida como proxy social, nunca biológica.
