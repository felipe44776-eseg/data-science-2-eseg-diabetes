# Análise explicativa — o que sobra depois do ajuste

> Odds ratio **ajustado**, não predição. Três especificações rodadas lado a lado; a
> instabilidade entre elas é o resultado.
>
> Reproduzir: `python -m diabetes.models.explicativo --xpt data/external/brfss2015/LLCP2015.XPT`
> Saída bruta: `data/processed/gold/_modelo_explicativo.json`

| especificação | variáveis | lê-se como |
|---|---|---|
| **M1 · risco puro** | 15 — exclui proxies de acesso e possíveis consequências | fatores de risco antecedentes |
| **M2 · clínico** | 18 — M1 + saúde geral, dificuldade de caminhar, dias ruins | quadro clínico completo |
| **M3 · completo** | 21 | máxima predição, mínima interpretabilidade |

Variáveis contínuas e ordinais foram **padronizadas**: o OR é por desvio-padrão, não por
unidade. Um ponto de IMC e uma faixa etária não são grandezas comparáveis; um desvio-padrão
de cada uma é.

---

## 1. M1 — fatores de risco ajustados

Base B (ponderada) é a estimativa populacional. `Atenuação` = quanto a base A subestima.

| variável | A (arquivo) | **B (populacional)** | IC 95% (B) | atenuação |
|---|---|---|---|---|
| `hipertensao` | 2,45 | **2,39** | [2,26; 2,54] | +2,4% |
| `colesterol_alto` | 1,90 | **2,00** | [1,89; 2,11] | −5,2% |
| `idade_faixa` (por DP) | 1,48 | **1,65** | [1,60; 1,70] | −10,0% |
| `imc` (por DP) | 1,58 | **1,59** | [1,55; 1,63] | −0,9% |
| `doenca_cardiaca` | 1,56 | **1,56** | [1,45; 1,68] | +0,3% |
| `sexo` (masculino) | 1,29 | **1,24** | [1,18; 1,31] | +3,8% |
| `avc` | 1,35 | **1,22** | [1,09; 1,35] | +10,9% |
| `fumante` | 1,04 | **1,08** | [1,03; 1,14] | −3,5% |
| `saude_mental_dias` (por DP) | 1,08 | **1,06** | [1,03; 1,08] | +1,7% |
| `frutas` | 0,94 | **0,94** | [0,89; 1,00] | −0,1% |
| `vegetais` | 0,95 | **0,93** | [0,87; 0,99] | +2,7% |
| `escolaridade` (por DP) | 0,93 | **0,92** | [0,89; 0,94] | +0,9% |
| `atividade_fisica` | 0,82 | **0,85** | [0,81; 0,90] | −4,2% |
| `renda_faixa` (por DP) | 0,81 | **0,82** | [0,80; 0,84] | −0,6% |
| `alcool_excessivo` | 0,44 | **0,49** | [0,42; 0,57] | −10,7% |

### 1.1 · Correção importante à leitura de `docs/06`

Na análise **bruta**, o arquivo entregue atenuava os OR em até 30%. No modelo **ajustado**,
a maior divergência é **11%** e a mediana fica abaixo de 4%.

**O ajuste multivariado absorve a maior parte do viés de seleção.** Faz sentido: a seleção
operou por idade, renda e acesso — que agora estão no modelo como covariáveis.

Isso **reabilita parcialmente o arquivo entregue** para análise multivariada, e é um
resultado que corta contra a narrativa mais fácil. Registrar isso é o que separa análise de
retórica. As ressalvas que **permanecem**:

- os **IC continuam metade** do correto (DEFF = 4,04) — o ponto estimado é robusto, a precisão declarada não;
- **prevalência e OR bruto continuam enviesados** (`docs/05`, `docs/06`);
- **análise de desigualdade de acesso continua inviável** no arquivo — a variação foi removida.

---

## 2. Estabilidade M1 → M2 → M3: onde o efeito "some"

Base B ponderada. `NaN` = variável não entra naquela especificação.

