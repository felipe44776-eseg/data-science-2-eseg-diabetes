# Fontes externas de comparação

O arquivo entregue é um **derivado empobrecido** de uma pesquisa pública. Trazer as fontes
originais não é enfeite: é o que permite (a) medir o viés introduzido pelo pré-processamento,
(b) corrigir a prevalência com peso amostral, (c) estimar o subdiagnóstico e
(d) ancorar as conclusões na realidade brasileira, não na americana.

Todas as fontes abaixo são **públicas e gratuitas**. Nenhuma exige cadastro pago.

---

## Camada 1 — A fonte original (a mais importante)

### 1.1 · BRFSS 2015 (CDC) — de onde o arquivo veio

| | |
|---|---|
| Formato | SAS XPT, ZIP ≈ 96,5 MB, publicado ago/2016 |
| URL | https://www.cdc.gov/brfss/annual_data/annual_2015.html |
| Leitura | `pandas.read_sas(..., format="xport")` |

**O achado que muda o trabalho:**

| Base | Respondentes |
|---|---|
| BRFSS 2015 original | **441.456** |
| Arquivo que recebemos | **253.680** |
| **Descartados no pré-processamento** | **187.776 — 42,5%** |

Quem construiu o CSV do Kaggle jogou fora **quase metade da amostra** (linhas com qualquer
`refused`/`don't know`) e, junto, as variáveis de desenho amostral:

- `_LLCPWT` — peso final de pós-estratificação (raking)
- `_STSTR` — estrato
- `_PSU` — unidade primária de amostragem

**Consequência direta:** BRFSS é uma **amostra complexa**, não aleatória simples.
Sem peso, **toda prevalência calculada no arquivo entregue é enviesada** e todo intervalo
de confiança é otimista (ignora o *design effect*, tipicamente 1,5–2,5).

**Análise proposta — e é o diferencial mais defensável do projeto:**

1. Baixar o BRFSS 2015 original.
2. Reconstruir as 22 colunas com as mesmas regras (`schema.PTBR_TO_BRFSS` já mapeia os nomes).
3. Calcular a prevalência de diabetes de quatro formas e tabelar lado a lado:

   | # | Estimativa | Valor |
   |---|---|---|
   | a | Nosso arquivo, sem peso | **13,933%** |
   | b | BRFSS completo, sem peso | **12,993%** |
   | c | BRFSS completo, **com `_LLCPWT`** | **10,500%** |
   | d | CDC oficial publicado (mediana entre 53 jurisdições) | **10,0%** — reproduzido em **10,04%** |

4. O gap (a) → (c) é o **viés que 42,5% de descarte + ausência de peso introduz**.

> ✅ **EXECUTADO.** Resultado completo em **`docs/05-comparacao-brfss-original.md`**.
> Viés total **+3,43 p.p. (superestimação de 32,7%)**, dos quais **73% vêm do peso
> descartado**, não do descarte de linhas. Efeito de desenho **DEFF = 4,04** → todo IC
> calculado no arquivo entregue é **metade** do correto. E o achado mais grave: o arquivo
> tem **96,3%** de pessoas que fizeram exame de colesterol contra **77,9%** na população —
> é uma amostra de quem tem acesso ao sistema de saúde.

Ferramenta: `samplics` ou `statsmodels` com `freq_weights`; para variância correta,
`survey`-style via `samplics` (Taylor linearization).

### 1.2 · BRFSS 2021 / 2023 — validação temporal

https://www.cdc.gov/brfss/annual_data/annual_2023.html

Reconstruir as mesmas variáveis em anos posteriores e testar:
**o modelo treinado em 2015 ainda funciona em 2023?** É validação temporal externa —
o teste mais duro de generalização, e o mais próximo de uso real (*drift*).

---

## Camada 2 — Medir o que o autorrelato esconde

### 2.1 · NHANES (CDC/NCHS) — laboratório, não questionário

