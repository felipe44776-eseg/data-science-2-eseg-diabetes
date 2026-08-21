> Reproduzir: `.\tasks.ps1 naosup` · saída `data/processed/gold/_naosupervisionada.json`

# Análise não supervisionada — fenótipos, padrões e atípicos

A Trilha D de `docs/02` propunha quatro técnicas. Três produziram resultado útil;
**a quarta foi refutada por medição**, e a refutação é o achado mais informativo.

**Amostra:** 60.000 respondentes com as 17 variáveis categóricas completas.

---

## 1. MCA, não PCA — e por que isso não é preciosismo

A base é majoritariamente categórica. **PCA supõe variável contínua** e distância
euclidiana; aplicada a binárias, decompõe a variância de Bernoulli, o que não tem
interpretação. A **análise de correspondência múltipla** é o análogo correto:
opera sobre a matriz indicadora com métrica qui-quadrado.

*PCA em dados binários aparece em quase todo notebook público deste dataset. É
erro de método, não de gosto.*

### Os dois eixos que a MCA encontra

| eixo | inércia | polo negativo | polo positivo |
|---|---|---|---|
| **1** | **16,3%** | jovem · renda alta · saúde boa · sem hipertensão | **AVC · DPOC · doença renal · dificuldade de caminhar** |
| **2** | 7,1% | cardiopatia · 65+ · masculino · hipertensão | **asma · DPOC · 18-44 · depressão** |

**Eixo 1 é um gradiente de morbidade acumulada** — a dimensão dominante da base
não é diabetes, é "quantas condições a pessoa tem".

**Eixo 2 separa dois tipos de doente:** cardiometabólico idoso de um lado,
respiratório e de saúde mental jovem do outro. Nenhuma supervisão foi usada — a
estrutura clínica emergiu sozinha.

---

## 2. Cinco fenótipos de risco

k-means sobre as coordenadas da MCA (agrupar direto nas variáveis originais
repetiria o erro do PCA — sobre as coordenadas, a distância euclidiana já é a
métrica certa).

| cluster | n | % | **prevalência** | perfil modal |
|---|---|---|---|---|
| **4** | 5.528 | 9,2% | **40,12%** | 65+ · hipertensão 82% · artrite 69% · saúde ruim 76% |
| 3 | 7.593 | 12,7% | 25,76% | 45-64 · **IMC 30+ 58%** · artrite 70% · saúde ruim 57% |
| 1 | 14.596 | 24,3% | 21,34% | 65+ · hipertensão 69% · IMC 25-29 · saúde regular |
| 0 | 15.198 | 25,3% | 9,71% | 45-64 · sem hipertensão 60% · saúde boa 74% |
| **2** | 17.085 | 28,5% | **2,36%** | 18-44 · IMC < 25 · sem hipertensão 94% · saúde boa |

**Gradiente de 17× entre o fenótipo de menor e maior risco**, encontrado sem usar
o rótulo em nenhum momento.

Os clusters 3 e 1 são interessantes por serem **quase iguais em prevalência**
(25,8% e 21,3%) e clinicamente distintos: o 3 é o **obeso de meia-idade**, o 1 é
o **idoso de peso normal com hipertensão**. Dois caminhos diferentes para o mesmo
risco — o tipo de coisa que um modelo supervisionado agrega e esconde.

---

## 3. Padrões de comorbidade (FP-Growth)

Ordenado por **lift** — não por suporte, que só premia o que é comum.

| lift | confiança | suporte | combinação |
|---|---|---|---|
| **3,83** | **56,8%** | 2,4% | colesterol + hipertensão + IMC 30+ + saúde ruim |
| 3,64 | 53,9% | 2,4% | colesterol + dific. caminhar + hipertensão + IMC 30+ |
| 3,60 | 53,3% | 2,1% | dific. caminhar + hipertensão + IMC 30+ + saúde ruim |
| 3,56 | 52,7% | 2,7% | colesterol + IMC 30+ + saúde ruim |
| 3,47 | 51,4% | 2,2% | artrite + hipertensão + IMC 30+ + saúde ruim |
| 3,45 | 51,2% | 3,2% | hipertensão + IMC 30+ + saúde ruim |

> A combinação **colesterol alto + hipertensão + obesidade + saúde ruim** ocorre
> em 2,4% da população, e **56,8% dessas pessoas têm diabetes** — quase 4× a
> prevalência de base.

