param(
    [string]$BaseUrl = "http://127.0.0.1:8088",
    [ValidateSet("edge", "chrome")]
    [string]$Browser = "edge",
    [string]$DriverPath = "",
    [string]$BrowserBinary = "",
    [switch]$ShowBrowser
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$env:ONLINE_BOUTIQUE_URL = $BaseUrl
$env:SELENIUM_BROWSER = $Browser
$env:SELENIUM_HEADLESS = if ($ShowBrowser) { "0" } else { "1" }
$env:PHASE3_SCREENSHOT_DIR = Join-Path $projectRoot "data\phase3\selenium\screenshots"
$env:PHASE3_SELENIUM_METRICS = Join-Path $projectRoot "data\phase3\selenium\timing_metrics.csv"
if ($DriverPath) { $env:SELENIUM_DRIVER_PATH = $DriverPath }
if ($BrowserBinary) { $env:SELENIUM_BROWSER_BINARY = $BrowserBinary }

New-Item -ItemType Directory -Force -Path $env:PHASE3_SCREENSHOT_DIR | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $env:PHASE3_SELENIUM_METRICS) | Out-Null

& (Join-Path $projectRoot ".conda\python.exe") -m pytest (Join-Path $projectRoot "tests\selenium") -v -o "cache_dir=$projectRoot\.pytest_cache"
