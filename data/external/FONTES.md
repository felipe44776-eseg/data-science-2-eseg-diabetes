# Fontes externas — proveniência e integridade

Os arquivos de dados não são versionados (ver `.gitignore`). Este documento é o
**manifesto**: quem baixou, de onde, quando, e como provar que o arquivo está íntegro.

## Um comando baixa tudo e prova a integridade

```powershell
.\tasks.ps1 dados                 # baixa o que falta e confere o SHA-256 de cada um
.\tasks.ps1 dados --verificar     # so confere o que ja existe
```

O download vai para um arquivo `.parcial` e **só é renomeado se o hash bater** — conexão
que cai não deixa arquivo truncado com o nome certo. As URLs e os hashes vivem em
`src/diabetes/external/baixar.py`, gerados deste documento.

**2,5 GB no total.** O único insumo que precisa ser copiado à mão é o PDF do enunciado
(`data/raw/Diabetes-2026.csv.pdf`, 105 MB) — ele não tem URL pública, mas **o hash dele
é conferido junto com os outros**.

### O PDF entregue

| | |
|---|---|
| **Tamanho** | 109.110.739 bytes |
| **SHA-256** | `d25054c754de24b8ab74206834f29e6f7ff1ac9088a0ab9f2646b14c36cf8cfd` |
| **Páginas** | 4.374 |
| **Linhas extraídas** | 253.680 · 0 em quarentena |
| **SHA-256 do CSV gerado** | `e2b5c90b37b68f8d8f6c854ab6876114afce0f4f2fa7dbae16f7383599c3ea57` |

A ingestão **compara** o hash da fonte com o do manifesto anterior antes de processar.
Se divergir, ela **para** — porque reprocessar um PDF diferente mudaria todo número
publicado e sobrescreveria o manifesto com o hash novo, sem que nada avisasse. Troca
deliberada exige `--aceitar-fonte-nova` e reprocessamento completo.

O CSV foi reproduzido **três vezes** a partir deste PDF, com hash idêntico nas três.

### Links diretos