Três leituras:

1. **`IMC 30+` aparece em todas as seis regras principais.** Nenhuma combinação
   de alto lift dispensa a obesidade — o que reforça o IMC como variável central,
   apesar de `docs/10` ter medido que ele contribui pouco *marginalmente*.
2. **É a síndrome metabólica se montando sozinha.** Colesterol + hipertensão +
   obesidade é a definição clínica, e o algoritmo a reconstruiu sem saber dela.
3. **Uma regra de 3 condições já dá lift 3,45.** Da quarta condição em diante o
   ganho é marginal — coerente com a curva de parcimônia de `docs/08` §4.

---

## 4. Isolation Forest × Positive-Unlabeled — **a proposta refutada**

`docs/02` Trilha D propôs: *"Isolation Forest — perfis atípicos: quem tem risco
alto e não tem diagnóstico, cruza com a Trilha B5/PU"*. A ideia era que as duas
listas se confirmassem mutuamente.

| | valor |
|---|---|
| atípicos (5% superior) | 21.649 |
| PU alto (5% superior) | 21.650 |
| **interseção, entre não rotulados** | **757** |
| **esperado por acaso** | **939** |
| **lift da interseção** | **0,81** |

> ### As duas listas não se confirmam — elas se **evitam**.
> A interseção é **19% menor** que o acaso produziria.

**Por quê, e o motivo é óbvio em retrospecto:** o Isolation Forest acha perfis
**raros**; o PU acha perfis de **alto risco não testados**. Alto risco de diabetes
é *comum* — obesidade, hipertensão e idade avançada não são atípicos numa
população americana. Procurar caso oculto entre os atípicos é procurar no lugar
errado.

A proposta de `docs/02` Trilha D fica **corrigida**: atipicidade não é proxy de
caso oculto. Detecção de anomalia responde "quem é diferente", não "quem está
doente sem saber".

*(Os atípicos têm mais diabetes que a média — 19,04% contra 13,22% — mas isso é
consequência de morbidade acumulada, não sinal de subdiagnóstico.)*

### O que a interseção contém, ainda assim

As 757 pessoas na interseção:

| indicador | valor |
|---|---|
| idade média | 64,8 |
| IMC médio | **36,5** |
| % hipertensão | **96,7%** |
| % doença renal | **35,0%** |
| % fez exame de colesterol | **84,3%** |
| % de minoria racial | **61,7%** |

São pessoas de **morbidade muito alta e sem diagnóstico de diabetes** — mas
**84,3% já fizeram exame**. Não são invisíveis ao sistema: foram testadas e não
receberam o rótulo. É um grupo clinicamente interessante, e **não** o grupo que
`docs/12` identificou (aquele tinha 28,6% de check-up e 57,1% de exame).

**São duas populações diferentes, e confundi-las era o erro da proposta original.**

---

## 5. Síntese

| # | Achado | Consequência |
|---|---|---|
| 1 | MCA eixo 1 (16,3%) é **morbidade acumulada**, não diabetes | A dimensão dominante da base não é o alvo |
| 2 | Eixo 2 separa **cardiometabólico idoso** de **respiratório/mental jovem** | Estrutura clínica emerge sem supervisão |
| 3 | **Cinco fenótipos, gradiente de 17×** (2,36% a 40,12%) | Estratificação sem usar o rótulo |
| 4 | Clusters 3 e 1: mesmo risco, **caminhos clínicos distintos** | O supervisionado agrega e esconde isso |
| 5 | `IMC 30+` em **todas** as regras de maior lift | Central em combinação, mesmo com baixa contribuição marginal |
| 6 | Síndrome metabólica reconstruída sozinha (lift 3,83) | Validação externa do método |
| 7 | **Isolation Forest × PU: lift 0,81** | Proposta de `docs/02` Trilha D **refutada** |

## 6. Limitações

1. **Amostra de 60.000** por custo computacional da MCA — as estimativas de
   cluster são estáveis, mas não são a base inteira.
2. **k = 5 escolhido por interpretabilidade**, não por critério ótimo (silhueta,
   gap). Outros k dariam outras partições igualmente defensáveis.
3. **Discretização é decisão nossa** — idade em 3 faixas, IMC em 3. Outra
   discretização moveria os eixos da MCA.
4. **As regras de associação são descritivas.** Lift alto não implica mecanismo,
   e o alvo continua sendo diagnóstico, não doença.
