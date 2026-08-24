# Síntese das cinco expansões

> Detalhe de cada uma em `docs/10` a `docs/14`. Este documento é o mapa: por que
> cada frente foi escolhida, em que ordem, e o que mudou no projeto.

---

## Como a ordem foi decidida

Não por sofisticação de método. `docs/08` §2.3 tinha estabelecido que **o teto do
modelo é a informação disponível, não o algoritmo** — a escada inteira de modelos
rendeu +0,036 de PR-AUC, e um teste exploratório com variáveis extras rendeu
+0,049. A ordem seguiu **retorno medido por esforço**:

| ordem | frente | por que aqui |
|---|---|---|
| 1º | Variáveis expandidas | único ganho já medido antes de começar |
| 2º | Pesos e inferência | fundacional — corrige todo IC do projeto |
| 3º | Positive-Unlabeled | muda a pergunta; depende da base expandida |
| 4º | EBM e conforme | fecha o entregável clínico; depende das duas anteriores |
| 5º | Medicaid DiD | maior originalidade, maior risco, independente das demais |

---

## O que cada frente entregou

| # | Frente | Resultado principal | Doc |
|---|---|---|---|
| 1 | **Variáveis expandidas** | +6,62% PR-AUC — e **o ganho é inteiramente das minorias** (+10 a 13 pp de recall, contra −0,45 pp dos brancos) | `docs/10` |
| 2 | **Positive-Unlabeled** | O BBE **nao identifica** `c` (espalhamento 0,118 na grade) — nao ha regiao pura de positivos no questionario. `c` fica como premissa exogena do NHANES, com faixa de sensibilidade | `docs/12` |
| 3 | **EBM + conforme** | EBM com **12 variáveis atinge 94,4%** do boosting com 60; monotonicidade custa 0,44% | `docs/13` |
| 4 | **Medicaid DiD** | Efeito causal sobre acesso medido (+3,11 pp de cobertura); **o desenho não tem poder** para o diagnóstico, e isso está provado | `docs/14` |
| 5 | **Pesos e inferência** | Raking remove **93,4%** do viés do arquivo entregue; DEFF real é 2,94, não 4,04 | `docs/11` |

---

## Os sete insights que valem mais que os números

### 1. Um ganho médio pode esconder uma redistribuição (Frente 1)

+6,6% de PR-AUC parece incremental. Desagregado por raça: brancos **−0,45 pp** de
recall, negros **+10,6**, hispânicos **+10,8**, multirraciais **+13,4**.

O modelo de 21 variáveis era sistematicamente pior para minorias — e **ninguém
podia saber, porque a variável que revela isso tinha sido removida da base**.

### 2. O efeito de equidade vem de raça, não das comorbidades (Frente 1)

Testado diretamente: sem raça como preditor, o ganho é pequeno e **uniforme**,
preservando a lacuna. Com raça, redistribui. O projeto toma posição explícita —
raça como *proxy de determinantes sociais*, nunca biológica — e reporta as duas
versões. Excluir raça não é neutro: é escolher manter a lacuna de 10 pontos.

### 3. Duas fontes independentes concordam sobre o subdiagnóstico (Frente 2)

> **Retratado (auditoria).** Este parágrafo dizia que o BBE (0,7283) e o NHANES
> (0,7240) concordavam na terceira casa decimal, e chamava isso de "a validação
> mais forte de todo o projeto". A concordância era artefato de um hiperparâmetro
> não declarado — ver `docs/12` Passo 1. Corrigido o estimador, ele **se recusa a
> estimar**: a fração no topo vai de 0,622 a 0,740 conforme a resolução do grid.
>
> O resultado honesto é outro, e ainda é resultado: **nenhum perfil construível a
> partir das 60 perguntas identifica um subgrupo em que todos têm diabetes.** É o
> teto de informação do questionário, medido por uma segunda via. `c` permanece
> premissa exógena do NHANES, com a faixa de sensibilidade sempre reportada.

### 4. Dois vieses opostos quase se cancelam — e isso não é um acerto (Frente 2)

```
13,93%   arquivo entregue, sem peso        (seleção, para cima)
10,67%   BRFSS ponderado, diagnóstico
14,29%   prevalência VERDADEIRA estimada   (subdiagnóstico, para baixo)
```

Quem usasse o arquivo cru chegaria a 13,93% — numericamente próximo dos 14,29%
corretos, **pelo motivo errado**, por dois vieses de sinal oposto e magnitude
parecida. É o exemplo mais didático do projeto.

### 5. Clinicamente iguais, invisíveis para o sistema (Frente 2)