https://wwwn.cdc.gov/nchs/nhanes/ · https://www.cdc.gov/nchs/products/databriefs/db516.htm

O NHANES mede **HbA1c e glicemia de jejum em laboratório**, além de perguntar o diagnóstico.
É a única fonte que permite quantificar o subdiagnóstico:

| Indicador (NHANES ago/2021–ago/2023, NCHS Data Brief 516) | Valor |
|---|---|
| Prevalência de diabetes **não diagnosticado** em adultos EUA | **4,5%** (H 4,9% · M 3,5%) |
| Proporção dos diabéticos que **não sabem** que têm | **27,6%** (≈ 11,0 milhões) |
| Critério laboratorial | glicemia jejum ≥ 126 mg/dL **ou** HbA1c ≥ 6,5% em quem nunca recebeu diagnóstico |

**Uso analítico direto — este número não é decorativo:**

- É o **prior de positivos ocultos** para a formulação **Positive-Unlabeled** (Trilha B5).
  Sabemos que ~27,6% dos verdadeiros positivos estão rotulados como `0` na nossa base.
- Permite **corrigir a matriz de confusão** para o subdiagnóstico e reportar a performance
  *"corrigida por verificação"* além da performance bruta.
- Fecha o cruzamento com o Isolation Forest (Trilha D): perfis de altíssimo risco rotulados
  como `0` são candidatos plausíveis a subdiagnóstico, e agora temos a taxa esperada.

---

## Camada 3 — Ancoragem no Brasil (o que dá relevância local ao trabalho)

O dataset é dos EUA, de 2015. Um trabalho que só descreve os EUA de 2015 tem valor limitado.
As duas fontes abaixo são de **desenho comparável** e permitem transposição honesta.

### 3.1 · VIGITEL (Ministério da Saúde) — o BRFSS brasileiro

https://www.gov.br/saude/pt-br/composicao/svsa/inqueritos-de-saude/vigitel
Microdados 2006–2024 + dicionários e notas técnicas na página "Banco de dados Vigitel".

**Comparabilidade metodológica é quase direta:** inquérito telefônico, adultos ≥18 anos,
autorrelato de diagnóstico médico, com peso de pós-estratificação. É o análogo desenhado
do BRFSS.

| Vigitel 2023 | Prevalência de diabetes |
|---|---|
| Brasil (capitais) | **10,1%** |
| Mulheres | 11,1% |
| Homens | 9,0% |
| Maiores: São Paulo e Distrito Federal | 12,1% |
| Menor: Rio Branco | 5,6% |

**Análise proposta:** replicar a modelagem no Vigitel com as variáveis equivalentes
(IMC, atividade física, frutas/hortaliças, tabagismo, hipertensão, escolaridade, idade)
e comparar **direção e magnitude dos odds ratios**. Fatores que se mantêm nos dois países
são robustos; fatores que invertem revelam o efeito do sistema de saúde (SUS universal
vs. cobertura privada nos EUA). **Este é o achado com maior valor original do trabalho.**

Detalhe importante: `acesso_saude` (cobertura) e `sem_consulta_por_custo` são variáveis
com significado radicalmente diferente sob o SUS. Isso torna a comparação binacional
um teste natural do efeito de acesso sobre o diagnóstico.

### 3.2 · PNS 2019 (IBGE) — presencial, com subamostra laboratorial

https://www.ibge.gov.br/estatisticas/sociais/saude/9160-pesquisa-nacional-de-saude.html

| PNS 2019 | Valor |
|---|---|
| Diabetes autorreferido (adultos) | **7,7%** (era 6,2% em 2013) |
| Amostra analítica | 82.349 adultos · 94.114 domicílios coletados |
| Diferencial | subamostra com **HbA1c coletada em laboratório** |

Papel no projeto: é o **NHANES brasileiro** — permite estimar a taxa de subdiagnóstico
*no Brasil* e verificar se o 27,6% americano transfere.

