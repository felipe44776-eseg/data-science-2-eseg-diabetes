# ADR 0003 — Local-first; GCP apenas com gatilho declarado

**Status:** aceito · **Data:** 2026-08-21

## Contexto
Base limpa: 253.680 × 31 em `uint8` = **8,6 MB em memória**, ~0,6 MB em Parquet+zstd.
O stack padrão do consultor é GCP, o que cria a tentação de subir tudo para BigQuery.

## Decisão
Parquet + DuckDB local. MLflow em `file:./mlruns`. Nenhum recurso de nuvem provisionado.

**Gatilhos que reabrem a decisão:** (1) ingestão de múltiplos anos do BRFSS completo
(441k × N × ~330 colunas); (2) re-treino agendado ou serving em API; (3) consumo por
terceiros sem clonar o repositório.

## Consequências
- Reprodutível offline, sem credencial, sem custo, sem risco de contaminação entre tenants.
- Arquitetura GCP fica desenhada em `docs/04-arquitetura.md` §5, pronta se o gatilho disparar.
- Se houver migração: tenant **ESEG** (`felipe_44776@aluno.eseg.edu.br`, config `eseg`),
  região `southamerica-east1`. Nunca sob conta de cliente.
