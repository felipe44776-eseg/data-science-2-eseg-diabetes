# Proposta de análise — as três perguntas e como respondemos cada uma

O enunciado pede: *"identificar informações relevantes que possam agregar algo de valor
e predizer ocorrências"*. São **dois objetivos distintos** — explicar e predizer — e
tratá-los com o mesmo modelo é o erro mais comum neste tipo de trabalho.
A proposta separa três trilhas, cada uma com sua pergunta, seu modelo e sua métrica.

| Trilha | Pergunta | Modelo | Métrica de sucesso |
|---|---|---|---|
| **A — Explicar** | Quais fatores estão associados a diabetes, e com que magnitude? | Logística ordinal / GLM com IC | Odds ratio + intervalo de confiança |
| **B — Predizer** | Dado o questionário, qual o risco desta pessoa? | Gradient boosting + calibração | PR-AUC, Brier, curva de calibração |
| **C — Decidir** | Vale rastrear? Quem primeiro? Com que custo? | Escore de pontos + análise de decisão | Net benefit, NNS |

A trilha C é o entregável que responde ao *"agregar algo de valor"*. As trilhas A e B
existem para sustentá-la.

---

## Trilha A — Análise explicativa

### A1. Análise exploratória com rigor estatístico

> ✅ **EXECUTADA em base dupla — `docs/06-analise-exploratoria.md`.**

Não "gráfico bonito". Cada afirmação com teste e tamanho de efeito.

| Cruzamento | Técnica | Tamanho de efeito |
|---|---|---|
| Alvo × cada binária | Qui-quadrado | **V de Cramér** + risco relativo + OR bruto |
| Alvo × ordinais (idade, renda, escolaridade, saúde geral) | Cochran-Armitage (tendência) | Gradiente da prevalência por nível |
| Alvo × IMC | Kruskal-Wallis + Dunn | **δ de Cliff** |
| Entre features | Matriz de associação mista | V de Cramér (cat×cat), η² (cat×num) |

> **Regra do projeto:** com n = 253.680, *tudo* dá p < 0,001. **P-valor é ruído nesta escala.**
> Relatamos tamanho de efeito e intervalo de confiança; p-valor entra só como nota de rodapé.
> Este é o ponto que distingue análise madura de saída de biblioteca.

### A2. Regressão logística ordinal (odds proporcionais)

O alvo é **ordinal**: 0 < 1 < 2 (sem → pré → diabetes). Praticamente toda análise pública
deste dataset ou (a) binariza juntando 1 e 2, ou (b) trata como multiclasse nominal.
Ambas jogam fora informação.

- Modelo de **odds proporcionais** (`statsmodels` / `mord`).
- **Teste da hipótese de odds proporcionais.** Se falhar, usamos **logística multinomial**
  e documentamos *por quê*. A rejeição é um achado, não um problema.

- Saída: **odds ratio ajustado com IC 95%** para as 21 variáveis. É isto que responde
  "quais informações são relevantes" de forma defensável.

> ⚠️ **EXECUTADO — hipótese REJEITADA. Ver `docs/07-analise-explicativa.md` §3.**
> Nove variáveis têm efeito materialmente diferente em pré-diabetes e em diabetes, e duas
> **invertem de direção**. **A especificação adotada é a multinomial.**
>
> Lição metodológica que vale registrar: o teste por *logits cumulativos* (`{0}` vs `{1,2}`
> contra `{0,1}` vs `{2}`) **não rejeitou** — divergência máxima de 8,6%. É falso negativo:
> com a classe 1 valendo 1,6% da amostra, os dois contrastes são quase idênticos por
> construção e o teste não tem poder. Só o contraste direto (cada classe contra a
> referência) resolve. **Teste de Brant por cortes cumulativos é inadequado quando uma
> classe é rara.**

### A3. Três especificações, reportadas lado a lado

> ✅ **EXECUTADA — `docs/07-analise-explicativa.md` §2.** O deslocamento revelou mediação:
> o efeito protetor da atividade física (OR 0,85) **desaparece** (OR 0,99) ao entrar
> `saude_geral`. M2/M3 não podem ser lidos como "atividade física não importa".

| Modelo | Variáveis | Lê-se como |
|---|---|---|
| **M1 — risco puro** | exclui `PROXIES_DE_ACESSO` e `POSSIVEIS_CONSEQUENCIAS` | fatores de risco antecedentes |
| **M2 — clínico** | M1 + saúde geral, dificuldade de caminhar, dias ruins | quadro clínico completo |
| **M3 — completo** | todas as 21 | máxima predição, mínima interpretabilidade |

