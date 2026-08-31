# CLAUDE.md — Data Science 2 · Projeto 1 (Diabetes)

Contexto de projeto. Herda de `~/CLAUDE.md` tudo que não estiver aqui.

## Tenant

**ESEG (acadêmico)** — nunca tocar em recurso de cliente a partir deste diretório.

| | |
|---|---|
| Identidade git | `felipe_44776@aluno.eseg.edu.br` |
| Conta gh | `felipe44776-eseg` |
| Repo | `felipe44776-eseg/data-science-2-eseg-diabetes` |
| gcloud config | `eseg` (não utilizada — projeto é local-first, ver ADR 0003) |

Subagente que rode `git`/`gh` aqui deve receber o tenant declarado no prompt.

## Equipe

| integrante | RA |
|---|---|
| Felipe Marins | 44776 |
| Otavio Bonfochi | *a confirmar* |
| Phelipe Torres Pamponet da França | 46643 |
| Tadeu Radovan Graça | 46305 |

Fonte única: `src/diabetes/produto/autoria.py`. Nome de integrante **não se
escreve à mão em nenhum outro lugar** — as cinco superfícies HTML leem de lá e
`tests/test_produto.py` falha se alguma perder um nome. Ordem alfabética de
propósito: não há primeiro autor.

Só o Felipe tem credencial git/gh neste repositório. Contribuição de outro
integrante entra por PR ou por commit com `Co-authored-by:`.

## Stack

Python 3.11 · pandas · pyarrow · scikit-learn · LightGBM · statsmodels · SHAP · DoWhy ·
**interpret** (o EBM é o modelo do produto) · prince (MCA) · mlxtend (FP-Growth).
Armazenamento: Parquet. **Sem GCP** — ver ADR 0003 e o gatilho que reabriria a decisão.

*DuckDB e MLflow foram planejados e nunca usados* — `mlflow` continua em
`requirements.txt` mas não é importado em lugar nenhum, e não existe `./mlruns`.
Não descrever o projeto como se houvesse rastreamento de experimento: o que existe
é `.\tasks.ps1 status` / `log`, em `src/diabetes/pipeline/estado.py`.

## Comandos

```powershell
.\tasks.ps1 all      # PDF -> bronze -> silver -> gold -> relatório
.\tasks.ps1 test     # ruff + pytest
```

`PYTHONPATH` aponta para `src/` (já configurado em `tasks.ps1` e `pyproject.toml`).

## Invariantes — não violar

1. **`src/diabetes/schema.py` é a única fonte de verdade** de nome, tipo, domínio e
   semântica de coluna. Nenhum literal de nome de coluna fora dele.
2. **Nenhuma linha é descartada em silêncio.** Toda remoção vai para quarentena com o motivo,
   e toda regra emite contagem no relatório de qualidade.
3. **Nunca `train_test_split` aleatório.** 23.899 duplicatas exatas contaminam 13,65% do
   teste. Usar `features/split.py` (partição por hash das features). ADR 0002.
   *Nota:* a inflação medida é pequena (0,1–1,2%, `docs/08` §2.1) — a regra permanece porque
   é gratuita e defensável, não porque o efeito seja grande. Não repetir a alegação antiga
   de que o split ingênuo "infla muito" a métrica.
4. **Acurácia não é reportada.** PR-AUC, recall @ especificidade, Brier, calibração. ADR 0005.
5. **SMOTE não é o método adotado** — cost-sensitive + ajuste de limiar. ADR 0004.
   SMOTE entra só como ablação para sustentar a escolha com número.
6. **Dado não é versionado; manifesto com hash é.** O PDF fonte (109 MB) fica fora do git.
7. **Notebook não contém lógica** — importa de `src/` e mostra resultado.
8. **`exame_colesterol`, `acesso_saude`, `sem_consulta_por_custo` não são fatores de risco**
   — são marcadores de detecção. Bloco separado, modelo reportado com e sem eles.
9. O alvo mede **diagnóstico autorrelatado**, não a doença. ~27,6% dos diabéticos não sabem
   (NHANES). Qualquer conclusão redigida como "tem diabetes" está errada.
10. **Toda prevalência é reportada em par:** não ponderada (arquivo) e ponderada (`_LLCPWT`
    do BRFSS). Sozinha, a não ponderada superestima diabetes em 32,7%. Ver `docs/05`.
11. **Todo IC calculado como amostra aleatória simples é estreito demais** — o DEFF real,
    por linearização de Taylor com `_STSTR` e `_PSU`, é **2,94** (multiplicador 1,71×).
    A aproximação de Kish (4,04) que usávamos era conservadora. Ver `docs/11` §A.
12. **Análise de desigualdade de acesso não pode ser feita só no arquivo entregue.**
    96,3% fizeram exame de colesterol contra 77,9% na população: a variação de acesso foi
    removida da amostra. Usar `data/external/brfss2015/brfss2015_reconstruido.parquet`.

## Estado

**Projeto encerrado em 2026-08-31.** 26/26 etapas coerentes, 137 testes, CI e Pages
verdes. 25 documentos + 5 ADRs, 6 notebooks, 26 + 11 slides, 6 superfícies publicadas.

Frentes abertas — **documentadas, nenhuma iniciada**, em `docs/25` §Para retomar:
recalibrar o produto para 2023 (`docs/22` §6, a mais barata), NHANES individual com
HbA1c, PNS 2019, determinantes sociais medidos, anos intermediários do Vigitel.

