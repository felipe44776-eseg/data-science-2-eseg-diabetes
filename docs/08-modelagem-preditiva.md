> Reproduzir: `.\tasks.ps1 modelos` · saída bruta `data/processed/gold/_escada_modelos.json`

# Modelagem preditiva — a escada, e três previsões minhas que não se confirmaram

**Alvo:** diabetes (classe 2) vs. sem diabetes (classe 0). A classe pré-diabetes foi
**excluída, não ignorada** — `docs/07` §3 mostrou que ela tem mecanismo de detecção próprio
e não é ponto intermediário do mesmo continuum.

**Protocolo, fixado antes de qualquer modelo:** `StratifiedGroupKFold(5)` por hash das
features + holdout de 20% separado por grupo e tocado uma única vez. `class_weight` em vez
de reamostragem (ADR 0004). PR-AUC como métrica principal; **acurácia não é reportada**
(ADR 0005).

---

## 1. A escada (holdout, 20% intocado)

| # | modelo | vars | **PR-AUC** | ganho vs. prevalência | ROC-AUC | recall @ esp. 90% | Brier | ECE |
|---|---|---|---|---|---|---|---|---|
| 0 | prevalência constante | — | 0,1428 | 1,00× | 0,500 | — | 0,1224 | 0,0011 |
| 1 | **regra clínica** (idade, IMC, hipertensão) | 3 | **0,3350** | 2,35× | 0,777 | 0,364 | 0,1081 | 0,0085 |
| 2 | logística L2 | 18 | 0,4139 | 2,90× | 0,825 | 0,460 | 0,1768 | 0,2456 |
| 3 | spline + logística | 18 | 0,4402 | 3,08× | 0,831 | 0,479 | 0,1747 | 0,2417 |
| 4 | gradient boosting | 18 | 0,4494 | 3,15× | 0,835 | 0,493 | 0,1739 | 0,2361 |
| 5 | **GB calibrado (isotônico)** | 18 | **0,4504** | 3,15× | 0,835 | 0,490 | **0,0972** | **0,0035** |
| 5' | GB calibrado + proxies de acesso | 21 | **0,4526** | 3,17× | 0,836 | 0,499 | 0,0970 | 0,0028 |

**Melhor modelo: PR-AUC 0,4526 — 3,17× a prevalência.** Em operação: aceitando 10% de
falso-positivo entre os saudáveis, capturamos **49,9% dos casos**.

O gradient boosting bate a regra clínica de 3 variáveis (0,4526 vs. 0,3350) — o critério
mínimo de `docs/02` B1 está satisfeito, o projeto se sustenta. Mas a margem é menor do que
o esperado, e é o assunto da §3.

---

## 2. Três previsões minhas que os dados não confirmaram

Registro as três porque cada uma estava escrita em documento anterior deste projeto, e
duas mudam o que o leitor deve acreditar.

### 2.1 · O vazamento por duplicata **quase não infla a métrica** ⟵ correção

`docs/01` §1.1 afirmava que a partição aleatória é "a diferença entre medir generalização e
medir memorização". **Medido, é falso para este dataset.**

| modelo | split aleatório | split por grupo | inflação |
|---|---|---|---|
| gradient boosting | 0,4498 | 0,4494 | **+0,09%** |
| árvore sem poda | 0,1999 | 0,1993 | +0,3% |
| árvore prof. 8 | 0,4241 | 0,4227 | +0,3% |
| **kNN k=1** (o memorizador máximo) | 0,1914 | 0,1890 | **+1,2%** |
| kNN k=15 | 0,3524 | 0,3511 | +0,4% |

13,65% do conjunto de teste tem gêmea idêntica no treino — o número de `docs/01` está certo.
Mas a inflação resultante é de **0,1% a 1,2%**, não a distorção grosseira que eu afirmei.

