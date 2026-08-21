<#
.SYNOPSIS
    Orquestrador do projeto. Um comando reconstrói tudo a partir do PDF original.

.EXAMPLE
    .\tasks.ps1 all
    .\tasks.ps1 clean
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('ingest', 'clean', 'features', 'train', 'report', 'test', 'all', 'help')]
    [string]$Task = 'help'
)

$ErrorActionPreference = 'Stop'
$env:PYTHONPATH = "$PSScriptRoot\src"
$PDF = 'data/raw/Diabetes-2026.csv.pdf'
$CSV = 'data/raw/diabetes_2026_raw.csv'
$SILVER = 'data/processed/diabetes_silver.parquet'

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

function Invoke-Ingest {
    if (-not (Test-Path $PDF)) { throw "PDF fonte ausente: $PDF" }
    Step 'ingestao: PDF -> CSV bronze'
    python -m diabetes.ingest.pdf_to_csv --pdf $PDF --out $CSV `
        --manifest data/raw/_manifest_ingestao.json
}

function Invoke-Clean {
    if (-not (Test-Path $CSV)) { Invoke-Ingest }
    Step 'limpeza: CSV -> Parquet silver'
    python -m diabetes.clean.pipeline --entrada $CSV --saida $SILVER
}

function Invoke-Features { Step 'features: silver -> gold'; python -m diabetes.features.build }
function Invoke-Train    { Step 'treino: escada de modelos -> MLflow'; python -m diabetes.models.train }
function Invoke-Report   { Step 'relatorio: figuras e tabelas'; python -m diabetes.viz.report }

function Invoke-Test {
    Step 'lint'
    ruff check src tests
    Step 'testes'
    pytest -q
}

switch ($Task) {
    'ingest'   { Invoke-Ingest }
    'clean'    { Invoke-Clean }
    'features' { Invoke-Features }
    'train'    { Invoke-Train }
    'report'   { Invoke-Report }
    'test'     { Invoke-Test }
    'all'      { Invoke-Ingest; Invoke-Clean; Invoke-Features; Invoke-Train; Invoke-Report }
    default    { Get-Help $PSCommandPath -Detailed }
}
