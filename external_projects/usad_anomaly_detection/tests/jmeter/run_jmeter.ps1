param(
  [string]$HostName = "127.0.0.1",
  [string]$Port = "8080",
  [int]$Threads = 10,
  [int]$Loops = 8,
  [int]$RampSeconds = 10
)

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
$tmpPlan = Join-Path $outDir "online_boutique_load_test.runtime.jmx"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
Remove-Item -Recurse -Force $html -ErrorAction SilentlyContinue
Remove-Item -Force $jtl -ErrorAction SilentlyContinue

[xml]$xml = Get-Content -LiteralPath $plan -Raw
$threadGroup = $xml.SelectSingleNode("//ThreadGroup[@testname='Frontend Users']")
$threadGroup.SelectSingleNode("stringProp[@name='ThreadGroup.num_threads']").InnerText = [string]$Threads
$threadGroup.SelectSingleNode("stringProp[@name='ThreadGroup.ramp_time']").InnerText = [string]$RampSeconds
$threadGroup.SelectSingleNode(".//stringProp[@name='LoopController.loops']").InnerText = [string]$Loops
$argsNodes = $xml.SelectNodes("//elementProp[@elementType='Argument']")
foreach ($node in $argsNodes) {
  $name = $node.SelectSingleNode("stringProp[@name='Argument.name']").InnerText
  if ($name -eq "host") {
    $node.SelectSingleNode("stringProp[@name='Argument.value']").InnerText = $HostName
  }
  if ($name -eq "port") {
    $node.SelectSingleNode("stringProp[@name='Argument.value']").InnerText = $Port
  }
}
$xml.Save($tmpPlan)

& $jmeter -n -t $tmpPlan -l $jtl -e -o $html
