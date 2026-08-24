> Reproduzir: `.\tasks.ps1 escorebr` · saída `data/processed/gold/_escore_brasil.json`

# Recalibração do escore para o Brasil

`docs/09` §2.3 mediu que o **IMC pesa menos no Brasil** e recomendou recalibração
como requisito, não refinamento. Esta frente executa isso — e o resultado é mais
nuançado do que a recomendação previa.

**Dados:** Vigitel 2015, **53.135 respondentes** com as 5 respostas completas,
peso `pesorake`. Partição própria (70/30) para não avaliar no que ajustou.

---

## 1. A harmonização que não dava para ignorar

As escalas de saúde autoavaliada diferem entre as duas pesquisas:

```
BRFSS GENHLTH   1 excelente · 2 muito boa · 3 boa · 4 regular · 5 ruim
Vigitel q74     1 muito bom · 2 bom       · 3 regular · 4 ruim · 5 muito ruim
```

O BRFSS separa "excelente" de "muito boa"; o Vigitel não. Mapeamento adotado
para os 3 níveis do escore:

| nível do escore | BRFSS | Vigitel |
|---|---|---|
| excelente / muito boa | 1–2 | 1 |
| boa | 3 | 2 |
| regular / ruim | 4–5 | 3–5 |

---

## 2. O escore americano aplicado cru ao Brasil

| | valor |
|---|---|
| **ROC-AUC** | **0,8032** |
| PR-AUC | 0,2407 |
| risco **observado** | 6,495% |
| risco **previsto** | **9,977%** |
| **razão previsto / observado** | **1,512** |
| erro absoluto | **+3,33 p.p.** |
| inclinação da calibração | 0,964 |
| intercepto da calibração | −0,581 |

> ### A discriminação transfere. A calibração não.
> O escore americano **ordena corretamente** no Brasil — ROC-AUC **0,8032**
> contra **0,8170** nos EUA. Mas **superestima o risco em 51%**.
>
> Inclinação 0,964 (quase perfeita) com intercepto −0,581 é a assinatura exata
> desse quadro: a *ordem* está certa, o *nível* está deslocado para cima.

> **Correção (auditoria).** Esta seção comparava com **0,804**, e chamava a queda
> de "2 milésimos". Aquele 0,804 era medido na *amostra comum* de `docs/16` — que
> exige colesterol não nulo e portanto está **filtrada por acesso**, o viés que o
> projeto existe para combater. O comparador correto é o desempenho de B em todo o
> holdout que ele consegue responder: **0,8170**. A queda EUA→Brasil é de
> **13,8 milésimos**, não 2.
>
> A manchete qualitativa sobrevive — 13,8 milésimos é a mesma ordem dos 11,9 que
> `docs/22` chama de "sem *concept drift*", e continua muito menor que os 51% de
> erro de nível. **A discriminação transfere; a calibração não.** Mas a margem era
> 7× menor do que dizíamos.

Num instrumento clínico, essa é a falha mais perigosa: dizer "seu risco é 28%"
quando o risco real é 18% gera rastreamento excessivo e ansiedade — e a métrica
que quase todo trabalho reporta (AUC) **não mostra o problema**.

*(PR-AUC cai de 0,3595 para 0,2407 simplesmente porque a prevalência brasileira é
metade da americana — 6,5% contra 13,3%. PR-AUC não é comparável entre populações
com prevalências diferentes; ROC-AUC é.)*

---

## 3. Onde o escore americano erra, faixa a faixa

| faixa | pontos | risco previsto (EUA) | risco observado (BR) | razão | n |
|---|---|---|---|---|---|
| 1 | 0–9 | 0,54% | 0,59% | **0,91** | 2.269 |
| 2 | 10–15 | 1,76% | 0,52% | **3,38** | 2.402 |
| 3 | 16–18 | 3,42% | 2,96% | 1,16 | 1.402 |
| 4 | 19–23 | 6,54% | 3,30% | 1,98 | 2.465 |
| 5 | 24–27 | 12,94% | 8,59% | 1,51 | 2.008 |
| 6 | 28–30 | 18,51% | 13,17% | 1,41 | 1.498 |
| 7 | 31–35 | 28,56% | 19,86% | 1,44 | 2.192 |
| **8** | **36–45** | **45,49%** | **28,71%** | **1,58** | 1.689 |