A instabilidade dos coeficientes entre M1/M2/M3 **é** o resultado: mostra quanto do
"efeito" atribuído a um fator na verdade passa por acesso ou por consequência.

### A4. Camada causal — o diferencial (com ressalva honesta)

Dados transversais **não estabelecem causalidade**. O que se pode fazer com honestidade:

1. **DAG explícito** (`dowhy`) declarando as suposições — o que é confundidor, o que é
   mediador, o que é colisor. Publicar o DAG é mais valioso que qualquer número.
2. **Estimativa de efeito ajustado** de `atividade_fisica` sobre diabetes, com backdoor
   adjustment, e **efeito heterogêneo** por faixa de renda/idade via `econml` (Causal Forest).
3. **Testes de refutação** (`dowhy.refute`): confundidor aleatório, subconjunto aleatório,
   placebo. Se o efeito sobrevive, é robusto *dentro das suposições do DAG* — e só isso.
4. **Análise de sensibilidade E-value**: quão forte teria de ser um confundidor não medido
   para anular o efeito? Número interpretável e citável.

**A ressalva vai no relatório em negrito:** com dados transversais e rótulo autorrelatado,
o resultado é *"efeito sob as suposições do DAG"*, nunca *"causa"*. Apresentar o inverso
seria o erro mais grave possível neste trabalho.

---

## Trilha B — Análise preditiva

### B1. Protocolo de validação (decidido antes de qualquer modelo)

Esta seção é o que impede o resultado de ser fantasia.

```
particao  : StratifiedGroupKFold(5), grupo = hash das 21 features
            -> impede que duplicata exata caia em treino e teste (§1.1 do diagnóstico)
holdout   : 20% separado ANTES de tudo, tocado uma única vez, no fim
tuning    : Optuna, dentro do treino, com CV aninhada
seed      : fixa e registrada; todo run vai para MLflow
baseline  : (a) prevalência constante  (b) regra clínica de 3 variáveis
            (idade, IMC, hipertensão) — se o GBM não bater isso, não há projeto
```

### B2. Escada de modelos — do simples ao caro, cada degrau justificado

| # | Modelo | Por quê |
|---|---|---|
| 0 | Prevalência constante | piso absoluto |
| 1 | Regra clínica 3 variáveis | piso *útil* — o que um médico faria sem ML |
| 2 | Logística regularizada (L1/L2/Elastic Net) | baseline linear interpretável |
| 3 | GAM / spline em IMC e idade | captura não-linearidade sem perder leitura |
| 4 | **LightGBM / XGBoost** com `scale_pos_weight` | esperado como melhor; captura interação |
| 5 | CatBoost (nativo em ordinal/categórico) | comparação — trata ordinal sem one-hot |
| 6 | Ensemble empilhado (logística como meta-modelo) | só se o ganho superar o teto de Bayes estimado |
| — | ~~Rede neural~~ | **descartada com justificativa**: 21 features tabulares de baixa cardinalidade; a literatura (Grinsztajn et al., 2022) mostra que árvores dominam este regime. Descartar com argumento vale mais que testar por reflexo. |

### B3. Desbalanceamento — a decisão que a maioria erra

| Abordagem | Veredito |
|---|---|
| **Cost-sensitive** (`class_weight`, `scale_pos_weight`) | ✅ **padrão do projeto** |
| Ajuste de limiar sobre probabilidade calibrada | ✅ **preferido** — decisão separada do modelo |
| SMOTE / ADASYN | ⚠️ testado, esperado **pior** |
| Undersampling da classe 0 | ⚠️ só como ablação |

**Argumento contra SMOTE, e ele é técnico:** 19 das 21 features são binárias ou ordinais
de baixa cardinalidade. SMOTE interpola em espaço contínuo e gera **registros impossíveis**
(`fumante = 0,63`). Além disso, oversampling **destrói a calibração** — a probabilidade
prevista deixa de corresponder à prevalência real, o que inviabiliza a Trilha C.
Se você precisa de probabilidade confiável, não pode usar SMOTE. Fazemos a ablação para
demonstrar isso com número, não para adotá-lo.

### B4. Métricas — acurácia é banida

| Métrica | Papel |
|---|---|
| **PR-AUC** (por classe, one-vs-rest) | principal — robusta a 84/2/14 |
| **Recall @ especificidade fixa (90%)** | leitura operacional: quantos casos capturo pagando X falsos-positivos |
| **Brier score + curva de calibração** | a probabilidade é confiável? Pré-requisito da Trilha C |
| **Log-loss** | otimização |
| ROC-AUC | reportado só para comparabilidade com a literatura |
| ~~Acurácia~~ | **não reportada** — 84,2% é o resultado de responder sempre "0" |