**Por quê:** o ADR 0002 já tinha o argumento certo e eu não segui até o fim. Com 21 features
discretas de baixa cardinalidade, a colisão é **legítima** — duas pessoas diferentes dando as
mesmas 21 respostas. A gêmea no treino não carrega o rótulo da linha de teste; carrega *um*
rótulo sorteado da mesma distribuição conflitante. Memorizá-la devolve a classe majoritária
do grupo, que é o que um bom modelo preveria de qualquer forma.

**O que muda:** a partição por grupo continua sendo o procedimento correto — é gratuita e
é a única defensável por princípio. O que sai é a **afirmação de magnitude**. Nas versões
anteriores de `docs/01`, do `README` e do `CLAUDE.md` isso estava exagerado; corrigido.

### 2.2 · Os proxies de acesso **quase não melhoram a predição** ⟵ correção

`docs/07` §2.3 concluiu que M3 seria "a especificação de maior performance e menor validade".
A parte da validade se sustenta; a da performance não:

| bloco | PR-AUC | diferença |
|---|---|---|
| sem proxies de acesso (18 vars) | 0,4504 | — |
| com proxies de acesso (21 vars) | 0,4526 | **+0,5%** |

`exame_colesterol` tem OR ajustado de **3,45** e ainda assim acrescenta meio por cento.
Não há contradição: no arquivo entregue a variável tem **96,3% de um único valor**
(`docs/05` §6.3). Um OR grande sobre quase nenhuma variância move quase nada.

**Consequência prática, e ela é boa:** a decisão de excluir os proxies de acesso —
justificada por validade — **não custa quase nada em performance**. Os dois objetivos
coincidem. Adotamos o bloco de 18 variáveis como modelo de referência.

### 2.3 · O teto de Bayes **não é a restrição** ⟵ correção de ênfase

`docs/01` §1.2 apresentou os 1.834 grupos com rótulo contraditório como "o argumento mais
forte do trabalho". Medido:

```
grupos de perfis idênticos           227.908
acerto máximo imposto pelo ruído      99,30%
acurácia da classe majoritária        85,72%
ROC-AUC do melhor modelo               0,836
```

O ruído de rótulo limita a acurácia a 99,3%, e o melhor modelo está muito longe disso. **O
teto que aperta não é o ruído — é a informação.** As 21 perguntas simplesmente não contêm o
suficiente para separar melhor. Nenhum algoritmo resolve isso; só variável nova resolve
(HbA1c, glicemia, histórico familiar, circunferência abdominal).

O cálculo continua útil, mas como **descarte de uma hipótese**, não como o achado central.

---

## 3. A calibração — aqui o ADR 0004 se confirma com folga

| modelo | Brier | **ECE** |
|---|---|---|
| logística com `class_weight="balanced"` | 0,1768 | **0,2456** |
| GB com `class_weight="balanced"` | 0,1739 | **0,2361** |
| **GB + calibração isotônica** | **0,0972** | **0,0035** |

**O erro de calibração cai 67×.** Um modelo com `class_weight` diz "40%" onde a prevalência
real é 14% — ordena bem (ROC-AUC idêntico, 0,835) mas a probabilidade não significa nada.

Isso é a demonstração empírica do ADR 0004: **reponderar destrói a calibração**. Como a
Trilha C (net benefit, número necessário para rastrear, escore de pontos) depende de
probabilidade confiável, a calibração deixa de ser refinamento e vira requisito.

O mesmo argumento condena o SMOTE pelo mesmo motivo, com o agravante de gerar registros
impossíveis (`fumante = 0,63`) num espaço com 19 variáveis binárias ou ordinais.

**Padrão do projeto:** ordenar com `class_weight`, calibrar depois em fold separado,
decidir por limiar sobre a probabilidade calibrada.

---

## 4. Curva de parcimônia — a resposta da Trilha C

Seleção gulosa para frente, com regressão logística (o candidato a escore precisa ser
linear para virar pontos inteiros no papel). Referência = 0,4526, o melhor modelo.

