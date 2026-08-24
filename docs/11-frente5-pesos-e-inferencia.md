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
| viés | +3,262 → **+0,704 p.p.** · **78,4% removido** |

### Passo 2 — o resíduo, e a hipótese que julgamos errado

> **Correção (auditoria).** Esta seção dizia que a hipótese "convergência
> insuficiente do IPF" era **falsa**, e a Limitação 4 atribuía o resíduo ao aparo
> de peso. As duas afirmações estavam erradas, e a segunda era impossível: o aparo
> é aplicado **depois** do laço (`pesos.py`), logo não pode explicar o desvio de
> convergência. A causa real estava duas camadas acima — `features/expandido.py`
> apagava a categoria `INCOME2 == 7` (US$ 50-75 mil, 57.166 pessoas), de modo que
> a margem-alvo de renda não tinha alvo para o bin `(6,7]`. Em `pesos.py:169`, o
> `.fillna(1.0)` entregava fator **fixo 1,0** a essas 43.219 linhas (17,04% do
> arquivo) nas 300 iterações: **o alvo era inalcançável por construção e o IPF não
> podia convergir.** Ver `docs/10` e o achado #1 da auditoria.

Com a codificação de renda corrigida:

| hipótese | teste | veredito |
|---|---|---|
| células conjuntas ausentes no arquivo | contei as 192 células | **falsa** — 0 ausentes, 0,00% da massa |
| convergência insuficiente do IPF | 300 iterações, desvio após o passe | **era VERDADEIRA** — ver acima |
| aparo de peso extremo | curva de aparo abaixo | **parcial** — vale 0,04 p.p. |

O IPF agora **converge em 10 iterações, com desvio final de 5,9e-09** — contra 300
iterações empacando em 1,2e-3. E `pesos.py` passou a **falhar alto** quando uma
categoria presente na amostra não tem alvo, em vez de preencher com 1,0: a classe
de erro não pode voltar em silêncio.

**Curva do aparo — o trade-off viés × variância:**

| aparo | prevalência | viés | n efetivo | DEFF |
|---|---|---|---|---|
| 3× | 11,868% | +1,197 | 161.561 | 1,57 |
| 5× | 11,444% | +0,773 | 141.043 | 1,80 |
| **8× (adotado)** | **11,375%** | **+0,704** | **133.101** | **1,91** |
| 15× | 11,335% | +0,664 | 127.727 | 1,99 |
| sem aparo | 11,335% | +0,664 | 127.727 | 1,99 |

**Mesmo sem aparo nenhum, sobra +0,664 p.p.** O aparo em 8× custa 0,04 p.p. de
viés e devolve 4% de n efetivo — troca boa, e é a escolha adotada. Note que 15× e
"sem aparo" agora coincidem: com a renda corrigida, nenhum peso passa de 15×, o que
por si só indica um raking mais bem-comportado.

### Passo 3 — o resíduo é acesso, e isso é demonstrável

Se as margens demográficas não fecham o viés, é porque a seleção **não é
demográfica**. `docs/05` §6.3 já tinha o candidato: o arquivo tem 96,3% de pessoas
que fizeram exame de colesterol, contra **77,9%** na população ponderada.

> **Correção (auditoria).** Este parágrafo dizia **74,5%**, e esse era o valor que
> `pesos.py` usava como margem-alvo — porque calibrava contra `CHOLCHK` bruta
> ("quando foi o último exame", 1 = no último ano), enquanto o lado da amostra é
> `_CHOLCHK` ("exame nos últimos 5 anos"). Construtos diferentes. Pior: `CHOLCHK`
> só é perguntada a quem respondeu `BLOODCHO == 1`, então o alvo **excluía os
> 49.206 que nunca fizeram exame** — exatamente a população que a análise existe
> para representar. O valor correto, 77,9%, é o que `docs/05` §6.3 já publicava:
> era contradição interna. Corrigido em `pesos.py`.

Acrescentei `exame_colesterol` como margem:

| margens | prevalência | viés | **% removido** | n efetivo | DEFF |
|---|---|---|---|---|---|
| demográficas | 11,375% | +0,704 | 78,4% | 133.101 | 1,91 |
| **demográficas + acesso** | **10,455%** | **−0,216** | **93,4%** | 106.659 | **2,38** |

> **Hipótese confirmada, com uma ressalva que antes não aparecia.** Reponderar por
> acesso remove **93,4%** do viés, ao custo de subir o DEFF de 1,91 para 2,38 e
> produzir razão de pesos de 32:1.
>
> Mas o resíduo agora **troca de sinal**: era +0,144 p.p. (aquém do alvo) e passa a
> **−0,216 p.p.** (além dele). Isso muda a leitura. A afirmação anterior — "o viés
> residual era *inteiramente* de acesso" — não se sustenta: 0,345 dos 1,049 p.p.
> que atribuíamos a acesso (**32,9%**) eram o bug de codificação de renda. Acesso
> continua sendo a explicação dominante do resíduo demográfico, e agora a margem
> **ultrapassa** o alvo, o que sugere que a variável de exame captura um pouco mais
> do que só o acesso.

O aparo de 8× continua contendo os extremos, e com a renda corrigida a razão de
pesos cai de 64:1 para 32:1 — outro sinal de raking mais bem-comportado.

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
| `peso_demografico` | 78,4% do viés | 1,91 | padrão conservador; só supõe margens demográficas |
| **`peso_com_acesso`** | **93,4% do viés** | 2,38 | **recomendado** para estimar prevalência populacional |

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
   beneficiam, mas o "93,4%" não transfere automaticamente.
3. O IC continua exigindo o DEFF: com `peso_com_acesso`, multiplique o EP ingênuo
   por **√2,65 = 1,63**.
4. **Não há margem de raça** — a variável não existe no arquivo entregue. Toda
   estimativa por raça continua impossível nele (`docs/10` mostra por que isso importa).

---

## Síntese

| # | Achado | Consequência |
|---|---|---|
| 1 | **DEFF real 2,94, não 4,04** — Kish superestimava a incerteza em 7% | Nossos IC eram conservadores; nenhuma conclusão muda |
| 2 | Raking demográfico remove **78,4%** do viés | Útil, mas insuficiente sozinho |
| 3 | Células conjuntas ausentes: **zero** | Hipótese descartada por medição |
| 4 | Aparo em 8× custa 0,07 p.p. e devolve 8% de n efetivo — e evita overshoot | Escolha adotada |
| 5 | **Margem de acesso leva a 93,4%** do viés removido, com o resíduo trocando de sinal | Acesso domina o resíduo, mas não o explica inteiro |
| 6 | Entregável reutilizável para o CSV do Kaggle | 13,93% → **10,82%** contra 10,67% de referência |

## Limitações

1. **Sem margem de raça** — impossível no arquivo entregue.
2. **Pesos calibrados contra o BRFSS 2015**, que também é autorrelato. Corrigem o
   viés de *seleção*, não o de *verificação* (`docs/01` §2) — a Frente 2 trata disso.
3. **Estratos com PSU único** tratados como variância zero (convenção conservadora).
4. ~~O raking demográfico não converge a 1e-8 mesmo em 300 iterações; o desvio
   residual de margem (~0,9 p.p.) vem do aparo, não do algoritmo.~~
   **Retratado (auditoria).** As duas afirmações estavam erradas. O IPF converge em
   **10 iterações a 5,9e-09** depois que a categoria de renda apagada foi
   restaurada — ver o Passo 2. E o aparo nunca poderia explicar o desvio de
   convergência: ele é aplicado depois do laço.
