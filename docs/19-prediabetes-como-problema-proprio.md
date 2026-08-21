> Reproduzir: `.\tasks.ps1 prediabetes` · saída `data/processed/gold/_prediabetes.json`

# Pré-diabetes como problema próprio

`docs/08` **excluiu** a classe pré-diabetes da modelagem preditiva, apoiada em
`docs/07` §3.3, que concluiu que ela era *"largamente um artefato do processo de
detecção"*. Excluir resolve o problema errado: é admitir que não sabemos o que a
classe é, não descobrir.

Esta frente testa quatro hipóteses. **Duas foram refutadas por medição** — e o
que sobra corrige a conclusão anterior.

**Dados:** BRFSS 2015, 440.658 respondentes — 375.712 sem diabetes, **7.690
pré-diabetes**, 57.256 diabetes. 66,5% fizeram exame de colesterol nos últimos
5 anos (o proxy de "foi testado").

---

## H1 · Acesso prediz pré-diabetes melhor que risco? **REFUTADA**

Se a classe fosse artefato de detecção, o bloco de **acesso** deveria predizê-la
melhor que o bloco de **risco fisiológico**.

| bloco | pré-diabetes vs. sem | *(controle)* diabetes vs. sem |
|---|---|---|
| **risco** (60 vars) | **0,7707** | **0,8521** |
| **acesso** (9 vars) | 0,6444 | 0,7254 |
| ambos (69 vars) | 0,7758 | 0,8619 |

**O risco fisiológico prediz melhor nas duas classes.** E a razão acesso/risco é
praticamente idêntica: **0,836** para pré-diabetes contra **0,851** para diabetes.

> Acesso **não** é mais importante para pré-diabetes do que para diabetes.
> A hipótese está errada e o teste é o controle: se fosse artefato de detecção,
> essa razão seria muito maior na classe 1.

---

## H2 · Condicionar em ter sido testado · **parcialmente confirmada**

| contraste | ROC-AUC |
|---|---|
| pré vs. sem — **todos** | 0,7707 |
| pré vs. sem — **só os testados** | **0,7314** |
| | **−39 milésimos** |

Parte da capacidade de predizer pré-diabetes vinha de distinguir **quem faz
exame** de quem não faz. Removida essa etapa, o modelo perde 39 milésimos.

**Mas mantém 0,7314.** Sobra sinal fisiológico real: entre pessoas que *foram
todas testadas*, o questionário ainda separa quem recebeu o rótulo.

---

## H3 · Distinguir pré-diabetes de diabetes é intrinsecamente difícil

| contraste | ROC-AUC |
|---|---|
| diabetes vs. pré-diabetes, entre os diagnosticados | **0,6685** |

Dado que a pessoa foi diagnosticada com *alguma* alteração glicêmica, o
questionário quase não distingue qual das duas. Faz sentido clínico: **a
distinção é laboratorial** — HbA1c entre 5,7 e 6,4 contra ≥ 6,5. Nenhuma
pergunta de questionário mede isso.

---

## H4 · Mesmo risco, menos diagnóstico · **CONFIRMADA**

Entre as pessoas no **decil superior de risco fisiológico** (modelo de 60
variáveis, sem nenhuma de acesso):

| grupo | n | sem diabetes | pré-diabetes | **diabetes** |
|---|---|---|---|---|
| risco alto · **testado** | 39.524 | 43,13% | 3,52% | **53,35%** |
| risco alto · **não testado** | 4.544 | 55,96% | 4,14% | **39,90%** |
| | | **+12,8 pp** | | **−13,5 pp** |

> **Mesmo risco fisiológico. 13,5 pontos percentuais menos diagnóstico.**
>
> Este é o tema central do projeto medido no contraste mais limpo possível: o
> modelo de risco não usa nenhuma variável de acesso, e ainda assim o diagnóstico
> depende de ter sido testado.

Detalhe contraintuitivo: a taxa de **pré-diabetes** é ligeiramente *maior* entre
os não testados (4,14% contra 3,52%). Com n de 4.544 e seleção não aleatória, não
tratamos isso como achado — é ruído provável.

