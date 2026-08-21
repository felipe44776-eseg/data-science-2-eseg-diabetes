> Reproduzir: `.\tasks.ps1 pesos` · saída `data/processed/gold/_frente5_pesos.json`
> e `data/processed/gold/pesos_arquivo_entregue.parquet`

# Frente 5 — inferência de amostra complexa e pesos para o arquivo entregue

Duas entregas independentes: **(A)** corrigir a inferência do projeto inteiro e
**(B)** produzir um vetor de pesos reutilizável que torne o arquivo do Kaggle
aproximadamente não-enviesado.

---

## A. Inferência de amostra complexa

Até aqui o projeto usava peso amostral no ponto estimado e **n efetivo de Kish**
na variância (`docs/07` §6.3), registrando que era aproximação. Agora com
linearização de Taylor usando `_STSTR` (estrato) e `_PSU`:

| método | prevalência | EP | IC 95% | n efetivo |
|---|---|---|---|---|
| 1 · aleatória simples (ignora peso e desenho) | **13,224%** | 0,0515 | [13,12; 13,32] | 432.968 |
| 2 · ponderado + Kish (nossa aproximação) | 10,671% | 0,0943 | [10,49; 10,86] | 107.254 |
| **3 · Taylor com `_STSTR` e `_PSU` (correto)** | **10,671%** | **0,0883** | **[10,50; 10,84]** | **122.372** |

### Insight — a aproximação de Kish errava para o lado seguro

O erro-padrão correto (0,0883) é **menor** que o de Kish (0,0943): nossa
aproximação **superestimava a incerteza em ~7%**. O motivo é que Kish só captura a
perda de eficiência por pesos desiguais; a **estratificação** do BRFSS *reduz* a
variância, e isso compensa parte da perda.

**DEFF real = 2,94**, não os 4,04 que vínhamos citando. Consequência:

- Todo IC do projeto era **conservador**, não otimista. Nenhuma conclusão publicada
  precisa ser revista — o erro era na direção segura.
- O multiplicador correto sobre o IC ingênuo é **1,71×**, não 2,01×.
- `docs/06`, `docs/07` e `CLAUDE.md` ficam corrigidos: o texto dizia "o IC é metade
  do correto". O correto é **≈58% do correto** — ainda grave, mas menos.

*(Nota: o BRFSS 2015 tem estratos com PSU único, que não contribuem variância.
Tratamos como zero, o que é a convenção conservadora — a alternativa, colapsar
estratos, exigiria decisão arbitrária.)*

---

## B. Pesos para o arquivo entregue

### Por que raking e não pós-estratificação

A tabela cruzada completa de idade × sexo × escolaridade × renda tem 192 células.
Pós-estratificação exigiria massa em todas; raking (*iterative proportional
fitting*) casa as **margens** uma a uma até convergir, o que é estável com célula
rala. É o método que o próprio CDC usa para construir `_LLCPWT`.

### Passo 1 — margens demográficas apenas

| | prevalência |
|---|---|
| arquivo entregue, sem peso | **13,933%** |
| arquivo entregue, com peso demográfico | **11,720%** |
| referência populacional (BRFSS ponderado) | **10,671%** |
| viés | +3,262 → **+1,049 p.p.** · **67,9% removido** |

### Passo 2 — o resíduo não é convergência nem aparo

Testei três hipóteses para o +1,05 p.p. residual:

| hipótese | teste | veredito |
|---|---|---|
| células conjuntas ausentes no arquivo | contei as 192 células | **falsa** — 0 ausentes, 0,00% da massa |
| convergência insuficiente do IPF | 300 iterações, desvio medido após o passe | **falsa** — melhora de 5,8e-3 para 1,2e-3 |
| aparo de peso extremo | curva de aparo abaixo | **parcial** — vale 0,07 p.p. |

**Curva do aparo — o trade-off viés × variância:**

| aparo | prevalência | viés | n efetivo | DEFF |
|---|---|---|---|---|
| 3× | 12,445% | +1,774 | 160.258 | 1,58 |
| 5× | 11,804% | +1,133 | 128.227 | 1,98 |
| **8× (adotado)** | **11,720%** | **+1,049** | **119.263** | **2,13** |
| 15× | 11,663% | +0,992 | 111.761 | 2,27 |
| sem aparo | 11,650% | +0,979 | 109.978 | 2,31 |

**Mesmo sem aparo nenhum, sobra +0,979 p.p.** O aparo em 8× custa 0,07 p.p. de
viés e devolve 8% de n efetivo — troca boa, e é a escolha adotada.

