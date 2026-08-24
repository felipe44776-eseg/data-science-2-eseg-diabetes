# Síntese final — o que este trabalho descobriu

> Mapa de leitura. Detalhe em `docs/01` a `docs/22`.

O enunciado pedia: *"analisar o arquivo e apresentar suas conclusões"*. O arquivo
era um PDF de 4.374 páginas. O que se descobriu ao abri-lo mudou a pergunta.

---

## A tese em uma frase

**Os dados de saúde não medem quem tem diabetes. Medem quem foi diagnosticado —
e quem é diagnosticado depende de ter acesso ao sistema de saúde.**

Tudo o mais é consequência disso, e cada consequência foi medida.

---

## As dez descobertas

| # | Descoberta | Número | Onde |
|---|---|---|---|
| 1 | A reconstrução do PDF bate **célula a célula** com o BRFSS original | **100,000000%** | `docs/05` |
| 2 | O arquivo entregue **superestima a prevalência em um terço** — e 73% disso vem de terem descartado três colunas de peso, não 187.776 pessoas | +3,26 p.p. | `docs/05` |
| 3 | **O arquivo é uma amostra de quem tem acesso**: 96,3% fizeram exame de colesterol contra 77,9% da população | +18,3 p.p. | `docs/05` §6.3 |
| 4 | **Pré-diabetes não é o mesmo continuum** — nove variáveis divergem, duas invertem de direção | ROC 0,669 para separar | `docs/07` · `docs/19` |
| 5 | **Brasil × EUA: seis de oito fatores convergem.** Hipertensão coincide na 3ª decimal | 3,136 vs 3,146 | `docs/09` |
| 6 | **Nenhum perfil de questionário isola um grupo em que todos têm diabetes** — o teto de informação, medido por uma segunda via | `c` não identificável | `docs/12` |
| 7 | **O ganho de variáveis novas é inteiramente das minorias** | −0,45 pp vs +10,6 a +13,4 pp | `docs/10` |
| 8 | **Mesmo risco fisiológico, 13,5 pontos menos diagnóstico** para quem não foi testado | 53,4% vs 39,9% | `docs/19` |
| 9 | **Cinco perguntas batem o FINDRISC** (5 dos 8 itens dele) | +36,9 milésimos | `docs/16` |
| 10 | **O modelo de 2015 perde 11,8 milésimos em oito anos** e fica a 2 milésimos de um treinado em 2023 | sem concept drift | `docs/22` |

---

## O padrão que se repete em quatro contextos

Quando o mundo muda, **a ordem transfere e o nível não**.

| transposição | discriminação | calibração |
|---|---|---|
| arquivo entregue → população (`docs/11`) | robusta | erro de +3,26 p.p. |
| EUA → Brasil (`docs/18`) | ROC 0,804 → 0,802 | superestima **54%** |
| 2015 → 2023 (`docs/22`) | −11,8 milésimos | ECE 4× pior |
| `class_weight` → calibrado (`docs/08`) | ROC idêntico | ECE **67×** pior |

**E recalibrar é sempre barato:** 20% de dados novos, um deslocamento de
intercepto. Nunca foi preciso retreinar.

> Se este trabalho tem uma lição metodológica única, é essa: **AUC é a métrica
> que quase todo mundo reporta e é a que menos se quebra.** O que quebra é a
> calibração, e quase ninguém a mede.

---

## Doze previsões nossas que os dados não confirmaram

Cada uma estava escrita em documento anterior e foi **corrigida na fonte**.

| # | O que dissemos | O que medimos | Onde |
|---|---|---|---|
| 1 | O vazamento por duplicata infla muito a métrica | **+0,09% a +1,2%** | `docs/08` §2.1 |
| 2 | Os proxies de acesso inflariam a performance | **+0,5%** | `docs/08` §2.2 |
| 3 | O teto de Bayes é a restrição | Limita a 99,3%; o modelo está em 0,836 | `docs/08` §2.3 |
| 4 | Há curva em J no IMC | Não há, após ajuste | `docs/13` §2 |
| 5 | DEFF é 4,04 (Kish) | **2,94** — nossos IC eram conservadores | `docs/11` §A |
| 6 | Oito variáveis divergem entre pré e diabetes | **Nove** | `docs/16` |
| 7 | Pré-diabetes é "largamente artefato de detecção" | Risco prediz melhor que acesso (0,771 vs 0,644) | `docs/19` |
| 8 | Isolation Forest acharia os casos ocultos | **Lift 0,81** — as listas se evitam | `docs/20` §4 |
| 9 | Saúde autoavaliada não existe no Vigitel | Existe (`q74`) — quase custou a variável mais forte do escore brasileiro | `docs/18` |
| 10 | O BBE **valida** a premissa de `c` do NHANES | Não valida: o estimador não identifica `c`, e a concordância era artefato de hiperparâmetro | `docs/12` |
| 11 | O IPF do raking **converge**; o resíduo vem do aparo | Não convergia — 17% da amostra sem alvo. E o aparo é aplicado depois do laço, logo nunca poderia explicar | `docs/11` |
| 12 | O resíduo de viés era **inteiramente** acesso | 32,9% dele era um bug de codificação de renda | `docs/11` |

