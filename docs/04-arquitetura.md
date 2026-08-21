# Arquitetura

## Recomendação, primeiro

**Local-first, arquitetura medallion sobre Parquet + DuckDB. Sem nuvem.**

A base limpa ocupa **8,6 MB em memória** (253.680 × 31, tudo `uint8`). Cabe no cache L3 de
um notebook. Subir isso para BigQuery seria engenharia decorativa: acrescenta latência,
custo, um tenant a gerenciar e uma dependência de rede para reproduzir o trabalho — sem
resolver problema nenhum que exista aqui.

O caminho GCP está desenhado no §5, com o **gatilho objetivo** que o justificaria.
Enquanto o gatilho não disparar, ele fica no papel.

---

## 1. Camadas de dado (medallion)

```
data/
├── raw/        BRONZE — imutável, nunca editado
│   ├── Diabetes-2026.csv.pdf          fonte do professor (109 MB, fora do git)
│   ├── diabetes_2026_raw.csv          reconstruído · sha256 e2b5c90b…c3ea57
│   └── _manifest_ingestao.json        hash, contagens, quarentena  ← VERSIONADO
│
├── external/   BRONZE externo — fontes de comparação
│   ├── brfss2015/     LLCP2015.XPT (CDC)
│   ├── vigitel/       microdados MS
│   ├── nhanes/        HbA1c + glicemia
│   └── FONTES.md      URL, data de download, hash de cada arquivo  ← VERSIONADO
│
├── interim/    quarentena e intermediários descartáveis
│   └── quarentena.parquet             linhas rejeitadas, com o motivo
│
└── processed/  SILVER + GOLD
    ├── diabetes_silver.parquet        253.680 × 31 · validado · flags de qualidade
    ├── _relatorio_limpeza.json        toda regra com contagem  ← VERSIONADO
    └── gold/
        ├── features.parquet           matriz de modelagem
        ├── folds.parquet              partição por grupo, congelada
        └── agregados_*.parquet        tabelas do relatório
```

**Invariante do projeto:** *o dado não é versionado; o **manifesto** é.*
Git guarda hash, contagem e regra. Qualquer pessoa reproduz `raw/` a partir do PDF
rodando um comando, e confere o hash. Isso é reprodutibilidade sem LFS e sem
repositório de 100 MB.

### Por que Parquet + zstd, não CSV

| | CSV | Parquet+zstd |
|---|---|---|
| Tamanho | 10,3 MB | ~0,6 MB |
| Tipos | perdidos a cada leitura | preservados (`uint8`, categórico) |
| Leitura de 3 colunas | lê o arquivo inteiro | lê só as 3 (colunar) |
| Consulta SQL direta | não | `duckdb.sql("… FROM 'x.parquet'")` |

### Por que DuckDB e não pandas puro

Não substitui o pandas — **complementa**. Agregação, janela e `GROUP BY` em SQL sobre
Parquet, sem carregar nada em memória, sem servidor, sem instalação. Uma linha:

```python
duckdb.sql("""
  SELECT idade_faixa, renda_faixa,
         avg(diabetes = 2) AS prev_diabetes, count(*) AS n
  FROM 'data/processed/diabetes_silver.parquet'
  GROUP BY 1, 2 ORDER BY 1, 2
""").df()
```

A tabela de prevalência cruzada do relatório sai daí, legível e auditável — em vez de
uma cadeia de `groupby().agg().unstack()` que ninguém revisa.

---

## 2. Camadas de código

```
src/diabetes/
├── schema.py         ★ CONTRATO ÚNICO — domínios, tipos, semântica, blocos de variáveis
│                       Tudo importa daqui. Nenhum nome de coluna literal fora deste arquivo.
├── ingest/
│   └── pdf_to_csv.py   PDF → CSV por coordenada de bounding box + manifesto  ✅ pronto
├── clean/
│   └── pipeline.py     CSV → Parquet validado, 7 regras rastreadas            ✅ pronto
├── features/           derivações, blocos M1/M2/M3, codificação ordinal
├── eda/                testes com tamanho de efeito, tabelas de associação
├── models/             escada de modelos, calibração, tuning
├── eval/               métricas, curva de decisão, NNS, fairness
├── causal/             DAG, backdoor, refutação, E-value
├── external/           carregadores BRFSS/Vigitel/NHANES + harmonização
└── viz/                figuras com estilo único
```

**A regra que sustenta tudo:** `schema.py` é a única fonte de verdade. Nome de coluna,
domínio válido, o que é proxy de acesso, o que é possível consequência, o que é sensível
para auditoria de viés — tudo declarado uma vez. Notebook que escreve `df["IMC"]` na mão
está errado por construção.

### Notebooks são vitrine, não motor

```
notebooks/
├── 01-ingestao-e-qualidade.ipynb
├── 02-eda-univariada.ipynb
├── 03-eda-bivariada-e-associacao.ipynb
├── 04-comparacao-fontes-externas.ipynb
├── 05-modelagem-explicativa.ipynb
├── 06-modelagem-preditiva.ipynb
├── 07-interpretabilidade-e-vies.ipynb
├── 08-causalidade.ipynb
└── 09-decisao-e-escore.ipynb
```