**Calibração é obrigatória** (Platt / isotônica, ajustada em fold separado). Um modelo que
ordena bem mas diz "40%" quando a prevalência é 14% é inútil para decisão clínica.

### B5. Formulações do alvo — comparadas, não escolhidas por conveniência

1. **Binária** `{0} vs {1,2}` — rastreamento amplo
2. **Binária** `{0,1} vs {2}` — diagnóstico estabelecido
3. **Multiclasse nominal** (3 classes)
4. **Ordinal** (odds proporcionais) — a formulação correta *a priori*
5. **Positive-Unlabeled** — trata a classe 0 como não-rotulada e estima o prior de positivos
   ocultos a partir do NHANES. **Diferencial de maior peso do projeto**; é a única
   formulação que enfrenta o subdiagnóstico de frente.

### B6. Interpretabilidade

- **SHAP** (TreeExplainer) — importância global e local; *beeswarm* e *dependence plot*.
- **Confronto SHAP × odds ratio da Trilha A.** Se divergirem, há interação ou confundimento —
  e investigar essa divergência é análise de verdade.
- **PDP / ALE** para IMC e idade (ALE por causa da correlação entre features).
- **Contrafactuais** (`dice-ml`): *"o que mudaria o prognóstico desta pessoa?"* — mas
  restritos a variáveis **acionáveis** (IMC, atividade física, dieta). Contrafactual sobre
  idade ou sexo é ruído; sobre atividade física é recomendação.

### B7. Auditoria de viés — não opcional

`fairlearn` sobre `sexo`, `renda_faixa`, `escolaridade`, `idade_faixa`:
equalized odds, paridade demográfica, **recall por subgrupo**.

**A hipótese que testamos:** o recall será menor nas faixas de renda baixa, porque essas
pessoas são menos diagnosticadas — o rótulo é pior lá. Se um serviço de saúde priorizar
rastreamento pelo modelo, **ele reproduz e amplifica a desigualdade de acesso existente**.
Documentar isso com número é um resultado de primeira ordem, não um apêndice.

---

## Trilha C — Do modelo à decisão (o "valor agregado")

### C1. Análise de curva de decisão (Vickers & Elkin)

**Net benefit** em função do limiar de probabilidade, comparando: modelo, "rastrear todos",
"rastrear ninguém", regra clínica. Responde a pergunta que AUC não responde:
**existe alguma faixa de limiar em que usar o modelo é melhor que não usar?**

### C2. Número necessário para rastrear (NNS)

Quantas pessoas precisam ser testadas por caso encontrado, em cada decil de risco.
Com custo unitário de teste (HbA1c ≈ R$ 25–40 na tabela SUS/AMB), converte o modelo
em **orçamento**. É a linguagem de quem decide.

### C3. Escore de pontos simplificado — o entregável final

Regressão logística com coeficientes discretizados em pontos inteiros, no formato
**FINDRISC / ADA Risk Test** (o padrão internacional). 6 a 8 variáveis, aplicável em papel.

> **A pergunta que fecha o trabalho:** se o escore de 7 variáveis atinge ~95% da PR-AUC
> do LightGBM de 21 variáveis, **o entregável correto é o escore** — porque roda numa
> unidade básica de saúde sem computador. Se atingir 60%, o entregável é o modelo.
> A resposta é empírica e o trabalho a mede.

### C4. Validação contra instrumentos existentes

Reimplementar **FINDRISC** e **ADA Diabetes Risk Test** com as variáveis disponíveis
(aproximação documentada) e comparar performance. Se nosso escore não bate um instrumento
publicado em 2003, isso é o resultado — e é um resultado honesto e informativo.

---

## Trilha D — Não supervisionada (apoio)

| Técnica | Uso |
|---|---|
| **k-prototypes** / **UMAP + HDBSCAN** | fenótipos de risco (dados mistos — k-means é inadequado) |
| **MCA** (análise de correspondência múltipla) | redução para variáveis categóricas — o análogo correto de PCA aqui |
| **Regras de associação** (FP-Growth) | padrões de comorbidade: `{hipertensão, colesterol, IMC≥30} → diabetes`, com lift |
| **Isolation Forest** | perfis atípicos — quem tem risco alto e não tem diagnóstico (candidatos a subdiagnóstico, cruza com a Trilha B5/PU) |

**PCA em dados binários é errado** e aparece em quase todo notebook deste dataset.
MCA é o método correto. Vale registrar essa escolha explicitamente.
