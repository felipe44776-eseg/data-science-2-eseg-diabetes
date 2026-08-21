> Reproduzir: `.\tasks.ps1 pu` · saída `data/processed/gold/_frente2_pu.json`

# Frente 2 — Positive-Unlabeled: de "quem consta" para "quem tem"

## Por que a formulação supervisionada está errada

O rótulo do BRFSS não é a doença, é o **diagnóstico autorrelatado**. NHANES:
**27,6% dos adultos com diabetes nos EUA não sabem**. Logo:

```
s = 1  ⟹  y = 1     quem foi diagnosticado tem a doença
s = 0  ⟹  y = ?     não rotulado — NÃO é negativo
```

Isto é **Positive-Unlabeled learning**. Tratar `s = 0` como negativo treina o
modelo a reproduzir o **processo de diagnóstico** — que `docs/05` mediu ser
enviesado por acesso, e `docs/10` mostrou penalizar minorias.

Seja **c = P(s=1 | y=1)**, a frequência de rotulagem. NHANES ancora c = 0,724.

---

## Passo 1 — a validação que não era esperada

`c` **não é identificável só com os dados** (Blanchard et al.): exige suposição
externa. Mas dá para estimá-lo por *Best Bin Estimation* (Garg et al. 2021):
numa região do espaço onde todos têm a doença, a fração rotulada tende a `c`.

| estimativa de c | valor |
|---|---|
| **BBE, só com os dados do BRFSS** | **0,7283** |
| **NHANES (fonte externa, laboratorial)** | **0,7240** |
| diferença | **0,0043** |

> Duas fontes completamente independentes — um inquérito telefônico de 2015 e
> um exame de sangue de 2021-2023 — concordam na terceira casa decimal sobre
> quanto do diabetes fica sem diagnóstico.

Isso valida a premissa da frente inteira. E era um resultado que podia sair
errado: se o BBE tivesse dado 0,95, a conclusão seria que não existe região pura
de positivos no espaço do questionário e a formulação SCAR não se sustentaria.

---

## Passo 2 — quanta doença está escondida

Com Elkan-Noto, `P(y=1|x) = P(s=1|x) / c`. Análise de sensibilidade ao longo da
faixa plausível de `c`, porque o valor de 2021-2023 não é necessariamente o de 2015:

| c | subdiagnóstico | prevalência **verdadeira** | diagnosticada | **oculta** |
|---|---|---|---|---|
| 0,650 | 35,0% | 15,846% | 10,671% | +5,18 p.p. |
| 0,700 | 30,0% | 14,768% | 10,671% | +4,10 p.p. |
| **0,724 (NHANES)** | **27,6%** | **14,291%** | **10,671%** | **+3,62 p.p.** |
| 0,780 | 22,0% | 13,278% | 10,671% | +2,61 p.p. |
| 0,850 | 15,0% | 12,188% | 10,671% | +1,52 p.p. |
| 0,900 | 10,0% | 11,512% | 10,671% | +0,84 p.p. |

**No ancoradouro do NHANES: prevalência verdadeira de 14,29% contra 10,67%
diagnosticada — 3,62 pontos percentuais de diabetes não diagnosticado.**

Sanidade externa: o NCHS reporta **4,5%** de diabetes não diagnosticado em adultos
(2021-2023). Nossos 3,62 p.p. para 2015 ficam na mesma ordem e ligeiramente
abaixo, o que é coerente com uma prevalência total menor em 2015.

### Ironia que vale registrar

`docs/05` mediu que o arquivo entregue **superestima** a prevalência em +3,26 p.p.
por viés de seleção. Esta frente mostra que o BRFSS completo **subestima** a
prevalência verdadeira em −3,62 p.p. por subdiagnóstico.

```
13,93%   arquivo entregue, sem peso          (viés de seleção, para cima)
10,67%   BRFSS ponderado, diagnóstico        (a referência de docs/05)
14,29%   prevalência VERDADEIRA estimada     (corrigido o subdiagnóstico)
```

Os dois vieses têm magnitude parecida e **sinais opostos**. Quem usasse o arquivo
entregue cru chegaria a 13,93% — numericamente perto dos 14,29% corretos, **pelo
motivo errado**. É o exemplo mais claro do projeto de por que dois erros que se
cancelam não são um acerto.

---

## Passo 3 — SCAR é falso aqui, e o SAR corrige

SCAR supõe `c` constante: o diagnóstico independe do perfil, dado que a pessoa tem
a doença. `docs/05` §6.3 provou o contrário — quem tem plano, faz check-up e toma
vacina é muito mais diagnosticado com a mesma doença.

