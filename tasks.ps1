<#
.SYNOPSIS
    Orquestrador do projeto. Um comando reconstrói tudo a partir do PDF original.

.DESCRIPTION
    Toda execução é registrada em reports/execucao.jsonl (início, fim, duração,
    código de saída). Use `.\tasks.ps1 status` para ver o que rodou, o que está
    obsoleto e qual é a próxima etapa acionável.

.EXAMPLE
    .\tasks.ps1 status      # o que rodou, o que está velho, o que falta
    .\tasks.ps1 log         # histórico de execuções
    .\tasks.ps1 all         # PDF -> relatório
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('status', 'log', 'ingest', 'clean', 'folds', 'external', 'eda',
                 'explicativo', 'figuras', 'modelos', 'vigitel',
                 'expandido', 'pesos', 'pu', 'glassbox', 'medicaid', 'trilhac',
                 'test', 'all', 'help')]
    [string]$Task = 'help'
)

$ErrorActionPreference = 'Stop'
$env:PYTHONPATH = "$PSScriptRoot\src"
$env:PYTHONIOENCODING = 'utf-8'

$PDF    = 'data/raw/Diabetes-2026.csv.pdf'
$CSV    = 'data/raw/diabetes_2026_raw.csv'
$SILVER = 'data/processed/diabetes_silver.parquet'
$XPT    = 'data/external/brfss2015/LLCP2015.XPT'
$LOG    = Join-Path $PSScriptRoot 'reports/execucao.jsonl'

function Write-Log($etapa, $evento, $extra) {
    $reg = [ordered]@{
        ts     = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss')
        etapa  = $etapa
        evento = $evento
        pid    = $PID
    }
    if ($extra) { foreach ($k in $extra.Keys) { $reg[$k] = $extra[$k] } }
    $dir = Split-Path $LOG -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    ($reg | ConvertTo-Json -Compress) | Add-Content -Path $LOG -Encoding utf8
}

# Envelopa uma etapa: registra início/fim, cronometra e propaga a falha.
function Invoke-Etapa($chave, $titulo, [scriptblock]$corpo) {
    Write-Host "==> $titulo" -ForegroundColor Cyan
    Write-Log $chave 'inicio' @{ detalhe = $titulo }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    try {
        & $corpo
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "saida $LASTEXITCODE" }
        $sw.Stop()
        $s = [math]::Round($sw.Elapsed.TotalSeconds, 1)
        Write-Log $chave 'fim' @{ segundos = $s }
        Write-Host "    concluido em ${s}s" -ForegroundColor DarkGray
    }
    catch {
        $sw.Stop()
        Write-Log $chave 'erro' @{
            segundos = [math]::Round($sw.Elapsed.TotalSeconds, 1)
            detalhe  = $_.Exception.Message
        }
        Write-Host "    FALHOU: $($_.Exception.Message)" -ForegroundColor Red
        throw
    }
}

function Assert-Arquivo($caminho, $dica) {
    if (-not (Test-Path (Join-Path $PSScriptRoot $caminho))) {
        throw "arquivo ausente: $caminho. $dica"
    }
}

# --- etapas ---------------------------------------------------------------

