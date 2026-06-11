param(
    [string]$Scenario = "",
    [string]$Alarm = "",
    [int]$PaaSize = 32,
    [double]$LambdaWeight = 0.9
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = Join-Path $projectRoot "src"
$env:MPLCONFIGDIR = Join-Path $projectRoot ".cache\matplotlib"

$python = Join-Path $projectRoot ".conda\python.exe"
$phase2Dir = Join-Path $projectRoot "data\phase2"
$outputDir = Join-Path $projectRoot "data\phase4\kpiroot"
$report = Join-Path $projectRoot "docs\PHASE4_KPIROOT.md"

New-Item -ItemType Directory -Force -Path $env:MPLCONFIGDIR | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $report) | Out-Null

$arguments = @(
    "-m", "kpiroot.cli",
    "--phase2-dir", $phase2Dir,
    "--output-dir", $outputDir,
    "--report", $report,
    "--paa-size", $PaaSize,
    "--lambda-weight", $LambdaWeight
)

if ($Scenario) {
    $arguments += @("--scenario", $Scenario)
}

if ($Alarm) {
    $arguments += @("--alarm", $Alarm)
}

& $python @arguments
