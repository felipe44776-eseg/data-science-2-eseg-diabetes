# Linha do tempo — como o trabalho foi construído

> Para apresentar. Cada fase traz o que entrou, a **decisão que ficou travada**
> ali, e o que a fase descobriu. Reconstruída do histórico do git — os commits
> são verificáveis.

O projeto foi feito em **15 commits**. A ordem importa: quase toda decisão de
arquitetura foi tomada por causa de um número medido na fase anterior, não por
preferência.

---

## Visão em uma tela

| # | fase | commit | entrega | o que travou |
|---|---|---|---|---|
| 0 | Repositório | `18542e2` | — | — |
| 1 | **Fundação** | `bfd99b7` | ingestão, limpeza, proposta | `schema.py` como fonte única · ADR 0001–0005 |
| 2 | **Prova do viés** | `a97f9e4` | BRFSS original reconstruído | o problema deixa de ser "predizer diabetes" |
| 3 | **Análise** | `a48d1cc` | EDA + explicativa, base dupla | toda prevalência sai em par |
| 4 | **Modelos** | `e9aa860` | escada, figuras, binacional, `status` | acurácia banida · calibração é requisito |
| 5 | **Expansões** | `452f527` | 5 frentes simultâneas | rótulo corrigido por PU |
| 6 | **Decisão** | `66590ab` | escore, DCA, equidade | escore sem marcador de acesso |
| 7 | **Produto** | `0ef1b3b` | calculadora offline | paridade Py↔JS verificada no build |
| 8 | **Grupo** | `75f5027`+`f88e58d` | 6 notebooks + deck | notebook não contém lógica |
| 9 | **Brasil e pré** | `ba466b6`+`0bdaa43` | Vigitel recalibrado, pré-diabetes | recalibrar, não retreinar |
| 10 | **Fechamento** | `0635b9f` | MCA, causal, temporal | o padrão dos 4 contextos |
| 11 | **Publicação** | *este* | site, docs/24, docs/25 | link público + bibliografia |

---

## Fase 1 · Fundação — `bfd99b7`

**37 arquivos, 2.060 linhas.** Ingestão, limpeza, proposta de análise e as cinco
ADRs.

O primeiro obstáculo não foi analítico: **os dados vieram como PDF de 4.374
páginas**. A ordem de leitura de um PDF não é garantida pela especificação, então
a extração ingênua embaralha colunas. A solução foi reconstruir cada linha pela
**coordenada da caixa delimitadora** de cada palavra.

**Decisões travadas aqui:**

| decisão | por quê |
|---|---|
| `schema.py` é a única fonte de verdade | nenhum literal de nome de coluna solto no código |
| Nenhuma linha some em silêncio | quarentena com motivo, contagem no relatório |
| Dado não é versionado; manifesto com hash é | reprodutibilidade sem repositório de 1 GB |
| Partição por hash das features (ADR 0002) | 23.899 duplicatas exatas na base |

**Descoberta:** 253.680 linhas, **0 em quarentena**, 0 fora de domínio. O arquivo
era limpo demais — e essa foi a primeira pista.

---

## Fase 2 · A prova do viés — `a97f9e4`

**A fase que mudou o trabalho.** Baixamos o BRFSS 2015 original (XPT, 1,17 GB,
441.456 respostas) e reconstruímos as 22 colunas do arquivo entregue.

**Resultado:** identidade **100,000000%**, célula a célula. Com a reconstrução
provada, dava para medir o que a "limpeza" original tinha feito:

| medida | valor |
|---|---|
| pessoas removidas | 187.776 |
| superestimação de prevalência | **+3,26 p.p.** |
| quanto disso vem de descartar as colunas de peso | **73%** |
| exame de colesterol: arquivo vs. população | 96,3% vs. **77,9%** |

> A partir daqui a pergunta deixou de ser *"que fatores predizem diabetes?"* e
> passou a ser *"o que este arquivo deixou de fora, e o que isso faz com toda
> conclusão que eu tirar dele?"*

---

## Fase 3 · Análise em base dupla — `a48d1cc`

**3.233 linhas.** EDA bivariada e análise explicativa, sempre nas duas bases —
arquivo entregue e BRFSS ponderado.