| arquivo | bytes | link |
|---|---|---|
| `LLCP2015.XPT` | 1.165.490.800 | [espelho UMT](https://topofire.dbs.umt.edu/public_data/federal_public_datasets/CDC%20Behavioral%20Risk%20Factor%20Surveillance%20System%20/2015%20Annual%20Survey%20Data/Data%20Files/LLCP2015.XPT%20) · [origem CDC](https://www.cdc.gov/brfss/annual_data/annual_2015.html) |
| `LLCP2023.XPT` | 1.205.554.400 | [espelho UMT](https://topofire.dbs.umt.edu/public_data/federal_public_datasets/CDC%20Behavioral%20Risk%20Factor%20Surveillance%20System%20/2023%20Annual%20Survey%20Data/Data%20Files/LLCP2023.XPT%20) · [origem CDC](https://www.cdc.gov/brfss/annual_data/annual_2023.html) |
| `vigitel-2015-peso-rake.zip` | 10.775.599 | https://svs.aids.gov.br/daent/cgdnt/vigitel/vigitel-2015-peso-rake.zip |
| `vigitel-2023-peso-rake.zip` | 15.935.870 | https://svs.aids.gov.br/daent/cgdnt/vigitel/vigitel-2023-peso-rake.zip |
| `dicionario-vigitel-2006-2024.xlsx` | 93.263 | https://svs.aids.gov.br/daent/cgdnt/vigitel/dicionario-vigitel-2006-2024.xlsx |

Os cinco links foram reverificados em 2026-08-21: **HTTP 200** e `content-length` idêntico
ao byte declarado acima.

> O portal do Vigitel publica **todos os anos de 2006 a 2024** no mesmo padrão de URL
> (`vigitel-AAAA-peso-rake.zip`). Os anos intermediários resolveriam a limitação 1 de
> `docs/22` — separar tendência de choque pandêmico —, hoje registrada como não feita.

---

## BRFSS 2015 (CDC) — `brfss2015/LLCP2015.XPT`

| | |
|---|---|
| **Baixado em** | 2026-08-21 |
| **Tamanho** | 1.165.490.800 bytes |
| **SHA-256** | `bfe9e62977cfc5183e51c3e8bdb5193510995cc3c21b225e568f537ad300b1b9` |
| **Formato** | SAS Transport (XPT), descompactado |
| **Conteúdo** | 441.456 registros × 330 colunas |
| **Origem canônica** | https://www.cdc.gov/brfss/annual_data/annual_2015.html |

### Por que um espelho

`www.cdc.gov` responde **HTTP 403** a acesso programático (curl e WebFetch, inclusive com
cabeçalhos de navegador e `Referer`). `ftp.cdc.gov/pub/data/brfss/` e `restoredcdc.org` não
expõem o arquivo de 2015.

URL efetivamente utilizada — espelho institucional da **University of Montana**, que
republica conjuntos federais do CDC na íntegra:

```
https://topofire.dbs.umt.edu/public_data/federal_public_datasets/CDC%20Behavioral%20Risk%20Factor%20Surveillance%20System%20/2015%20Annual%20Survey%20Data/Data%20Files/LLCP2015.XPT%20
```

> Atenção: o nome do arquivo na URL termina em **espaço** (`LLCP2015.XPT%20`) — é assim que
> o CDC o distribui e o espelho preservou. Sem o `%20` a requisição retorna 404.

### Prova de integridade

Espelho não é origem, então a integridade **não foi assumida** — foi verificada por três
vias independentes, todas registradas em `docs/05-comparacao-brfss-original.md`:

| # | Verificação | Resultado |
|---|---|---|
| 1 | Contagem de registros vs. documentação do CDC | 441.456 = **441.456** ✅ |
| 2 | Reconstrução das 22 colunas vs. arquivo entregue pelo professor | **100,000000%** das células idênticas, 253.680/253.680 linhas, mesma ordem ✅ |
| 3 | Prevalência ponderada vs. número publicado pelo CDC | mediana entre 53 jurisdições **10,04%** vs. CDC **10,0%** ✅ |

A verificação 2 é a mais forte: qualquer corrupção, truncamento ou versão diferente do
arquivo tornaria a igualdade exata impossível.

### Variáveis relevantes

- **Usadas na reconstrução (22):** ver tabela em `docs/05-comparacao-brfss-original.md` §3
- **Desenho amostral (descartadas pelo pré-processamento original):** `_LLCPWT` (peso de
  pós-estratificação por raking), `_STSTR` (estrato), `_PSU` (unidade primária), `_STATE`

### Artefatos derivados (também fora do git)

| arquivo | conteúdo |
|---|---|
| `brfss2015/brfss2015_reconstruido.parquet` | 253.680 × 26 — as 22 colunas + desenho amostral |
| `brfss2015/brfss2015_excluidos.parquet` | 187.776 registros excluídos, com o motivo |
| `brfss2015/_cascata_exclusoes.json` | contagem de exclusões por regra — **versionado** |
| `brfss2015/_analise_vies.json` | prevalência e perfil comparados — **versionado** |

Reproduzir: `python -m diabetes.external.brfss2015 --xpt data/external/brfss2015/LLCP2015.XPT`

---

## CDC Open Data — prevalência publicada

| | |
|---|---|
| **Endpoint** | https://data.cdc.gov/resource/dttw-5yxu.json |
| **Dataset** | BRFSS Prevalence Data (2011 to present) |
| **Consultado em** | 2026-08-21 |
| **Uso** | validar a estimativa ponderada contra o número oficial |

```bash
curl -G "https://data.cdc.gov/resource/dttw-5yxu.json" \
  --data-urlencode "\$where=year='2015' and locationabbr='US'" \
  --data-urlencode "\$q=diabetes"
```

Resposta para 2015 / `US` / *Crude Prevalence*: Sim **10,0%** · pré-diabetes 1,3% ·
gestacional 0,8% · Não 87,4%.

> **Detalhe metodológico que importa:** o campo `sample_size` do registro vale **53** —
> são jurisdições, não respondentes. A linha "US" é agregação entre estados (mediana),
> não estimativa nacional *pooled*. Sem isso a comparação parece divergir 0,5 p.p.
> Ao contrário deste endpoint, `www.cdc.gov` **não** bloqueia `data.cdc.gov`.

---

## Vigitel 2015 e 2023 (Ministério da Saúde) — `vigitel/`

| | |
|---|---|
| **Baixado em** | 2026-08-21 |
| **Origem** | https://svs.aids.gov.br/daent/cgdnt/vigitel/ |
| **Acesso** | direto, sem bloqueio |

| arquivo | bytes | SHA-256 (32 primeiros) |
|---|---|---|
| `vigitel-2015-peso-rake.zip` | 10.775.599 | `2e24a11ec1a43d74e4cfe9087ab533f0` |
| `vigitel-2023-peso-rake.zip` | 15.935.870 | `566fc89d38cafbf2451ff41cd7796ebf` |
| `dicionario-vigitel-2006-2024.xlsx` | 93.263 | `c67e63f6f10c2aae7694f3f67b5d2c89` |

Conteúdo extraído: `Vigitel-2015-peso-rake.xls` (**54.174 × 190**, formato OLE2 — exige
`xlrd`) e `Vigitel-2023-peso-rake.xlsx`. Peso de pós-estratificação: **`pesorake`**.

### Prova de integridade

A harmonização reproduz o número publicado do Vigitel 2015:

| | nosso cálculo | publicado |
|---|---|---|
| diabetes, homens | **6,92%** | 6,9% |
| diabetes, mulheres | **7,84%** | 7,8% |

Detalhe em `docs/09-comparacao-binacional.md` §0.

### Variáveis usadas (2015)

| projeto | Vigitel | codificação |
|---|---|---|
| `diabetes` | `q76` (+ `r138` gestacional) | 1 = sim · 2 = não · 777 = não sabe |
| `hipertensao` | `q75` | 1 = sim · 2 = não · 777 |
| `imc` | `q9_i` / (`q11_i`/100)² | peso e altura imputados |
| `fumante` | `q60` ou `q64` | atual ou ex — casa com `SMOKE100` |
| `atividade_fisica` | `q42` | 1 = sim · 2 = não |
| `frutas` | `q27` = 4 | "todos os dias" ≈ `_FRTLT1` |
| `acesso_saude` | `q88` ∈ {1,2} | plano **privado** — ver ressalva abaixo |
| `sexo` | `q7` | 1 = masculino · 2 = feminino |
| `idade_faixa` | `q6` (anos) → faixa BRFSS | |
| `escolaridade` | `fesc` | 1 = 0-8 anos · 2 = 9-11 · 3 = 12+ |

> **`q88` não é comparável a `HLTHPLN1`.** No Brasil mede plano **privado**; a cobertura
> pública pelo SUS é universal e não aparece na variável. Fora do modelo comum, por isso.
>
> **`alcool_excessivo` também não é comparável:** BRFSS mede volume semanal, Vigitel mede
> *binge*. Construtos distintos — a lista completa está em `NAO_COMPARAVEL`,
> em `src/diabetes/external/vigitel.py`.

Reproduzir: `.\tasks.ps1 vigitel`

---

## BRFSS 2023 (CDC) — `brfss2023/LLCP2023.XPT`

| | |
|---|---|
| **Baixado em** | 2026-08-21 |
| **Tamanho** | 1.205.554.400 bytes |
| **SHA-256** | `3d3bf8ef5195bde227828ddc4c90745b76e8b304f8f5b9a043b6d99895fd1615` |
| **Conteúdo** | 421.745 registros × 350 colunas |
| **Origem canônica** | https://www.cdc.gov/brfss/annual_data/annual_2023.html |
| **Baixado de** | mesmo espelho da UMT, pasta `2023 Annual Survey Data/Data Files/LLCP2023.XPT ` |
| **Uso** | validação temporal (`docs/22`) |

### O BRFSS renomeia variáveis entre anos

Não é detalhe: 43 de 47 variáveis mudaram de nome ou sufixo entre 2015 e 2023.

| 2015 | 2023 | | 2015 | 2023 |
|---|---|---|---|---|
| `DIABETE3` | `DIABETE4` | | `INCOME2` | `INCOME3` |
| `_RFHYPE5` | `_RFHYPE6` | | `SEX` | `SEXVAR` |
| `TOLDHI2` | `TOLDHI3` | | `_RFDRHV5` | `_RFDRHV8` |
| `CHCKIDNY` | `CHCKDNY2` | | `ADDEPEV2` | `ADDEPEV3` |

O mapeamento completo está em `EQUIVALENCIAS`, em
`src/diabetes/external/temporal.py`, e o módulo **falha** se não encontrar
equivalente — em vez de treinar com a coluna virando `NaN`.

Sem equivalente em 2023: `USEEQUIP`, `QLACTLM2`, `_FRTLT1`, `_VEGLT1`
(o módulo de frutas e vegetais foi descontinuado).

---

## Pendentes (ver `docs/03-fontes-externas.md`)

| # | Fonte | Uso |
|---|---|---|
| 3 | **NHANES** (CDC/NCHS) | prior de subdiagnóstico para a formulação Positive-Unlabeled |
| 4 | IDF Atlas · NCD-RisC | contexto internacional |
| 5 | PNS 2019 (IBGE) | subdiagnóstico brasileiro (HbA1c) |
| 6 | DATASUS SIH/SIM | custo de internação para a análise de decisão |