O erro **cresce com o risco**: na faixa mais alta o escore americano prevê 45,5%
onde o Brasil observa 28,7%. Usar a tabela americana no topo do escore
superestima em **17 pontos percentuais**.

---

## 4. Os pontos reajustados

| variável | nível | EUA | **Brasil** |
|---|---|---|---|
| **idade** | 35–44 | +8 | **+5** |
| | 45–54 | +12 | **+7** |
| | 55–64 | +15 | **+9** |
| | 65+ | +17 | **+10** |
| **IMC** | 25–29 | +3 | **+2** |
| | 30–34 | +5 | **+2** |
| | **35+** | **+9** | **+2** |
| **saúde** | boa | +6 | **+2** |
| | regular/ruim | +11 | **+5** |
| **hipertensão** | sim | +7 | **+4** |
| **sexo** | masculino | +1 | **+1** |

Total: **0–45 nos EUA · 0–22 no Brasil.**

Os pontos absolutos não são comparáveis (a unidade de escala difere). O que
importa é o **peso relativo** de cada fator:

| fator | peso nos EUA | peso no Brasil | razão |
|---|---|---|---|
| idade | 37,8% | **45,5%** | 1,20× |
| **IMC** | **20,0%** | **9,1%** | **0,45×** |
| saúde autoavaliada | 24,4% | 22,7% | 0,93× |
| hipertensão | 15,6% | 18,2% | 1,17× |
| sexo | 2,2% | 4,5% | 2,05× |

> **O IMC vale menos da metade no Brasil.** Idade e hipertensão ganham peso para
> compensar.

### Tabela de risco brasileira

| pontos | risco |
|---|---|
| 0–4 | 0,55% |
| 5–7 | 0,70% |
| 8–10 | 2,50% |
| 11–12 | 6,50% |
| 13–14 | 9,93% |
| 15–16 | 14,15% |
| 17–19 | 21,72% |
| **20–22** | **35,87%** |

---

## 5. Quanto a recalibração ganha

| | escore dos EUA | **escore recalibrado** |
|---|---|---|
| ROC-AUC | 0,8032 | 0,8046 |
| razão previsto/observado | **1,512** | **1,132** |
| erro de calibração | **+3,33 p.p.** | **+0,86 p.p.** |
| inclinação | 0,964 | 0,989 |
| intercepto | −0,618 | −0,172 |

**Discriminação: +1,4 milésimos — irrelevante.**
**Calibração: erro cai 75%.**

> Recalibrar não melhora a capacidade de ordenar pessoas por risco. Melhora a
> capacidade de dizer **qual é o risco**. Para triagem por ordem de fila, o
> escore americano serve. Para dizer um número a um paciente, não.

---

## 6. Por que o IMC pesa menos — três hipóteses testadas

### Hipótese 1: erro de medida por imputação · **descartada**

O Vigitel imputa peso e altura de quem não informa. Se a imputação fosse grande,
atenuaria o coeficiente.

| | |
|---|---|
| peso imputado ou não informado | 5,1% |
| altura imputada ou não informada | 7,7% |
| OR do IMC (por 5 kg/m²) **só entre não imputados**, ajustado por idade | **1,462** |

O valor entre não imputados é **praticamente idêntico ao americano** (1,454) —
mas isso é com ajuste só por idade. A imputação **não** explica a diferença.

### Hipótese 2: mediação diferencial pela hipertensão · **descartada**

Se no Brasil o IMC agisse mais *através* da hipertensão, o coeficiente cairia
mais ao ajustar por ela.

