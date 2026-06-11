param(
  [string]$Browser = "chrome",
  [string]$BaseUrl = "http://127.0.0.1:8080"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = $env:PYTHON
if (-not $python) {
  $python = "python"
}
$outDir = Join-Path $root "outputs_selenium"
& $python (Join-Path $PSScriptRoot "online_boutique_ui_test.py") --browser $Browser --base-url $BaseUrl --out-dir $outDir