Os 57 achados sem veredito da auditoria adversarial **não são confirmados**. Tratá-los
como reais é o erro oposto ao que a auditoria existe para evitar.

O XPT do BRFSS (1,17 GB) fica fora do git — URL, hash e prova de integridade em
`data/external/FONTES.md`. `www.cdc.gov` bloqueia acesso automatizado (403);
`data.cdc.gov` não.

## Reconstruir o projeto do zero

Escrito para quem não estava na sessão — outro integrante do grupo, o professor,
ou uma sessão futura de agente. **Nada aqui depende de contexto de conversa**:
se `status` fechar em 26/26, o que está publicado reflete o dado atual.

### Pré-requisitos

| | |
|---|---|
| Python | **3.11** (o pin de `requirements.txt` é testado nessa versão) |
| Node | 18+ — **só** para `tests/paridade_js.mjs`; sem dependência de npm |
| Shell | PowerShell 7 — `tasks.ps1` é PS, não bash |
| Disco | ~4 GB: 2,5 GB de insumo externo + ~1 GB de Parquet derivado |
| Rede | os downloads são do `data.cdc.gov` e do `svs.aids.gov.br` |

### Os quatro comandos

```powershell
git clone https://github.com/felipe44776-eseg/data-science-2-eseg-diabetes.git
cd data-science-2-eseg-diabetes

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

.\tasks.ps1 dados      # baixa 2,5 GB e confere o SHA-256 de cada arquivo
.\tasks.ps1 all        # PDF -> bronze -> silver -> gold -> produto -> superficies
.\tasks.ps1 status     # tem de fechar 26/26 ok
.\tasks.ps1 test       # ruff + pytest: 137 testes
```

`all` leva algo entre 40 e 90 minutos, quase tudo em `expandido`, `pu` e
`glassbox`. Cada etapa isolada tem verbo próprio — `.\tasks.ps1 help` lista.

### O que não vem no git, e por quê

Invariante 6: **dado não é versionado, manifesto com hash é.** O repositório
inteiro tem 2,6 MB.

| insumo | tamanho | como obter |
|---|---|---|
| PDF do enunciado | 109 MB | **não tem URL pública** — copiar à mão para `data/raw/Diabetes-2026.csv.pdf`. Hash em `data/external/FONTES.md` |
| BRFSS 2015 `LLCP2015.XPT` | 1,17 GB | `.\tasks.ps1 dados` |
| BRFSS 2023 `LLCP2023.XPT` | 1,21 GB | `.\tasks.ps1 dados` |
| Vigitel 2015 e 2023 | 12 MB | `.\tasks.ps1 dados` |
| CDC Open Data | API | `.\tasks.ps1 medicaid` |

`dados` **aborta se um hash divergir** — não segue com arquivo diferente do que
produziu os números publicados. Se o CDC republicar o XPT, é isso que avisa.

As duas ausências se comportam de forma **diferente, de propósito**: sem o PDF,
`all` **aborta** já em `ingest` (`Assert-Arquivo` lança) — é o insumo do trabalho
e seguir sem ele não faria sentido. Sem o XPT, `all` **pula 17 das 26 etapas** e
avisa em amarelo, porque o núcleo (ingestão, limpeza, partição, modelos) não
depende dele. Nenhum dos dois falha em silêncio.

### Se `status` não fechar 26/26

| o que aparece | significa | o que fazer |
|---|---|---|
| `ausente` | a etapa nunca rodou | rodar o verbo dela |
| `OBSOLETO` | uma entrada mudou depois da última execução | rodar de novo; o `status` diz qual entrada |
| `ok` mas número diferente do publicado | o insumo mudou na origem | conferir `.\tasks.ps1 dados --verificar` antes de qualquer coisa |

`status` é gerado de hash de arquivo, não de anotação manual — ele não mente
sobre estar atualizado.

### Onde cada coisa mora

| quero… | vou em |
|---|---|
| o contrato de dados | `src/diabetes/schema.py` — **única** fonte de nome/tipo/domínio |
| o grafo de etapas | `src/diabetes/pipeline/estado.py` — `ETAPAS`, entradas e saídas de cada uma |
| a autoria | `src/diabetes/produto/autoria.py` |
| o modelo do produto | `reports/produto/modelo.json` — **é** o modelo, não um resumo dele |
| as decisões travadas | `docs/adr/` — 5 ADRs |
| o percurso | `docs/25-linha-do-tempo.md` — 13 fases, com o que cada uma refutou |
| o que falta | `docs/25` §Para retomar |

### Falhas conhecidas de ambiente

- **`www.cdc.gov` responde 403** a acesso automatizado. `data.cdc.gov` não —
  `baixar.py` já usa o segundo. Não "consertar" trocando de volta.
- **Vigitel 2015 é `.xls` OLE2**, não `.xlsx`: exige `xlrd`. Está declarado.
- **`interpret` não é opcional** — sem ele não há calculadora nem `docs/13`.
- O PDF é extraído por coordenada de *bounding box* (PyMuPDF), não por texto.
  Trocar de biblioteca refaz o resultado do zero; ver `docs/01`.

### Uma coisa que a suíte não cobre

O número de acessibilidade do README — *WCAG AA, 1.534 amostras, 0 falhas* — foi
medido com um script Puppeteer **de uso único, não versionado**. É uma medição
real, feita nas seis superfícies em claro e escuro, mas **não é reproduzível por
`.\tasks.ps1 test`**. Quem quiser reconferir tem de reescrever o script. Está
listado aqui para que ninguém o cite como se o CI o garantisse.