| ajuste | Brasil | EUA | razão BR/EUA |
|---|---|---|---|
| sem ajuste | 1,367 | 1,497 | 0,91 |
| + idade | 1,368 | 1,589 | 0,86 |
| + idade + hipertensão | 1,237 | 1,474 | 0,84 |
| + idade + hipertensão + saúde | 1,192 | 1,390 | 0,86 |

**A razão é estável em ~0,86 em todos os níveis.** A diferença já existe sem
ajuste nenhum e não é criada nem removida por mediação.

### Hipótese 3: o efeito do IMC **satura** no Brasil · **confirmada**

Prevalência de diabetes diagnosticado por faixa de IMC:

| faixa de IMC | Brasil | EUA | **razão BR/EUA** |
|---|---|---|---|
| < 25 | 4,16% | 4,49% | **0,93** |
| 25–29 | 8,61% | 10,04% | 0,86 |
| 30–34 | 10,77% | 16,47% | **0,65** |
| **35+** | **13,10%** | **24,71%** | **0,53** |

**A razão cai monotonicamente com o IMC.** No eutrófico os dois países são quase
iguais; na obesidade grave o Brasil tem **metade** da prevalência.

| | Brasil | EUA |
|---|---|---|
| gradiente 35+ vs. eutrófico | **3,15×** | **5,50×** |
| ganho de 30–34 para 35+ | 1,22× | 1,50× |

É exatamente por isso que o escore recalibrado dá **+2 para todas as faixas acima
de 25**: no Brasil, passar de sobrepeso para obesidade grave acrescenta pouco.

### E a leitura alternativa que precisa constar

**Pode não ser fisiologia. Pode ser diagnóstico.**

Pessoas com obesidade grave nos EUA têm mais contato com o sistema de saúde e
são mais rastreadas. Se no Brasil esse gradiente de rastreamento por IMC for
menor, a menor prevalência *diagnosticada* entre obesos brasileiros seria **menos
diagnóstico, não menos doença** — o mesmo mecanismo que `docs/05` mediu dentro
dos EUA, agora entre países.

**Não conseguimos distinguir com estes dados.** Separar exigiria a PNS 2019 com
HbA1c, que mede a doença e não o diagnóstico (`docs/03` §3.2). Fica registrado
como a limitação mais importante desta frente.

---

## 7. Síntese

| # | Achado | Consequência |
|---|---|---|
| 1 | Escore dos EUA **discrimina bem** no Brasil (ROC-AUC 0,803 vs 0,817 nos EUA) | A ordem de risco transfere |
| 2 | Mas **superestima em 51%** (razão previsto/observado 1,512) | A tabela de risco **não** transfere |
| 3 | Recalibrar ganha 1,4 milésimos de AUC e corta **75%** do erro de calibração | Recalibração é sobre nível, não sobre ordem |
| 4 | **IMC vale 0,45×** no escore brasileiro; idade e hipertensão compensam | Escore brasileiro tem forma própria |
| 5 | O efeito do IMC **satura acima de 25** no Brasil (gradiente 3,15× vs 5,50×) | Explica a queda de peso do IMC |
| 6 | Imputação e mediação **descartadas** como explicação, por medição | Duas hipóteses testadas e rejeitadas |
| 7 | Saturação pode ser **subdiagnóstico diferencial**, não fisiologia | Exige PNS 2019 com HbA1c para separar |

## 8. Limitações

1. **Vigitel cobre apenas as 27 capitais.** Renda, acesso e urbanização acima da
   média nacional — o escore recalibrado é para capitais, não para o Brasil.
2. **O alvo continua sendo diagnóstico autorrelatado** nos dois países, com
   subdiagnóstico possivelmente diferente. Ver §6.
3. **Sem validação externa brasileira.** A partição 70/30 é interna ao Vigitel
   2015; o teste honesto seria o Vigitel 2023.
4. **Cinco variáveis apenas.** O Vigitel tem outras (feijão, atividade física,
   tabagismo) que poderiam melhorar o escore brasileiro — não exploradas aqui
   para manter a comparabilidade com o americano.