### Passo 3 — o resíduo é acesso, e isso é demonstrável

Se as margens demográficas não fecham o viés, é porque a seleção **não é
demográfica**. `docs/05` §6.3 já tinha o candidato: o arquivo tem 96,3% de pessoas
que fizeram exame de colesterol, contra 74,5% na população ponderada.

Acrescentei `exame_colesterol` como margem:

| margens | prevalência | viés | **% removido** | n efetivo | DEFF |
|---|---|---|---|---|---|
| demográficas | 11,720% | +1,049 | 67,9% | 119.263 | 2,13 |
| **demográficas + acesso** | **10,815%** | **+0,144** | **95,6%** | 95.789 | **2,65** |

> **Hipótese confirmada.** O viés residual era inteiramente de acesso. Reponderar
> por acesso remove **95,6%** do viés total, ao custo de subir o DEFF de 2,13 para
> 2,65 e produzir razão de pesos de 64:1.

O custo é modesto porque o aparo de 8× contém os extremos. *(Sem aparo, a mesma
margem produz razão de 11.337:1, DEFF 4,82 e **ultrapassa o alvo** — viés −0,61 p.p.
O aparo não é só higiene de variância; aqui ele também impede o overshoot.)*

### O que o peso não conserta

O peso reponderá **quem está na amostra**; não ressuscita quem foi excluído.
Funciona aqui porque os 3,7% sem exame de colesterol ainda existem no arquivo —
mas eles carregam sozinhos o peso de representar 25,5% da população. Se a exclusão
tivesse sido total, nenhuma reponderação salvaria.

---

## Entregável: `pesos_arquivo_entregue.parquet`

253.680 linhas, na ordem original do arquivo, com duas colunas:

| coluna | remove | DEFF | quando usar |
|---|---|---|---|
| `peso_demografico` | 67,9% do viés | 2,13 | padrão conservador; só supõe margens demográficas |
| **`peso_com_acesso`** | **95,6% do viés** | 2,65 | **recomendado** para estimar prevalência populacional |

```python
import pandas as pd, numpy as np
df = pd.read_csv("diabetes_012_health_indicators_BRFSS2015.csv")
w  = pd.read_parquet("pesos_arquivo_entregue.parquet")["peso_com_acesso"]
prev = np.average(df["Diabetes_012"] == 2, weights=w)   # 10,82% em vez de 13,93%
```

**Ressalvas de uso**, e elas importam:

1. Os pesos valem para **estimativa populacional descritiva**. Para modelagem
   preditiva, ponderar a função de perda muda o problema — ver ADR 0004.
2. Foram calibrados para a prevalência de diabetes. Outras estimativas se
   beneficiam, mas o "95,6%" não transfere automaticamente.
3. O IC continua exigindo o DEFF: com `peso_com_acesso`, multiplique o EP ingênuo
   por **√2,65 = 1,63**.
4. **Não há margem de raça** — a variável não existe no arquivo entregue. Toda
   estimativa por raça continua impossível nele (`docs/10` mostra por que isso importa).

---

## Síntese

| # | Achado | Consequência |
|---|---|---|
| 1 | **DEFF real 2,94, não 4,04** — Kish superestimava a incerteza em 7% | Nossos IC eram conservadores; nenhuma conclusão muda |
| 2 | Raking demográfico remove **67,9%** do viés | Útil, mas insuficiente sozinho |
| 3 | Células conjuntas ausentes: **zero** | Hipótese descartada por medição |
| 4 | Aparo em 8× custa 0,07 p.p. e devolve 8% de n efetivo — e evita overshoot | Escolha adotada |
| 5 | **Margem de acesso leva a 95,6%** do viés removido | O resíduo era acesso, como `docs/05` previa |
| 6 | Entregável reutilizável para o CSV do Kaggle | 13,93% → **10,82%** contra 10,67% de referência |

## Limitações

1. **Sem margem de raça** — impossível no arquivo entregue.
2. **Pesos calibrados contra o BRFSS 2015**, que também é autorrelato. Corrigem o
   viés de *seleção*, não o de *verificação* (`docs/01` §2) — a Frente 2 trata disso.
3. **Estratos com PSU único** tratados como variância zero (convenção conservadora).
4. O raking demográfico não converge a 1e-8 mesmo em 300 iterações; o desvio
   residual de margem (~0,9 p.p.) vem do aparo, não do algoritmo.