function Invoke-Ingest {
    Assert-Arquivo $PDF 'Coloque o PDF do professor em data/raw/.'
    Invoke-Etapa 'ingest' 'Ingestao: PDF -> CSV bronze' {
        python -m diabetes.ingest.pdf_to_csv --pdf $PDF --out $CSV `
            --manifest data/raw/_manifest_ingestao.json
    }
}

function Invoke-Clean {
    if (-not (Test-Path $CSV)) { Invoke-Ingest }
    Invoke-Etapa 'clean' 'Limpeza: CSV -> Parquet silver' {
        python -m diabetes.clean.pipeline --entrada $CSV --saida $SILVER
    }
}

function Invoke-Folds {
    Invoke-Etapa 'folds' 'Particionamento a prova de vazamento' {
        python -m diabetes.features.split --silver $SILVER
    }
}

function Invoke-External {
    Assert-Arquivo $XPT 'URL, hash e prova de integridade em data/external/FONTES.md.'
    Invoke-Etapa 'external' 'BRFSS 2015: reconstrucao + cascata de exclusoes' {
        python -m diabetes.external.brfss2015 --xpt $XPT
        python -m diabetes.external.vies_amostral --xpt $XPT
    }
}

function Invoke-Eda {
    Assert-Arquivo $XPT 'URL e hash em data/external/FONTES.md.'
    Invoke-Etapa 'eda' 'EDA comparativa: arquivo entregue vs BRFSS ponderado' {
        python -m diabetes.eda.comparativo --xpt $XPT
    }
}

function Invoke-Explicativo {
    Assert-Arquivo $XPT 'URL e hash em data/external/FONTES.md.'
    Invoke-Etapa 'explicativo' 'Modelo explicativo: M1/M2/M3 + odds proporcionais' {
        python -m diabetes.models.explicativo --xpt $XPT
    }
}

function Invoke-Figuras {
    Invoke-Etapa 'figuras' 'Figuras do relatorio' { python -m diabetes.viz.figuras }
}

function Invoke-Modelos {
    Invoke-Etapa 'modelos' 'Escada de modelos preditivos' {
        python -m diabetes.models.escada --silver $SILVER
    }
}

function Invoke-Vigitel {
    Invoke-Etapa 'vigitel' 'Vigitel: comparacao binacional de odds ratio' {
        python -m diabetes.external.vigitel
    }
}

function Invoke-Expandido {
    Assert-Arquivo $XPT 'URL e hash em data/external/FONTES.md.'
    Invoke-Etapa 'expandido' 'Frente 1: variaveis expandidas + ablacao + auditoria racial' {
        python -m diabetes.features.expandido --xpt $XPT
        python -m diabetes.models.expandido
    }
}

function Invoke-Pesos {
    Invoke-Etapa 'pesos' 'Frente 5: inferencia complexa e pesos por raking' {
        python -m diabetes.external.pesos
    }
}

function Invoke-Pu {
    Invoke-Etapa 'pu' 'Frente 2: Positive-Unlabeled' { python -m diabetes.models.pu }
}

function Invoke-Glassbox {
    Invoke-Etapa 'glassbox' 'Frente 3: EBM e predicao conforme' {
        python -m diabetes.models.glassbox
    }
}

function Invoke-Medicaid {
    Invoke-Etapa 'medicaid' 'Frente 4: expansao do Medicaid (DiD)' {
        python -m diabetes.external.medicaid
    }
}

function Invoke-TrilhaC {
    Invoke-Etapa 'trilhac' 'Trilha C: escore de pontos, curva de decisao e equidade' {
        python -m diabetes.eval.escore
        python -m diabetes.eval.decisao
        python -m diabetes.eval.equidade
    }
}

function Invoke-Test {
    Invoke-Etapa 'test' 'Lint e testes' {
        python -m ruff check src tests
        python -m pytest -q
    }
}

# --- despacho -------------------------------------------------------------

switch ($Task) {
    'status'      { python -m diabetes.pipeline.estado }
    'log'         { python -m diabetes.pipeline.estado --execucoes }
    'ingest'      { Invoke-Ingest }
    'clean'       { Invoke-Clean }
    'folds'       { Invoke-Folds }
    'external'    { Invoke-External }
    'eda'         { Invoke-Eda }
    'explicativo' { Invoke-Explicativo }
    'figuras'     { Invoke-Figuras }
    'modelos'     { Invoke-Modelos }
    'vigitel'     { Invoke-Vigitel }
    'expandido'   { Invoke-Expandido }
    'pesos'       { Invoke-Pesos }
    'pu'          { Invoke-Pu }
    'glassbox'    { Invoke-Glassbox }
    'medicaid'    { Invoke-Medicaid }
    'trilhac'     { Invoke-TrilhaC }
    'test'        { Invoke-Test }
    'all' {
        Invoke-Ingest; Invoke-Clean; Invoke-Folds
        if (Test-Path (Join-Path $PSScriptRoot $XPT)) {
            Invoke-External; Invoke-Eda; Invoke-Explicativo
        }
        else {
            Write-Host 'XPT do BRFSS ausente - etapas externas puladas. Ver data/external/FONTES.md' -ForegroundColor Yellow
            Write-Log 'all' 'pulado' @{ detalhe = 'XPT ausente' }
        }
        Invoke-Modelos; Invoke-Figuras
        if (Test-Path (Join-Path $PSScriptRoot $XPT)) {
            Invoke-Expandido; Invoke-Pesos; Invoke-Pu; Invoke-Glassbox; Invoke-TrilhaC
        }
        Invoke-Medicaid
        python -m diabetes.pipeline.estado
    }
    default { Get-Help $PSCommandPath -Detailed }
}
