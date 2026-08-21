# Fontes externas — proveniência e integridade

Os arquivos de dados não são versionados (ver `.gitignore`). Este documento é o
**manifesto**: quem baixou, de onde, quando, e como provar que o arquivo está íntegro.

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

## Pendentes (ver `docs/03-fontes-externas.md`)

| # | Fonte | Uso |
|---|---|---|
| 2 | **Vigitel** (Ministério da Saúde) — microdados 2006–2024 | comparação binacional de odds ratio |
| 3 | **NHANES** (CDC/NCHS) | prior de subdiagnóstico para a formulação Positive-Unlabeled |
| 4 | IDF Atlas · NCD-RisC | contexto internacional |
| 5 | PNS 2019 (IBGE) | subdiagnóstico brasileiro (HbA1c) |
| 6 | DATASUS SIH/SIM | custo de internação para a análise de decisão |
