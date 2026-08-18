param(
    [Parameter(Mandatory = $true)]
    [string]$Source,
    [string]$OutputDir = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot 'runtime\python\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Clean runtime is missing. Run scripts\install-runtime.ps1 first.' }
if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "Source image not found: $Source" }
if (-not $OutputDir) { $OutputDir = Join-Path $ProjectRoot 'output' }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONPATH = $ProjectRoot
$Started = Get-Date
& $Python -u -m app.cli run $Source $OutputDir
$ExitCode = $LASTEXITCODE
$Elapsed = (Get-Date) - $Started
Write-Host ("Benchmark wall time: {0:N2}s" -f $Elapsed.TotalSeconds)
exit $ExitCode