| variável | M1 risco | M2 clínico | M3 completo | deslocamento M1→M3 |
|---|---|---|---|---|
| `hipertensao` | 2,394 | 2,110 | 2,080 | **−13,1%** |
| `colesterol_alto` | 2,000 | 1,877 | 1,852 | −7,4% |
| `idade_faixa` | 1,645 | 1,639 | 1,626 | −1,2% |
| `imc` | 1,589 | 1,515 | 1,511 | −4,9% |
| `doenca_cardiaca` | 1,556 | 1,261 | 1,252 | **−19,5%** |
| `sexo` | 1,240 | 1,249 | 1,258 | +1,5% |
| `avc` | 1,215 | 1,059 | 1,063 | **−12,5%** |
| `fumante` | 1,082 | 1,032 | 1,041 | −3,8% |
| `saude_mental_dias` | 1,058 | 0,951 | 0,951 | **−10,1% · inverte** |
| `escolaridade` | 0,917 | 0,975 | 0,973 | +6,1% |
| `renda_faixa` | 0,818 | 0,907 | 0,904 | **+10,5%** |
| `atividade_fisica` | 0,852 | 0,988 | 0,978 | **+14,8%** |
| `alcool_excessivo` | 0,491 | 0,513 | 0,516 | +5,1% |
| — | | | | |
| `saude_geral` | — | **1,781** | 1,787 | entra em M2 |
| `dificuldade_caminhar` | — | 1,096 | 1,076 | entra em M2 |
| `saude_fisica_dias` | — | 0,959 | 0,954 | entra em M2 |
| `exame_colesterol` | — | — | **3,448** | entra em M3 |
| `acesso_saude` | — | — | 1,170 | entra em M3 |
| `sem_consulta_por_custo` | — | — | 1,102 | entra em M3 |

### 2.1 · O efeito protetor da atividade física **desaparece**

```
M1 (risco puro)  atividade_fisica  OR 0,852   protetor, IC [0,81; 0,90]
M2 (+ saúde geral, dificuldade de caminhar, dias ruins)
                 atividade_fisica  OR 0,988   sem efeito
```

Ao entrar `saude_geral`, o efeito da atividade física evapora. Isso é **mediação**, e é a
leitura errada mais provável do trabalho inteiro:

- se `saude_geral` é **mediador** (fazer atividade física → melhor saúde percebida →
  menos diabetes), condicionar nela **bloqueia o caminho causal** e o M2 subestima o efeito
  real da atividade física;
- se `saude_geral` é **consequência** do diabetes, condicionar nela abre viés de colisor.

Nos dois casos, **M2 e M3 não podem ser lidos como "atividade física não importa"**. Quem
quiser o efeito da atividade física deve olhar M1 — e mesmo assim com a ressalva de dados
transversais.

O mesmo padrão, mais fraco, atinge `renda_faixa` (0,818 → 0,907): parte do efeito da renda
passa por saúde autoavaliada.

### 2.2 · `saude_mental_dias` inverte de sinal

M1: OR 1,058 (mais dias ruins → mais diabetes). M2: OR 0,951 (menos). Uma variável que troca
de direção ao mudar o conjunto de controles não sustenta interpretação causal em nenhuma das
duas especificações. **Não deve ser reportada como fator** — só como componente preditivo.

### 2.3 · `exame_colesterol` OR 3,45 ajustado confirma o diagnóstico do `docs/05`

Mesmo controlando pelas outras 20 variáveis, ter feito exame de colesterol multiplica por
**3,4** a chance de constar como diabético. Nenhum mecanismo fisiológico explica isso. É
**detecção**: o modelo M3 aprende quem foi testado, não quem está doente.

É a justificativa empírica de `schema.PROXIES_DE_ACESSO` — e a razão de M3 ser a
especificação de **maior performance e menor validade**.

---

## 3. O alvo é ordinal? Dois testes, respostas opostas

