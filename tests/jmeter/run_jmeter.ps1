$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$jmeterHome = $env:JMETER_HOME
if (-not $jmeterHome) {
  throw "Please set JMETER_HOME to the Apache JMeter directory, for example: `$env:JMETER_HOME='D:\...\apache-jmeter-5.6.3'"
}
$jmeter = Join-Path $jmeterHome "bin\jmeter.bat"
$plan = Join-Path $PSScriptRoot "online_boutique_load_test.jmx"
$outDir = Join-Path $root "outputs_jmeter"
$jtl = Join-Path $outDir "online_boutique_load_test.jtl"
$html = Join-Path $outDir "html"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
Remove-Item -Recurse -Force $html -ErrorAction SilentlyContinue
Remove-Item -Force $jtl -ErrorAction SilentlyContinue

& $jmeter -n -t $plan -l $jtl -e -o $html
