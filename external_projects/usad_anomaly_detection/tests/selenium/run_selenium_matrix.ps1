param(
  [string]$BaseUrl = "http://127.0.0.1:8080",
  [string[]]$Browsers = @("chrome", "edge", "firefox")
)

$ErrorActionPreference = "Continue"

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = $env:PYTHON
if (-not $python) {
  $python = "python"
}

$outDir = Join-Path $root "outputs_selenium_matrix"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$results = @()
foreach ($browser in $Browsers) {
  $browserOut = Join-Path $outDir $browser
  New-Item -ItemType Directory -Force -Path $browserOut | Out-Null
  & $python (Join-Path $PSScriptRoot "online_boutique_ui_test.py") --browser $browser --base-url $BaseUrl --out-dir $browserOut
  $resultFile = Join-Path $browserOut "selenium_result.json"
  if (Test-Path -LiteralPath $resultFile) {
    $json = Get-Content -LiteralPath $resultFile -Raw | ConvertFrom-Json
    $results += [pscustomobject]@{
      browser = $browser
      status = $json.status
      home_ms = (($json.steps | Where-Object name -eq "open_home").latency_ms)
      product_ms = (($json.steps | Where-Object name -eq "open_product").latency_ms)
      cart_ms = (($json.steps | Where-Object name -eq "open_cart").latency_ms)
      error = $json.error
    }
  } else {
    $results += [pscustomobject]@{
      browser = $browser
      status = "failed"
      home_ms = ""
      product_ms = ""
      cart_ms = ""
      error = "result file was not generated"
    }
  }
}

$csvPath = Join-Path $outDir "selenium_browser_matrix_summary.csv"
$mdPath = Join-Path $outDir "selenium_browser_matrix_summary.md"
$results | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $csvPath

$lines = @(
  "# Selenium Browser Compatibility Summary",
  "",
  "| Browser | Status | Home(ms) | Product(ms) | Cart(ms) | Note |",
  "|---|---|---:|---:|---:|---|"
)
foreach ($r in $results) {
  $lines += "| $($r.browser) | $($r.status) | $($r.home_ms) | $($r.product_ms) | $($r.cart_ms) | $($r.error) |"
}
$lines | Set-Content -Encoding UTF8 -Path $mdPath

Write-Host $csvPath
Write-Host $mdPath
