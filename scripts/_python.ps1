# Usa somente a venv do projeto, independentemente do diretório de chamada.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Argumentos)
$ErrorActionPreference = 'Stop'
$raizPrumo = Split-Path -Parent $PSScriptRoot
$pythonPrumo = Join-Path $raizPrumo '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPrumo)) {
    throw 'Crie a venv com py -3.12 -m venv .venv e instale requirements/development.txt.'
}
& $pythonPrumo (Join-Path $PSScriptRoot 'dev.py') @Argumentos
exit $LASTEXITCODE