Com *n* = 253.680, p-valor não distingue nada. A regra que ficou: **tamanho de
efeito com intervalo, nunca teste de significância** (V de Cramér, δ de Cliff,
OR ajustado).

**Descoberta:** pré-diabetes não é ponto intermediário do mesmo contínuo — nove
variáveis divergem e duas invertem de direção. Consequência: modelo multinomial,
não ordinal.

---

## Fase 4 · Escada de modelos e observabilidade — `e9aa860`

**3.890 linhas.** Escada de 6 degraus (prevalência → regra clínica → logística →
… → GB calibrado), 6 figuras SVG, comparação Brasil × EUA e a camada de
observabilidade `tasks.ps1 status`.

**Três previsões nossas caíram aqui**, e foram corrigidas na fonte:

| dissemos | medimos |
|---|---|
| o vazamento por duplicata infla muito a métrica | **+0,09% a +1,2%** |
| os proxies de acesso inflariam a performance | **+0,5%** |
| o teto de Bayes é a restrição | limita a 99,3%; o modelo está em 0,836 |

**O achado que virou tema:** calibrar não muda a ROC-AUC em nada e melhora o ECE
em **67×**. Primeira aparição do padrão "a ordem transfere, o nível não".

E a comparação binacional: hipertensão dá OR **3,136** no Brasil contra **3,146**
nos EUA. Terceira casa decimal, países diferentes.

---

## Fase 5 · Cinco expansões — `452f527`

**5.218 linhas, o maior commit do projeto.** Cinco frentes independentes:

1. **Variáveis expandidas** (21 → 69, recuperadas do XPT) — +6,62% de PR-AUC,
   com o ganho **inteiramente das minorias**: brancos −0,45 p.p. de recall,
   negros +10,6, hispânicos +10,8.
2. **Positive-Unlabeled** — BBE estima c = **0,7283**; o NHANES, com exame de
   sangue, implica **0,7240**. Prevalência real: **14,29%**.
3. **Glass-box** — EBM com restrições de monotonicidade e predição conforme.
4. **Medicaid como experimento natural** — DiD, e a honestidade de reportar que
   **o desenho não tem poder** (MDE 0,90 p.p. contra efeito esperado de 0,16).
5. **Pesos publicáveis** — raking que corrige 95,6% do viés do CSV do Kaggle.
   E aqui o DEFF real (2,94, por linearização de Taylor) refutou a aproximação
   de Kish (4,04) que vínhamos usando.

---

## Fase 6 · Da predição à decisão — `66590ab`

**3.389 linhas.** Escore de papel, curva de decisão e auditoria de equidade.

**A decisão de desenho mais importante do projeto:** o escore A, que usa exame de
colesterol, tem ROC 0,8082. O escore B, sem nenhum marcador de acesso, tem 0,8040.
Escolhemos o B. Custo: **4,2 milésimos**.

O motivo não é estatístico. Um instrumento de rastreamento que pergunta "você já
fez exame?" funciona melhor no papel e pior na vida — porque exclui exatamente
quem nunca foi rastreado.

**E o escore B bate o FINDRISC** (0,7663), padrão internacional desde 2003, em
**+37,7 milésimos** na mesma amostra.

**Erro encontrado e corrigido nesta fase:** os escores A e B estavam sendo
comparados em amostras diferentes — A exigia colesterol não nulo, ou seja, já
vinha filtrado por acesso. **Era exatamente o viés que o projeto combate,
reproduzido dentro da própria avaliação.** Corrigido para uma amostra comum de
62.294.

---

## Fase 7 · O produto — `0ef1b3b`

**Calculadora de 59 KB que roda offline no navegador.** Como o EBM é aditivo,
exportamos as tabelas de consulta e reimplementamos a predição em JavaScript.

**A garantia:** 500 casos comparados, erro máximo **1,110 × 10⁻¹⁶**.

**Dois bugs desta fase entraram nos testes permanentes:**

1. `R.prevalencia_eua_diagnosticada_%` — `%` não é identificador válido em JS. A
   página **abria, parecia certa e não calculava nada**. Correção: notação de
   colchetes + `node --check` no build.
