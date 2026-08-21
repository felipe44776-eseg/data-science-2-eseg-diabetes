> Reproduzir: `.\tasks.ps1 medicaid` · saída `data/external/medicaid/_frente4_medicaid.json`

# Frente 4 — expansão do Medicaid como experimento natural

## Por que esta frente

Todo o projeto gira em torno do **viés de acesso ao diagnóstico**: `docs/05` mediu
que o arquivo entregue é uma amostra de quem tem acesso; `docs/12` mostrou que os
prováveis diabéticos não diagnosticados são clinicamente idênticos aos
diagnosticados e diferem **apenas** em acesso.

Mas tudo isso foi estabelecido por **ajuste de covariáveis em dados transversais**,
que não identifica efeito causal. Em 2014, parte dos estados americanos expandiu o
Medicaid e parte não — **variação exógena de acesso**, no ano imediatamente
anterior à nossa base.

---

## Desenho

```
tratados  : 25 jurisdições que expandiram em 1/1/2014
controles : 13 que não expandiram até 2019
excluídos : adotantes escalonados (MI, NH, PA, IN, AK, MT, LA, VA, ME, WI…)

população        : adultos com renda < 25 mil USD  (os afetados)
controle interno : adultos com renda ≥ 50 mil USD  (não elegíveis)
período : 2011–2019, referência 2013. 2020+ fora (COVID)
erro-padrão : agrupado por estado
```

**Três decisões de desenho, cada uma com motivo:**

1. **Excluir os adotantes escalonados** não é conveniência. DiD com adoção
   escalonada é inconsistente sob efeito heterogêneo (Goodman-Bacon 2021).
   Com adoção única numa data, o estimador de dois períodos é válido.
2. **Wisconsin fica fora das duas listas.** Não adotou a expansão da ACA, mas
   cobriu adultos até 100% da linha de pobreza por *waiver* em 2014 — não é
   controle limpo.
3. **Estratificar por renda** dá um controle *dentro* do estado. A tripla
   diferença absorve choques estaduais que atingem todas as faixas.

Dados: `data.cdc.gov` (`dttw-5yxu`) — prevalência BRFSS por estado × ano × faixa de
renda, já ponderada pelo CDC. Painel de 682 células estado-ano-estrato.

---

## Passo 1 — o desenho está identificado?

Estudo de evento com 2013 como referência. Os coeficientes **anteriores a 2014**
são o teste de tendências paralelas.

| desfecho | maior efeito pré-2014 | algum significante? |
|---|---|---|
| diabetes | +0,448 p.p. | **não** |
| cobertura | +1,898 p.p. | **não** |
| barreira de custo | +0,000 p.p. | **não** |
| colesterol checado | +0,991 p.p. | **não** |

**Tendências paralelas se sustentam em todos os desfechos.** Nenhum coeficiente
pré-tratamento é distinguível de zero. A identificação é plausível.

---

## Passo 2 — a política funcionou? (adultos de baixa renda)

| desfecho | **efeito** | EP | IC 95% | p | média pré (trat.) | média pré (ctrl.) |
|---|---|---|---|---|---|---|
| **cobertura de saúde** | **+3,11 p.p.** | 1,58 | [0,02; 6,21] | **0,048** | 70,7% | 63,2% |
| **barreira de custo** | **−2,24 p.p.** | 1,14 | [−4,49; −0,00] | **0,050** | 27,2% | 32,9% |
| colesterol checado | +1,08 p.p. | 0,92 | [−0,73; 2,89] | 0,241 | 71,6% | 71,1% |
| **diagnóstico de diabetes** | **−0,40 p.p.** | 0,32 | [−1,03; 0,24] | 0,219 | 13,5% | 14,6% |

**A expansão aumentou o acesso**: +3,1 pontos de cobertura e −2,2 pontos de
renúncia a consulta por custo, ambos na margem da significância convencional.

**Não aumentou o diagnóstico de diabetes.** O ponto estimado é até ligeiramente
negativo.

## Passo 3 — o placebo (adultos de renda alta, não elegíveis)

| desfecho | efeito | p |
|---|---|---|
| cobertura | +0,48 p.p. | 0,087 |
| barreira de custo | −0,20 p.p. | 0,501 |
| colesterol checado | +0,32 p.p. | 0,556 |
| diabetes | +0,08 p.p. | 0,698 |

**Todos nulos.** Exatamente o esperado: a política não alcançava quem tinha renda
alta. É a validação mais forte do desenho — se os efeitos aparecessem também aqui,
seriam choques estaduais, não a política.

## Passo 4 — tripla diferença

| desfecho | efeito | IC 95% | p |
|---|---|---|---|
| barreira de custo | **−2,07 p.p.** | [−4,14; −0,00] | **0,050** |
| cobertura | +2,68 p.p. | [−0,18; 5,53] | 0,066 |
| diabetes | −0,48 p.p. | [−1,04; 0,08] | 0,090 |
| colesterol checado | +0,76 p.p. | [−1,00; 2,52] | 0,396 |

Confirma o quadro: efeito sobre acesso, nada sobre diagnóstico.

---

## Passo 5 — o passo que salva a interpretação

Um resultado nulo tem duas leituras — "não existe efeito" e "não conseguimos
medi-lo" — e confundi-las é o erro mais comum em avaliação de política. Dá para
separar, e o cálculo é direto:

```
efeito da política sobre a cobertura ....................... +3,11 p.p.
prevalência diagnosticada na baixa renda ................... 13,48%
prevalência VERDADEIRA implicada (subdiag. 27,6%) .......... 18,62%
   -> fração com diabetes OCULTO ........................... 5,14%

efeito MÁXIMO esperado sobre o diagnóstico
   = 3,11% × 5,14%  ....................................... 0,16 p.p.
      (supondo que TODO recém-coberto com diabetes oculto seja diagnosticado)

erro-padrão do desenho ..................................... 0,32 p.p.
diferença mínima detectável (poder 80%, α 5%) .............. 0,90 p.p.

                            MDE / efeito esperado = 5,7×
```

> ### O desenho não tem poder para detectar o efeito esperado — por construção.
> O efeito máximo plausível (0,16 p.p.) é **5,7 vezes menor** que a menor diferença
> que este desenho consegue detectar (0,90 p.p.). O IC de [−1,03; +0,24] **contém
> confortavelmente** o efeito esperado.
>
> **O nulo é inconclusivo, não é evidência de ausência.**

Para detectar 0,16 p.p. seria preciso um erro-padrão de ~0,06 p.p. — variância 29×
menor, ou seja, cerca de 29× mais estados-ano. Não existe esse dado.

---

## O que a frente entrega, afinal

Ela **não** responde "acesso causa diagnóstico?" — e demonstrar por que não
responde é o resultado. Mas entrega três coisas concretas:

**1. Efeito causal do Medicaid sobre acesso, medido.** +3,11 p.p. de cobertura e
−2,24 p.p. de barreira de custo entre adultos de baixa renda, com tendências
paralelas verificadas e placebo nulo. Isso valida a **premissa** de toda a cadeia
argumentativa do projeto: acesso é manipulável e responde a política.

**2. A magnitude realista do canal acesso → diagnóstico.** 0,16 p.p. no melhor
cenário. Isso **recalibra** o discurso do projeto: `docs/05` e `docs/12` mostraram
que o viés de acesso é enorme **na composição da amostra**; esta frente mostra
que o efeito de uma mudança *marginal* de acesso sobre a taxa agregada de
diagnóstico é **pequeno**. As duas coisas são compatíveis e a distinção importa.

**3. Um limite metodológico quantificado.** Qualquer estudo futuro que use
expansão do Medicaid com desfecho de prevalência de diagnóstico enfrenta o mesmo
problema. Desfechos mais sensíveis — taxa de teste de HbA1c, diagnósticos
*incidentes* em registro administrativo — teriam poder; prevalência autorrelatada
em inquérito, não.

### Uma observação que o projeto precisa absorver

A associação transversal entre acesso e diagnóstico é forte (`docs/07`:
`exame_colesterol` com OR ajustado de 3,45). O experimento natural, que remove o
confundimento, não consegue confirmar o canal causal com o poder disponível.

Isso **não invalida** o argumento de viés de verificação — que se sustenta na
composição da amostra, medida diretamente em `docs/05` §6.3. Mas é um lembrete de
que **OR ajustado grande em corte transversal não implica efeito causal grande**,
e o projeto deve continuar reportando os dois separadamente.

---

## Síntese

| # | Achado | Consequência |
|---|---|---|
| 1 | Tendências paralelas **passam** nos 4 desfechos | Desenho identificado |
| 2 | Placebo em renda alta **nulo** nos 4 desfechos | Efeitos não são choque estadual |
| 3 | **Cobertura +3,11 p.p.**, barreira de custo **−2,24 p.p.** | A política funcionou — acesso responde a política |
| 4 | Diagnóstico de diabetes: −0,40 p.p., n.s. | Nulo |
| 5 | **MDE 0,90 p.p. vs efeito esperado 0,16 p.p.** | O nulo é **inconclusivo**, e isso está provado |
| 6 | Efeito marginal de acesso sobre diagnóstico é pequeno | Recalibra a leitura de `docs/05` e `docs/12` |

## Limitações

1. **Poder insuficiente para o desfecho principal** — é o achado, e limita o resto.
2. **Dado agregado por estado-ano.** Microdados individuais dariam mais precisão e
   permitiriam controlar composição; exigiria baixar BRFSS 2011–2019 (~7 GB).
3. **Faixas de renda grosseiras.** "< 25 mil" não é o mesmo que "elegível ao
   Medicaid expandido" (138% da linha de pobreza, que varia com o tamanho da família).
   O erro de classificação atenua o efeito estimado.
4. **Autorrelato dos dois lados.** Cobertura e diagnóstico são autorrelatados.
5. **13 controles apenas**, e concentrados no Sul dos EUA — o que limita a
   generalidade mesmo com tendências paralelas verificadas.

## Fontes

- [CDC Open Data — BRFSS Prevalence Data, `dttw-5yxu`](https://data.cdc.gov/resource/dttw-5yxu.json)
- [KFF — An Overview of State Approaches to Adopting the Medicaid Expansion](https://www.kff.org/affordable-care-act/an-overview-of-state-approaches-to-adopting-the-medicaid-expansion/)
- [Congress.gov CRS — Overview of the ACA Medicaid Expansion](https://www.congress.gov/crs-product/IF10399)
- Goodman-Bacon (2021), *Difference-in-differences with variation in treatment timing*
- Bertrand, Duflo & Mullainathan (2004), *How much should we trust DiD estimates?*