Observe a escada: **13,9% (BRFSS não ponderado) → 10,1% (Vigitel) → 7,7% (PNS)**.
Explicar essa escada — quanto é diferença real de prevalência, quanto é peso amostral,
quanto é desenho (telefônico vs. domiciliar), quanto é acesso ao diagnóstico — **é uma
análise inteira e é exatamente o que o enunciado chama de "informação que agrega valor"**.

### 3.3 · DATASUS — desfecho, não questionário

- **SIH-SUS** — internações por diabetes (CID E10–E14) e complicações
- **SIM** — mortalidade com diabetes como causa básica/associada
- Acesso: `pysus`, TabNet, ou FTP `ftp.datasus.gov.br`

Uso: converter risco previsto em **desfecho e custo**. Alimenta o NNS e o net benefit
da Trilha C com valores de internação reais do SUS, em reais.

---

## Camada 4 — Benchmarks e instrumentos publicados

| Fonte | Uso |
|---|---|
| **IDF Diabetes Atlas** (idf.org/diabetesatlas) | prevalência por país — sanidade externa das nossas estimativas |
| **NCD-RisC** (ncdrisc.org) | séries históricas de IMC e diabetes; dados em CSV aberto |
| **WHO Global Health Observatory** | API REST; indicadores comparáveis internacionalmente |
| **FINDRISC** (Lindström & Tuomilehto, 2003) | escore de referência a ser reimplementado e batido (Trilha C4) |
| **ADA Diabetes Risk Test** | escore americano de 7 itens — comparação direta |
| **Pima Indians Diabetes** (UCI) | 768 registros com variáveis bioquímicas; teste de transferência entre domínios |

---

## Prioridade de execução

Ordem por relação valor/esforço. As três primeiras já sustentam o trabalho.

| # | Fonte | Esforço | Por que primeiro |
|---|---|---|---|
| 1 | **BRFSS 2015 original** | ✅ **feito** | quantificou o viés do arquivo entregue — ver `docs/05` |
| 2 | **Vigitel 2023** | médio | dá relevância brasileira; comparação binacional de OR |
| 3 | **NHANES / NCHS 516** | baixo | um número (27,6%) destrava toda a formulação PU |
| 4 | IDF Atlas / NCD-RisC | baixo | sanidade e contexto para os gráficos |
| 5 | PNS 2019 | alto | subdiagnóstico brasileiro medido, se houver fôlego |
| 6 | DATASUS SIH/SIM | alto | custo em reais para a análise de decisão |

---

## Fontes

- [CDC — 2015 BRFSS Survey Data and Documentation](https://www.cdc.gov/brfss/annual_data/annual_2015.html)
- [CDC — 2023 BRFSS Survey Data and Documentation](https://www.cdc.gov/brfss/annual_data/annual_2023.html)
- [NCHS Data Brief 516 — Prevalence of Total, Diagnosed, and Undiagnosed Diabetes in Adults: United States, August 2021–August 2023](https://www.cdc.gov/nchs/products/databriefs/db516.htm)
- [CDC — National Diabetes Statistics Report](https://www.cdc.gov/diabetes/php/data-research/index.html)
- [Ministério da Saúde — Vigitel](https://www.gov.br/saude/pt-br/composicao/svsa/inqueritos-de-saude/vigitel)
- [Vigitel Brasil 2023 (PDF)](https://bvsms.saude.gov.br/bvs/publicacoes/vigitel_brasil_2023.pdf)
- [Diabetes autorreferido e fatores associados na população adulta brasileira: PNS 2019 (SciELO)](https://www.scielo.br/j/csc/a/FC39MrV7mL43ZNgTDjjtfgB/?lang=en)
- [Prevalência de diabetes mellitus determinada pela hemoglobina glicada, PNS (SciELO)](http://www.scielo.br/j/rbepid/a/qQttB6XwmqzJYgcZKfpMV7L/?lang=pt)