> As três últimas vieram de uma **auditoria adversarial** (20 agentes, 7 camadas,
> cada achado submetido a um cético). Ela confirmou 8 achados e derrubou 4 — e o
> mais importante é que 100 verificações independentes **passaram**, incluindo a
> reconstrução do PDF, a partição sem vazamento e a paridade Python↔JavaScript.

**E três hipóteses testadas e rejeitadas com medição**, em vez de assumidas:
imputação e mediação como explicação do IMC brasileiro (`docs/18` §6), e células
conjuntas ausentes como explicação do resíduo de raking (`docs/11` §B).

---

## O que se entrega

| entregável | onde |
|---|---|
| **Calculadora de risco** — 59 KB, offline, paridade Python↔JS de 1,1×10⁻¹⁶ | `reports/produto/index.html` |
| **Apresentação** — 19 slides, exporta em PDF | `reports/deck/apresentacao.html` |
| **Escore de papel** — 5 perguntas, aplicável sem computador | `docs/16` |
| **Escore brasileiro** — recalibrado no Vigitel | `docs/18` |
| **Pesos publicáveis** — corrigem 93,4% do viés do CSV do Kaggle | `docs/11` |
| **6 notebooks** executados, com saídas | `notebooks/` |
| **25 documentos + 5 ADRs** | `docs/` |
| **Pipeline de 24 etapas** com detector de obsolescência | `.\tasks.ps1 status` |
| **Site público** — calculadora, deck e figuras com link | [felipe44776-eseg.github.io/data-science-2-eseg-diabetes](https://felipe44776-eseg.github.io/data-science-2-eseg-diabetes/) |

---

## Como ler, por perfil

**Professor / avaliador** → o deck (26 slides), depois `docs/23` (este),
`docs/16` (o valor agregado) e `docs/24` (de onde vem cada método).

**Quem quiser só testar** → a [calculadora](https://felipe44776-eseg.github.io/data-science-2-eseg-diabetes/calculadora/),
no navegador, sem instalar nada.

**Colega do grupo** → `README.md` → notebooks 01 a 06, na ordem.

**Quem for continuar** → `docs/15` (síntese das expansões) e a seção "Limitações"
de cada documento — é onde estão as próximas perguntas.

**Quem duvidar de um número** → todo número tem um comando que o reproduz, no
cabeçalho do documento correspondente.

**Quem quiser a base teórica** → `docs/24` (método por método, com bibliografia)
e `docs/25` (como o trabalho foi construído, fase a fase).

---

## O que ficou de fora, e por quê

| não feito | por quê |
|---|---|
| **NHANES individual com HbA1c** | validaria o PU caso a caso e separaria fisiologia de subdiagnóstico no Brasil (`docs/18` §6). É a próxima fonte da fila |
| **PNS 2019 com HbA1c** | mediria o subdiagnóstico brasileiro |
| **Determinantes sociais medidos** | é o teste falseável do papel de raça (`docs/10` §4b) |
| **Modelo de Markov de custo-efetividade** | converteria casos encontrados em QALY; os insumos estão prontos |
| **Anos intermediários do BRFSS** | separaria tendência de choque pandêmico (`docs/22` §7) |
| **Recalibrar o produto para 2023** | o mais barato e de maior retorno: um deslocamento de intercepto na tabela já exportada |

---

## A conclusão que fecha o trabalho

Começamos procurando fatores de risco de diabetes. Encontramos todos os
esperados — hipertensão, idade, IMC, renda — e eles se replicam entre países com
precisão de terceira casa decimal.

Mas o achado que sobrevive à revisão não é sobre diabetes.

**É sobre o que os dados de saúde deixam de fora.** O arquivo que recebemos, ao
ser "limpo", removeu preferencialmente quem nunca fez um exame. O rótulo que
modelamos mede diagnóstico, não doença. E as pessoas clinicamente idênticas aos
diabéticos, mas sem acesso ao sistema, ficam registradas como saudáveis.

Um instrumento de rastreamento que exige exame prévio **exclui exatamente quem
mais precisa dele**. Foi por isso que o escore final tem cinco perguntas, e
nenhuma delas exige ter visto um médico.