Os prováveis positivos ocultos têm hipertensão em **74,7%** contra **74,9%** dos
diagnosticados, IMC 32,3 contra 31,7 — e **28,6% de check-up no ano contra 88,1%**,
o dobro de renúncia a consulta por custo, renda menor e mais minorias.

### 6. Auditabilidade é quase de graça (Frente 3)

Restrições de monotonicidade custam **0,44%** de PR-AUC. O EBM com 12 variáveis
entrega **94,4%** do boosting com 60 — e desenha a função de forma. Ele
**redescobriu sozinho** a queda de risco em 80+ que `docs/06` tinha medido.

E mostrou onde *não* impor monotonicidade: na idade, justamente porque a
inflexão é real. Restrição precisa de evidência, não de intuição.

### 7. "Não detectamos" não é "não existe" — e dá para provar qual é (Frente 4)

O DiD não achou efeito sobre diagnóstico. Antes de interpretar, calculamos o
poder: efeito máximo plausível **0,16 p.p.**, diferença mínima detectável
**0,90 p.p.** — razão de **5,7×**. O desenho não podia detectar o efeito esperado.

Sem esse cálculo, o nulo seria lido como "acesso não causa diagnóstico" — conclusão
oposta à evidência do projeto, obtida por falta de poder.

---

## O que mudou nos documentos anteriores

Nenhuma dessas correções foi cosmética.

| documento | correção | fonte |
|---|---|---|
| `docs/06` §4 | **Não há curva em J no IMC** após ajuste — era artefato do arquivo entregue | `docs/13` §2 |
| `docs/07` §6.3 · `CLAUDE.md` | **DEFF é 2,94, não 4,04.** Kish superestimava a incerteza em 7% — nossos IC eram conservadores, não otimistas | `docs/11` §A |
| `docs/08` §2.2 | Proxies de acesso continuam com pouca contribuição preditiva (+2,98%), agora medido na base expandida | `docs/10` §2 |
| `docs/08` Trilha B | O modelo de referência prediz **diagnóstico**; a versão PU prediz **doença** e é a correta para rastreamento | `docs/12` |
| `docs/05` e `docs/12` | O viés de acesso é enorme **na composição**; o efeito de mudança *marginal* de acesso sobre diagnóstico agregado é **pequeno**. Compatíveis, e a distinção importa | `docs/14` |

---

## Números operacionais consolidados

Para a Trilha C, tudo já está medido:

| pergunta | resposta | fonte |
|---|---|---|
| Melhor PR-AUC alcançável | 0,4874 (69 vars) · 0,4733 (só risco) | `docs/10` |
| Modelo auditável | EBM, 12 vars, PR-AUC 0,4460, ECE 0,0026 | `docs/13` |
| Testar 25% da população acha… | **70%** dos casos, NNS 2,7 | `docs/13` §4 |
| Testar 45% acha… | **90%** dos casos, NNS 3,8 | `docs/13` §4 |
| Prevalência verdadeira (com ocultos) | **14,29%** contra 10,67% diagnosticada | `docs/12` |
| Peso para o CSV do Kaggle | remove **93,4%** do viés | `docs/11` |
| Bloco de variáveis que mais importa | comorbidades (−9,2% ao remover) | `docs/10` |
| Bloco irrelevante | **tabagismo (−0,04%)** — fora do escore | `docs/10` |

---

## O que ficou de fora, e por quê

| não feito | motivo |
|---|---|
| NHANES com HbA1c individual | validaria o PU caso a caso; é a próxima fonte da fila |
| Microdados BRFSS 2011–2019 para o DiD | ~7 GB; ganho de precisão insuficiente para vencer o problema de poder |
| Determinantes sociais medidos diretamente | é o teste falseável do papel de raça (`docs/10` §4b) — exige fonte que não temos |
| Validação temporal 2015 → 2023 | quebraria a permutabilidade que o conforme exige; precisa de método próprio |
| Modelo de Markov de custo-efetividade | Trilha C; os insumos (probabilidade calibrada, NNS) já estão prontos |

## Reprodução

```powershell
.\tasks.ps1 status       # o que rodou, o que está obsoleto, o que falta
.\tasks.ps1 expandido    # Frente 1
.\tasks.ps1 pesos        # Frente 5
.\tasks.ps1 pu           # Frente 2
.\tasks.ps1 glassbox     # Frente 3
.\tasks.ps1 medicaid     # Frente 4  (não precisa do XPT local)
.\tasks.ps1 all          # tudo, do PDF ao relatório
```
