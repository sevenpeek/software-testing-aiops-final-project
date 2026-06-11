param(
  [string]$BaseUrl = "http://127.0.0.1:8080",
  [int]$Samples = 120,
  [double]$IntervalSeconds = 1.0,
  [int]$FaultStart = 45,
  [int]$FaultEnd = 75
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = $env:PYTHON
if (-not $python) {
  $python = "python"
}

$dataPath = Join-Path $root "data\online_boutique_chaosmesh_metrics.csv"
$outDir = Join-Path $root "outputs_online_boutique_chaosmesh"
$evidencePath = Join-Path $root "docs\chaosmesh_kpi_collection_evidence.md"

& $python (Join-Path $root "src\collect_online_boutique_chaosmesh_metrics.py") `
  --base-url $BaseUrl `
  --samples $Samples `
  --interval $IntervalSeconds `
  --fault-start $FaultStart `
  --fault-end $FaultEnd `
  --out $dataPath `
  --evidence-out $evidencePath

& $python (Join-Path $root "src\run_usad.py") `
  --input $dataPath `
  --out $outDir `
  --window 6 `
  --epochs 120 `
  --train-ratio 0.35 `
  --title "USAD anomaly score on Online Boutique ChaosMesh KPI"

Write-Host "ChaosMesh KPI CSV: $dataPath"
Write-Host "USAD output: $outDir"
Write-Host "Evidence: $evidencePath"