Notebook **importa de `src/` e mostra resultado**. Lógica dentro de notebook não é testável,
não é reutilizável e não sobrevive à revisão. É a regra que separa este projeto de um
`.ipynb` de 900 células.

---

## 3. Orquestração

```powershell
.\tasks.ps1 ingest     # PDF   -> CSV bronze + manifesto
.\tasks.ps1 clean      # CSV   -> Parquet silver + relatório de qualidade
.\tasks.ps1 features   # silver-> gold
.\tasks.ps1 train      # escada de modelos -> MLflow
.\tasks.ps1 report     # figuras + tabelas -> reports/
.\tasks.ps1 all        # tudo, do PDF ao relatório
.\tasks.ps1 test       # pytest + ruff
```

Um comando reconstrói o projeto inteiro a partir do PDF original. Se `all` não roda limpo
numa máquina nova, o projeto está quebrado — e isso é verificável em CI.

**Rastreabilidade de experimento:** MLflow local (`file:./mlruns`). Cada run grava
hiperparâmetro, métrica, seed, hash do dado de entrada e versão do `schema.py`.
Sem isso, "meu melhor modelo deu 0,82" não é afirmação verificável.

---

## 4. Qualidade e CI

| Camada | Ferramenta | Bloqueia? |
|---|---|---|
| Contrato de schema | `pandera` sobre `schema.ESQUEMA` | ✅ sim |
| Testes unitários | `pytest` — regras de limpeza, derivadas, particionamento | ✅ sim |
| **Teste de vazamento** | assert: nenhum grupo de duplicata cruza treino/teste | ✅ **sim** |
| Lint / formato | `ruff` | ✅ sim |
| Determinismo | rodar `ingest` duas vezes → mesmo sha256 | ✅ sim |
| Perfilamento | `ydata-profiling` → HTML | ℹ️ artefato |

GitHub Actions em `.github/workflows/ci.yml`. O **teste de vazamento** é o mais importante
da lista: é o erro que o dataset convida a cometer (§1.1 do diagnóstico), e um `assert`
em CI garante que ele não volte numa refatoração.

---

## 5. Caminho GCP — desenhado, não construído

**Gatilho objetivo para migrar:** qualquer uma das condições abaixo.

1. Ingestão do BRFSS 2015 **completo de vários anos** (441k linhas × N anos × ~330 colunas
   → dezenas de GB). Aí o Parquet local deixa de ser confortável.
2. Necessidade de re-treino agendado ou serving do escore como API.
3. Terceiros precisando consultar os resultados sem clonar o repositório.

**Arquitetura, se disparar** (região `southamerica-east1`):

```
GCS  gs://<proj>-diabetes-raw/       PDF, XPT do CDC, microdados Vigitel
      │  (bucket com versionamento; lifecycle -> Nearline em 90d)
      ▼
Cloud Run Job  ingest      PyMuPDF / read_sas  ->  Parquet em gs://…-silver/
      ▼
BigQuery  ds_diabetes      external tables sobre o Parquet (bronze/silver)
                           tabelas materializadas (gold) + BQML para baseline
      ▼
Cloud Run Job  train       LightGBM  ->  modelo no GCS + métricas no MLflow
      ▼
Vertex AI Model Registry   versionamento e (se houver) endpoint do escore
      ▲
Cloud Scheduler ──► Workflows ──► encadeia ingest → clean → train
Secret Manager             credenciais de fontes externas, se houver
```

| Componente | Custo mensal estimado neste volume | Ponto de falha |
|---|---|---|
| GCS (< 1 GB) | ~R$ 0,20 | — |
| BigQuery (< 10 GB, on-demand) | dentro do free tier de 1 TB de query | query sem partição varre tudo |
| Cloud Run Job (poucos min/mês) | ~R$ 0 (free tier) | cold start irrelevante em job |
| Vertex Endpoint | **~R$ 150+/mês, sempre ligado** | ⚠️ único item caro — só com uso real |

**Recomendação explícita:** não fazer agora. Custo marginal ≈ zero de benefício.
Se for feito, tenant **ESEG** (`felipe_44776@aluno.eseg.edu.br`, config gcloud `eseg`,
projeto `treino-llm` ou um novo `eseg-diabetes`) — **nunca** sob conta de cliente.

---

## 6. Decisões registradas (ADR)

| # | Decisão | Arquivo |
|---|---|---|
| 0001 | Extrair o PDF por coordenada, não por ordem de leitura | `adr/0001-ingestao-por-coordenada.md` |
| 0002 | Marcar duplicatas em vez de remover; decisão fica na modelagem | `adr/0002-duplicatas.md` |
| 0003 | Local-first; GCP só com gatilho declarado | `adr/0003-local-first.md` |
| 0004 | Cost-sensitive em vez de SMOTE | `adr/0004-desbalanceamento.md` |
| 0005 | Banir acurácia; PR-AUC + calibração | `adr/0005-metricas.md` |