`docs/02` previa que a hipótese de odds proporcionais cairia. O caminho até confirmar isso
tem uma lição metodológica que vale registrar.

### 3.1 · Teste por logits cumulativos — **não rejeita** (e é um falso negativo)

Comparando `{0} vs {1,2}` com `{0,1} vs {2}`: maior divergência **8,6%** (`alcool_excessivo`),
todos os IC se sobrepõem. Aparentemente a proporcionalidade se sustenta.

**Não se sustenta — o teste não tem poder.** A classe 1 é apenas **1,6%** da amostra. Mover
1,6% dos casos de um lado para o outro produz dois contrastes quase idênticos *por
construção*. A não-rejeição aqui não é evidência de proporcionalidade; é ausência de
resolução.

### 3.2 · Contraste direto — **rejeita**

Cada classe contra a referência, separadamente (base B ponderada, especificação M3):

| variável | OR pré vs. sem | IC 95% | OR diabetes vs. sem | IC 95% | razão | IC sobrepõe |
|---|---|---|---|---|---|---|
| `exame_colesterol` | 2,09 | [1,31; 3,34] | 3,53 | [2,68; 4,63] | 1,68 | sim |
| `hipertensao` | **1,47** | [1,29; 1,68] | **2,11** | [1,98; 2,24] | 1,43 | **não** |
| `doenca_cardiaca` | **0,92** | [0,76; 1,12] | **1,25** | [1,15; 1,35] | 1,35 | **não** |
| `saude_geral` | **1,34** | [1,24; 1,44] | **1,80** | [1,74; 1,87] | 1,35 | **não** |
| `sexo` | **1,00** | [0,89; 1,14] | **1,26** | [1,19; 1,33] | 1,25 | **não** |
| `imc` | **1,30** | [1,24; 1,37] | **1,53** | [1,49; 1,57] | 1,17 | **não** |
| `escolaridade` | **0,85** | [0,80; 0,90] | **0,97** | [0,94; 0,99] | 1,14 | **não** |
| `idade_faixa` | **1,44** | [1,34; 1,54] | **1,64** | [1,59; 1,70] | 1,14 | **não** |
| `sem_consulta_por_custo` | **1,46** | [1,22; 1,74] | 1,12 | [1,03; 1,22] | 0,77 | sim |
| `saude_mental_dias` | **1,07** | [1,02; 1,13] | **0,95** | [0,93; 0,98] | 0,89 | **não** |
| `alcool_excessivo` | **0,87** | [0,66; 1,15] | **0,52** | [0,45; 0,60] | 0,60 | **não** |

**Nove variáveis com IC que não se sobrepõem** — hipertensão, doença cardíaca, saúde geral,
sexo, IMC, escolaridade, idade, dias de saúde mental e álcool excessivo. Duas delas
**invertem de direção** entre as classes (`doenca_cardiaca`, `saude_mental_dias`).

> ### Decisão: **modelo multinomial, não ordinal.**
> Pré-diabetes e diabetes não são dois pontos de um mesmo continuum latente nesta base.
> `docs/02` (Trilha A2) fica corrigido: a especificação de odds proporcionais é rejeitada,
> e o teste de Brant baseado em cortes cumulativos é inadequado quando uma das classes
> é rara.

### 3.3 · O que o contraste revela sobre a classe 1

Três padrões, e todos apontam para o mesmo mecanismo:

**`sexo` = 1,00 para pré-diabetes, 1,26 para diabetes.** Ser homem não tem *nenhuma*
associação com receber rótulo de pré-diabetes, mas tem com diabetes. Se pré-diabetes fosse
um estágio fisiológico do mesmo processo, o gradiente por sexo apareceria nos dois.

**`doenca_cardiaca` = 0,92 (pré) vs. 1,25 (diabetes).** Quem já teve evento cardíaco tem
*menos* chance de constar como pré-diabético — porque, uma vez investigado, recebe o
diagnóstico completo. A classe 1 é o que sobra de quem foi parcialmente investigado.