Na formulação **SAR** (Bekker & Davis, 2020), `c(x)` depende do perfil. Modelamos a
**propensão de rastreamento** com o bloco de acesso (sem as variáveis de colesterol,
que seriam vazamento contra o alvo auxiliar) e a reescalamos para que a média
ponderada pelo risco bata com o ancoradouro:

| | valor |
|---|---|
| propensão de rastreamento | min 0,500 · mediana 0,765 · máx 0,876 |
| prevalência verdadeira sob **SAR** | **14,471%** |
| prevalência verdadeira sob SCAR (mesmo c) | 14,291% |

A diferença no agregado é pequena (0,18 p.p.) — mas **o agregado não é o ponto**.
O que muda é *quem* o modelo aponta, e isso aparece no passo seguinte.

### Uma decisão de implementação que era substantiva

Na primeira versão, `c(x)` podia chegar a 0,05, e `p_s/c(x)` explodia. O ranking
deixava de medir *"tem risco e não foi testado"* e passava a medir apenas *"não foi
testado"* — o perfil resultante tinha **0,0%** de exame de colesterol, ou seja,
selecionava por ausência de teste, não por doença. Limitar `c(x)` a [0,50; 0,95]
não é higiene numérica: é o que mantém a pergunta correta.

---

## Passo 4 — quem são os prováveis positivos ocultos

Os 20.000 não rotulados com maior `P(y=1|x) − P(s=1|x)`, comparados aos
diagnosticados e ao resto:

| indicador | **prováveis ocultos** | diagnosticados | demais não rotulados |
|---|---|---|---|
| n | 20.000 | 57.256 | 355.712 |
| **idade média** | **62,3** | 64,4 | 53,4 |
| **IMC médio** | **32,3** | 31,7 | 27,2 |
| **% hipertensão** | **74,7%** | **74,9%** | 32,4% |
| — | | | |
| % fez exame de colesterol | **57,1%** | 89,2% | 63,0% |
| **% check-up no último ano** | **28,6%** | **88,1%** | 73,8% |
| **% sem consulta por custo** | **23,0%** | 11,1% | 8,8% |
| % com plano de saúde | 84,0% | 95,1% | 92,3% |
| renda mediana (faixa) | **4** | 5 | 6 |
| **% de minoria racial** | **34,1%** | 29,4% | 22,2% |

> ### O achado da frente
> Os prováveis positivos ocultos têm o **perfil clínico dos diagnosticados** —
> hipertensão 74,7% contra 74,9%, IMC 32,3 contra 31,7, idade 62,3 contra 64,4 —
> e o **perfil de acesso dos excluídos**: um terço do check-up, o dobro de
> renúncia a consulta por custo, renda mais baixa e mais minorias.
>
> Clinicamente iguais a quem tem diabetes. Invisíveis para o sistema de saúde.

É exatamente a população que um programa de rastreamento deveria alcançar — e a
que um classificador supervisionado ingênuo **ignora por construção**, porque
aprendeu que "não diagnosticado" significa "saudável".

---

## O que isso muda no projeto

| documento | ajuste |
|---|---|
| `docs/08` Trilha B | o modelo de referência prediz **diagnóstico**. A versão PU prediz **doença** e é a correta para rastreamento |
| `docs/02` B5 | formulação PU deixa de ser proposta e passa a ter número: c validado em duas fontes |
| `docs/10` fairness | a lacuna racial é **maior** do que a medida: 34,1% dos ocultos são minorias contra 22,2% da base |
| Trilha C | o alvo da análise de decisão passa a ser o ranking PU, não o supervisionado |
| `docs/11` pesos | os pesos corrigem viés de **seleção**; o PU corrige viés de **verificação**. São complementares, não substitutos |

## Limitações

1. **`c` não é identificável só com os dados.** O acordo BBE ↔ NHANES é forte, mas
   ambos podem partilhar viés — e o BBE usa uma aproximação prática do estimador.
2. **`c` do NHANES é de 2021-2023**, aplicado a dados de 2015. Daí a análise de
   sensibilidade; a conclusão qualitativa é estável em toda a faixa.
3. **A propensão SAR é proxy.** Modelamos propensão de *rastreamento*, não
   `P(s=1|y=1,x)` — que não é observável. A suposição está declarada em `sar()`.
4. **Sem validação externa individual.** Só o NHANES com HbA1c permitiria conferir
   caso a caso. É a próxima fonte da fila (`docs/03` §2.1).
5. **Os "prováveis ocultos" não são diagnósticos.** São uma lista de prioridade de
   rastreamento. Chamar de "casos" seria repetir o erro que a frente combate.
