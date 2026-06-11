param(
    [int]$Threads = 5,
    [int]$RampUp = 10,
    [int]$Loops = 3,
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8088,
    [string]$Protocol = "http",
    [string]$RunName = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$jmeterBat = "D:\Study\jmeter\apache-jmeter-5.1.1\bin\jmeter.bat"
$testPlan = Join-Path $projectRoot "tests\jmeter\online_boutique_load_test.jmx"

if (-not (Test-Path -LiteralPath $jmeterBat)) {
    throw "JMeter not found at $jmeterBat"
}

if (-not $RunName) {
    $RunName = "run-" + (Get-Date -Format "yyyyMMdd-HHmmss")
}

$outputRoot = Join-Path $projectRoot "data\phase3\jmeter\$RunName"
$reportDir = Join-Path $outputRoot "html-report"
$jtlPath = Join-Path $outputRoot "result.jtl"
$logPath = Join-Path $outputRoot "jmeter.log"
$effectiveTestPlan = Join-Path $outputRoot "effective-test-plan.jmx"

New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
if (Test-Path -LiteralPath $reportDir) {
    Remove-Item -LiteralPath $reportDir -Recurse -Force
}
if (Test-Path -LiteralPath $jtlPath) {
    Remove-Item -LiteralPath $jtlPath -Force
}
if (Test-Path -LiteralPath $logPath) {
    Remove-Item -LiteralPath $logPath -Force
}

$jmx = Get-Content -LiteralPath $testPlan -Raw
$jmx = $jmx.Replace('<stringProp name="ThreadGroup.num_threads">5</stringProp>', "<stringProp name=`"ThreadGroup.num_threads`">$Threads</stringProp>")
$jmx = $jmx.Replace('<stringProp name="ThreadGroup.ramp_time">10</stringProp>', "<stringProp name=`"ThreadGroup.ramp_time`">$RampUp</stringProp>")
$jmx = $jmx.Replace('<stringProp name="LoopController.loops">3</stringProp>', "<stringProp name=`"LoopController.loops`">$Loops</stringProp>")
$jmx = $jmx.Replace('${__P(host,127.0.0.1)}', $HostName)
$jmx = $jmx.Replace('${__P(port,8088)}', [string]$Port)
$jmx = $jmx.Replace('${__P(protocol,http)}', $Protocol)
Set-Content -LiteralPath $effectiveTestPlan -Value $jmx -Encoding UTF8

& $jmeterBat `
    -n `
    -t $effectiveTestPlan `
    -l $jtlPath `
    -j $logPath `
    -e `
    -o $reportDir `
    -Jthreads=$Threads `
    -Jrampup=$RampUp `
    -Jloops=$Loops `
    -Jjmeter.save.saveservice.subresults=false

Write-Host "JMeter run completed."
Write-Host "JTL: $jtlPath"
Write-Host "HTML report: $reportDir"