| vars | variável acrescentada | PR-AUC | **% do melhor modelo** |
|---|---|---|---|
| 1 | `saude_geral` | 0,2706 | 59,8% |
| 2 | `imc` | 0,3362 | 74,3% |
| 3 | `hipertensao` | 0,3780 | **83,5%** |
| 4 | `colesterol_alto` | 0,3984 | 88,0% |
| 5 | `idade_faixa` | 0,4039 | **89,2%** |
| 6 | `alcool_excessivo` | 0,4073 | 90,0% |
| 7 | `sexo` | 0,4095 | 90,5% |
| 8 | `doenca_cardiaca` | 0,4110 | 90,8% |

**Cinco perguntas entregam 89,2% do modelo de 21 variáveis.** Da sexta em diante o ganho é
de décimos.

> **A pergunta de `docs/02` C3 está respondida: o entregável correto é o escore.**
> Cinco perguntas — saúde autoavaliada, IMC, hipertensão, colesterol alto e faixa etária —
> aplicáveis em papel numa unidade básica de saúde, sem computador, entregando quase nove
> décimos do que um gradient boosting de 21 variáveis entrega.

Duas ressalvas honestas sobre esse conjunto:

1. **`saude_geral` é a primeira escolhida e é a mais problemática.** Como preditor operacional
   é legítima (é uma pergunta que se faz). Como fator, não: `docs/07` §2.1 mostrou que ela
   absorve o efeito da atividade física, e quem já sabe do diagnóstico tende a avaliar a
   própria saúde pior. O escore prediz bem; não explica.
2. **`alcool_excessivo` aparece em 6º com OR protetor.** É a causalidade reversa de
   `docs/06` §2.3 entrando no modelo. Preditivamente funciona; num escore para uso clínico
   ela deve sair, porque a leitura "beba mais" é inaceitável.

**Escore recomendado: as 5 primeiras, com `alcool_excessivo` deliberadamente fora.**

---

## 5. Onde o modelo está, em termos operacionais

| limiar | especificidade | recall | leitura |
|---|---|---|---|
| esp. 90% | 90% | **49,9%** | testando 10% dos saudáveis, acho metade dos casos |
| esp. 95% | 95% | ~35% | testando 5%, acho um terço |

Um ROC-AUC de 0,836 com PR-AUC 0,45 é **compatível com a literatura** de escores de risco
de diabetes baseados em questionário (FINDRISC, ADA Risk Test operam nessa faixa). Não é um
resultado ruim: é o teto do que um questionário sem exame de sangue consegue.

## 6. O que fica para a Trilha C

| # | Item | Insumo pronto |
|---|---|---|
| 1 | Curva de decisão (net benefit) | probabilidade calibrada, ECE 0,0035 |
| 2 | Número necessário para rastrear por decil | idem |
| 3 | Escore de pontos inteiros | 5 variáveis da §4 |
| 4 | Comparação com FINDRISC e ADA Risk Test | escore da §4 como concorrente |
| 5 | Auditoria de viés (`fairlearn`) | modelo de 18 variáveis + `ATRIBUTOS_SENSIVEIS` |

## 7. Limitações

1. **O alvo é diagnóstico autorrelatado**, não a doença. O modelo prediz quem *consta* como
   diabético (`docs/01` §2).
2. **Sem tuning de hiperparâmetros.** Os valores do gradient boosting são razoáveis, não
   otimizados. Optuna daria talvez 1–2% — irrelevante frente ao teto de informação da §2.3.
3. **A classe pré-diabetes ficou de fora.** É um problema separado e provavelmente um
   classificador de acesso ao sistema, não de fisiologia (`docs/07` §3.3).
4. **Sem validação temporal.** O teste duro é BRFSS 2021/2023 (`docs/03` §1.2), não feito.
5. **Modelo treinado no arquivo entregue**, que é enviesado para pessoas com acesso à saúde
   (`docs/05` §6.3). Reportado assim de propósito — é o que o enunciado pede —, mas o
   modelo populacional deveria ser treinado na base reconstruída e ponderada.
