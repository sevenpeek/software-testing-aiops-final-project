param(
    [string]$MonitoringNamespace = "monitoring",
    [string]$OnlineBoutiqueNamespace = "online-boutique",
    [string]$ManifestPath = ""
)

$ErrorActionPreference = "Stop"

if (-not $ManifestPath) {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $ManifestPath = Join-Path $repoRoot "monitoring\blackbox-exporter.yaml"
}

if (-not (Test-Path $ManifestPath)) {
    throw "Blackbox exporter manifest not found: $ManifestPath"
}

Write-Host "Applying blackbox exporter manifest..."
kubectl apply -f $ManifestPath
kubectl rollout status deployment/blackbox-exporter -n $MonitoringNamespace --timeout=180s

$jobName = "online-boutique-frontend-blackbox"
$frontendTarget = "http://frontend.$OnlineBoutiqueNamespace.svc.cluster.local/"
$blackboxAddress = "blackbox-exporter.$MonitoringNamespace.svc.cluster.local:9115"

$cm = kubectl get configmap prometheus-configmap -n $MonitoringNamespace -o json | ConvertFrom-Json
$prometheusConfig = $cm.data.'prometheus.yml'

Write-Host "Normalizing Prometheus scrape job '$jobName'..."
$jobPattern = "(?ms)`n\s*-\s*job_name:\s*'$([regex]::Escape($jobName))'.*?(?=`n\s*-\s*job_name:|\z)"
$prometheusConfig = [regex]::Replace($prometheusConfig, $jobPattern, "")

# The lab2 Prometheus config writes scrape_configs list items without extra
# indentation, so this job intentionally starts at column 1.
$scrapeJob = @"
- job_name: '$jobName'
  metrics_path: /probe
  params:
    module: [http_2xx]
  static_configs:
  - targets:
    - $frontendTarget
  relabel_configs:
  - source_labels: [__address__]
    target_label: __param_target
  - source_labels: [__param_target]
    target_label: instance
  - target_label: __address__
    replacement: $blackboxAddress
"@
$prometheusConfig = $prometheusConfig.TrimEnd() + "`n" + $scrapeJob + "`n"

$patch = @{
    data = @{
        "prometheus.yml" = $prometheusConfig
    }
} | ConvertTo-Json -Depth 8

$patchPath = Join-Path ([System.IO.Path]::GetTempPath()) "prometheus-configmap-blackbox-patch.json"
Set-Content -LiteralPath $patchPath -Value $patch -Encoding UTF8
kubectl patch configmap prometheus-configmap -n $MonitoringNamespace --type merge --patch-file $patchPath

Write-Host "Restarting Prometheus to load the scrape job..."
kubectl rollout restart deployment/prometheus-deployment -n $MonitoringNamespace
kubectl rollout status deployment/prometheus-deployment -n $MonitoringNamespace --timeout=180s

Write-Host "Waiting for Prometheus to scrape the frontend probe..."
Start-Sleep -Seconds 20

$query = [System.Uri]::EscapeDataString("probe_success{job=`"$jobName`"}")
$url = "http://localhost:9090/api/v1/query?query=$query"
kubectl exec -n $MonitoringNamespace deployment/prometheus-deployment -- wget -qO- $url

Write-Host ""
Write-Host "Blackbox frontend probe setup is complete."
