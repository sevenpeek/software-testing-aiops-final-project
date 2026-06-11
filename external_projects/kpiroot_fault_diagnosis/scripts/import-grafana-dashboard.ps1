param(
    [int]$LocalPort = 3000,
    [string]$Username = "admin",
    [string]$Password = "admin",
    [string]$DashboardPath = "",
    [string]$LogsDir = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $DashboardPath) {
    $DashboardPath = Join-Path $repoRoot "grafana\online-boutique-maintenance-dashboard.json"
}
if (-not $LogsDir) {
    $LogsDir = Join-Path $repoRoot ".logs"
}
if (-not (Test-Path $DashboardPath)) {
    throw "Dashboard JSON not found: $DashboardPath"
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

$grafanaUrl = "http://127.0.0.1:$LocalPort"
$outLog = Join-Path $LogsDir "grafana-port-forward.out.log"
$errLog = Join-Path $LogsDir "grafana-port-forward.err.log"

$portInUse = Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue
if (-not $portInUse) {
    Start-Process -FilePath kubectl `
        -ArgumentList @("port-forward", "-n", "monitoring", "service/grafana", "${LocalPort}:80") `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog
}

$bytes = [System.Text.Encoding]::UTF8.GetBytes("${Username}:${Password}")
$auth = [Convert]::ToBase64String($bytes)
$headers = @{
    Authorization = "Basic $auth"
}

$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    try {
        Invoke-RestMethod -Uri "$grafanaUrl/api/health" -Headers $headers -Method Get | Out-Null
        break
    }
    catch {
        Start-Sleep -Seconds 1
    }
}

Invoke-RestMethod -Uri "$grafanaUrl/api/health" -Headers $headers -Method Get | Out-Null

$datasourceName = "Prometheus"
$datasourceUrl = "http://prometheus.monitoring.svc.cluster.local:9090"

try {
    $existingDatasource = Invoke-RestMethod -Uri "$grafanaUrl/api/datasources/name/$datasourceName" -Headers $headers -Method Get
    Write-Host "Updating Grafana datasource '$datasourceName'..."
    $datasourcePayload = @{
        id = $existingDatasource.id
        orgId = $existingDatasource.orgId
        name = $datasourceName
        type = "prometheus"
        access = "proxy"
        url = $datasourceUrl
        basicAuth = $false
        isDefault = $true
        jsonData = @{}
        version = $existingDatasource.version
    } | ConvertTo-Json -Depth 8

    Invoke-RestMethod `
        -Uri "$grafanaUrl/api/datasources/$($existingDatasource.id)" `
        -Headers $headers `
        -ContentType "application/json" `
        -Method Put `
        -Body $datasourcePayload | Out-Null
}
catch {
    Write-Host "Creating Grafana datasource '$datasourceName'..."
    $datasourcePayload = @{
        name = $datasourceName
        type = "prometheus"
        access = "proxy"
        url = $datasourceUrl
        isDefault = $true
    } | ConvertTo-Json -Depth 8

    Invoke-RestMethod `
        -Uri "$grafanaUrl/api/datasources" `
        -Headers $headers `
        -ContentType "application/json" `
        -Method Post `
        -Body $datasourcePayload | Out-Null
}

$dashboard = Get-Content -LiteralPath $DashboardPath -Raw | ConvertFrom-Json
foreach ($panel in $dashboard.panels) {
    $panel.datasource = $datasourceName
}

$payload = @{
    dashboard = $dashboard
    overwrite = $true
    folderId = 0
} | ConvertTo-Json -Depth 100

Invoke-RestMethod `
    -Uri "$grafanaUrl/api/dashboards/db" `
    -Headers $headers `
    -ContentType "application/json" `
    -Method Post `
    -Body $payload | Out-Null

Write-Host "Grafana dashboard imported: $grafanaUrl/d/online-boutique-maintenance"