---

## O que importa para predizer pré-diabetes

Importância por permutação, modelo com as 69 variáveis:

| # | variável | bloco | importância |
|---|---|---|---|
| 1 | **`_RACEGR3`** (raça/etnia) | risco | 0,01578 |
| 2 | `_BMI5` | risco | 0,01394 |
| 3 | `GENHLTH` | risco | 0,01235 |
| 4 | `MAXVO2_` (aptidão) | risco | 0,01074 |
| 5 | `_RFHYPE5` | risco | 0,00811 |
| 6 | `INCOME2` | risco | 0,00417 |
| 7 | `TOLDHI2` | risco | 0,00403 |
| 8 | `CHOLCHK` | **acesso** | 0,00350 |
| 9 | `QLACTLM2` | risco | 0,00329 |
| 10 | `FTJUDA1_` | risco | 0,00315 |

**Nove das dez são de risco.** Só `CHOLCHK` aparece, em oitavo — mais uma
evidência contra H1.

E **raça/etnia é a variável mais importante** para predizer pré-diabetes — mais
que IMC. Coerente com `docs/10`: onde o rótulo depende do acesso e o acesso é
estratificado por raça, raça carrega informação que nenhuma outra variável tem.

---

## A correção que esta frente produz

`docs/07` §3.3 escreveu que a classe pré-diabetes é *"largamente um artefato do
processo de detecção"*. **Medido, isso está exagerado.**

O que se sustenta:

- ✅ pré-diabetes **não é ponto intermediário** do mesmo continuum — `docs/07` §3.2
  continua válido, e H3 reforça (ROC 0,67 para separar de diabetes);
- ✅ o rótulo **depende de ter sido testado** — H2 mostra 39 milésimos, H4 mostra
  13,5 pontos percentuais;
- ❌ mas **não é majoritariamente artefato**: o risco fisiológico prediz muito
  melhor que o acesso (0,771 contra 0,644), e a proporção entre os dois é a mesma
  que para diabetes estabelecido.

**Leitura revisada:** pré-diabetes é uma classe **real, porém rara, mal medida e
condicionada à testagem**. O problema não é que ela seja artefato — é que ela é
*subamostrada de forma não aleatória* e *definida por um limiar laboratorial* que
o questionário não alcança.

### Consequência para a modelagem

| decisão anterior | revisão |
|---|---|
| excluir a classe 1 (`docs/08`) | **mantida** para o modelo de rastreamento de diabetes — a classe é rara e o alvo é outro |
| tratá-la como detecção pura | **corrigida** — tem sinal fisiológico próprio |
| — | **novo:** se o objetivo for rastrear pré-diabetes, o contraste correto é **entre os testados** (ROC 0,731), não na população geral, porque na população geral o modelo aprende parcialmente quem faz exame |

---

## Síntese

| # | Hipótese | Veredito | Número |
|---|---|---|---|
| H1 | acesso prediz melhor que risco | **refutada** | 0,644 contra 0,771 |
| H2 | condicionar em testado muda o contraste | confirmada, efeito modesto | −39 milésimos |
| H3 | separar pré de diabetes é difícil | confirmada | ROC 0,669 |
| H4 | mesmo risco, menos diagnóstico | **confirmada** | **−13,5 pp** |

## Limitações

1. **"Testado" é proxy.** Usamos exame de colesterol nos últimos 5 anos; o ideal
   seria o próprio teste de glicemia, que o BRFSS 2015 não traz de forma limpa.
2. **A classe tem 7.690 casos** (1,7%). Todos os intervalos são largos e H4 usa
   apenas 4.544 pessoas no braço não testado.
3. **Sem HbA1c.** A definição de pré-diabetes é laboratorial; qualquer modelo de
   questionário está predizendo o *rótulo*, não a condição.
4. **Raça em primeiro lugar** exige a mesma ressalva de `docs/10` §4b: proxy de
   determinantes sociais, nunca fator biológico.