**`sem_consulta_por_custo` = 1,46 (pré) vs. 1,12 (diabetes).** Quem deixou de consultar por
custo aparece **46% mais** como pré-diabético. Diagnóstico interrompido no meio do caminho.

Confirma o que `docs/01` §2 levantou como hipótese e `docs/05` §6.3 mediu: **a classe
pré-diabetes é largamente um artefato do processo de detecção**, não um estágio clínico
observado de forma homogênea. Modelá-la como alvo clínico produz um classificador de
trajetória diagnóstica.

---

## 4. Efeitos que sobrevivem a tudo

Robustos às três especificações e às duas bases:

| variável | OR ajustado (B, M1) | leitura |
|---|---|---|
| **`hipertensao`** | **2,39** [2,26; 2,54] | maior fator de risco modificável |
| **`colesterol_alto`** | **2,00** [1,89; 2,11] | componente da síndrome metabólica |
| **`idade_faixa`** | **1,65** /DP [1,60; 1,70] | não modificável, mas domina qualquer escore |
| **`imc`** | **1,59** /DP [1,55; 1,63] | **o alvo de intervenção mais acionável** |
| **`renda_faixa`** | **0,82** /DP [0,80; 0,84] | gradiente socioeconômico persiste após ajuste |

`renda_faixa` merece destaque: **mesmo controlando por IMC, atividade física, dieta,
tabagismo, idade e escolaridade**, cada desvio-padrão de renda a mais reduz em 18% a chance
de diabetes. O gradiente socioeconômico **não** é apenas hábitos de vida.

---

## 5. Consequências para as próximas trilhas

| Trilha | Ajuste |
|---|---|
| **A2** — logística ordinal | **Substituída por multinomial.** Odds proporcionais rejeitada (§3.2) |
| **A3** — M1/M2/M3 | Mantida e produtiva: o deslocamento revela mediação (§2.1) |
| **A4** — causal | Prioridade: `atividade_fisica` → diabetes com `saude_geral` como **mediador**, não confundidor. DAG precisa distingui-los explicitamente |
| **B** — preditiva | M3 é a melhor preditora e a pior explicação. Reportar performance **com e sem** `PROXIES_DE_ACESSO` |
| **B3** — desbalanceamento | Classe 1 com 1,6% e semântica distinta: **modelar as três classes juntas é discutível**. Avaliar `{0}` vs `{2}` excluindo a classe 1, e tratar a classe 1 como problema separado |
| **C** — escore | Candidatas: `hipertensao`, `colesterol_alto`, `idade_faixa`, `imc`, `renda_faixa`. Cinco variáveis, todas em M1, todas robustas |

## 6. Limitações — devem constar do relatório final

1. **Dados transversais.** Nenhum OR aqui é efeito causal. Não há eixo temporal e a
   causalidade reversa é plausível em pelo menos três variáveis (§2.1, §2.2, `docs/06` §2.3).
2. **O rótulo é diagnóstico autorrelatado**, não a doença (`docs/01` §2). ~27,6% dos
   diabéticos não sabem (NHANES).
3. **Inferência ponderada é aproximada.** Usamos `freq_weights` reescalados ao n efetivo de
   Kish.

   > ✅ **VERIFICADO — a aproximação erra para o lado seguro. Ver `docs/11` §A.**
   > Com linearização de Taylor usando `_STSTR` e `_PSU`, o **DEFF real é 2,94**, não os
   > 4,04 de Kish. Nossa aproximação **superestimava a incerteza em ~7%** — os IC deste
   > documento são **conservadores**, não otimistas, e nenhuma conclusão precisa ser revista.
4. **Exclusão par a par** na base B faz o n variar entre estimativas, e a não-resposta
   continua sendo MNAR. Não conserta o viés — deixa de amplificá-lo e torna o n explícito.
5. **Linearidade assumida** nas ordinais padronizadas. A inflexão etária em 80+
   (`docs/06` §3.1) mostra que isso é falso nas pontas. Spline/GAM na Trilha B.