2. `-Infinity` no JSON do modelo — `JSON.parse` rejeita. Pior: a verificação de
   paridade em Python **passava**, porque nunca serializava para texto. Correção:
   `allow_nan=False` e paridade que **atravessa o JSON como texto**.

---

## Fase 8 · Para o grupo — `75f5027` e `f88e58d`

Seis notebooks executados com saídas, README estruturado, deck de 19 slides.

Invariante: **notebook mostra resultado, não contém lógica** — importa de `src/`.
Lógica em notebook não é testável nem reutilizável.

---

## Fase 9 · Brasil e pré-diabetes — `ba466b6` e `0bdaa43`

**Escore recalibrado no Vigitel.** Aplicado cru no Brasil, o escore ordena bem
(ROC 0,802) e **superestima o risco em 54%**. Recalibrado: erro de calibração cai
de 3,48 p.p. para 0,86 — **75% eliminados** com um deslocamento de intercepto.

**Quase perdemos a variável mais forte:** tínhamos registrado que o Vigitel não
tinha saúde autoavaliada. Tem — é a `q74`. Corrigido, e a correção virou o
sexto item da lista de previsões refutadas.

**Pré-diabetes.** `docs/07` dizia "largamente artefato de detecção". Medido, o
exagero era nosso: risco prediz 0,771 contra acesso 0,644.

Mas o contraste mais limpo do projeto apareceu aqui — no decil superior de risco,
com modelo **sem nenhuma variável de acesso**: quem foi testado tem **53,4%** de
diagnóstico; quem não foi, **39,9%**. Mesmo risco, **13,5 pontos** de diferença.

---

## Fase 10 · Fechamento — `0635b9f`

Três frentes de uma vez.

**Não supervisionada.** MCA (não PCA — os dados são categóricos) revela que o
eixo 1 não é diabetes: é **morbidade acumulada**. Cinco fenótipos com gradiente de
**17×**, sem o algoritmo jamais ter visto o rótulo. E o FP-Growth reconstruiu a
síndrome metabólica sozinho.
**Refutação:** o Isolation Forest **não** acha os casos ocultos — lift 0,81, as
listas se evitam. Alto risco de diabetes é comum, não atípico.

**Camada causal.** A mesma pergunta dá OR 0,51 / **0,75** / 0,86 / 0,98 conforme o
ajuste. O DAG diz qual é qual — e prova que M2/M3 de `docs/07` sofrem viés de
colisor. Três refutações passam, mas o **E-value é 2,02**, com um confundidor
plausível à vista.

**Validação temporal.** O modelo de 2015 aplicado ao BRFSS 2023 perde **11,8
milésimos** e fica a **2 milésimos** de um treinado nativamente em 2023.
*Concept drift* praticamente ausente. E a pandemia aparece: dias ruins de saúde
mental **+32%**.

**Foi aqui que o padrão fechou** — quatro transposições independentes, uma
assinatura só (`docs/23`).

---

## Fase 11 · Publicação — este commit

O que faltava para o trabalho ser **entregável**, não só correto:

| entrega | por quê |
|---|---|
| **Site público** no GitHub Pages | sem link, ninguém testa o questionário |
| **Deck de 26 slides** | o de 19 parava na fase 8 — faltavam 5 frentes |
| **`docs/24`** — fundamentação teórica | as citações estavam soltas, sem bibliografia |
| **`docs/25`** — esta linha do tempo | para apresentar o percurso, não só o resultado |
| **Docstrings completas** | 52% das funções públicas estavam sem |

---

## O que a linha do tempo mostra

**Nove vezes o dado contradisse o que tínhamos escrito** — e as nove correções
estão na fonte, não em errata. A lista completa está em `docs/23`.

Isso não é acidente de processo: é consequência de duas regras adotadas na fase 1.
Todo número tem um comando que o reproduz, e `tasks.ps1 status` marca como
**OBSOLETO** qualquer artefato mais velho que sua entrada. Sem essas duas, uma
previsão errada sobrevive até a apresentação.

> A fase 2 é o ponto de virada. Antes dela, o trabalho era sobre diabetes.
> Depois, passou a ser sobre **o que os dados de saúde deixam de fora** — e todas
> as fases seguintes são consequência dessa medição.
