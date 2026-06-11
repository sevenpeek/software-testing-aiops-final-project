param(
    [string]$MonitoringNamespace = "monitoring",
    [string]$OnlineBoutiqueNamespace = "online-boutique"
)

$ErrorActionPreference = "Stop"

function Invoke-PrometheusQuery {
    param(
        [string]$Query,
        [string]$MonitoringNamespace
    )

    $encoded = [System.Uri]::EscapeDataString($Query)
    $url = "http://localhost:9090/api/v1/query?query=$encoded"
    kubectl exec -n $MonitoringNamespace deployment/prometheus-deployment -- wget -qO- $url
}

Write-Host "== Online-Boutique Pods =="
kubectl get pods -n $OnlineBoutiqueNamespace -o wide

Write-Host ""
Write-Host "== Monitoring Stack =="
kubectl get all -n $MonitoringNamespace

Write-Host ""
Write-Host "== ChaosMesh =="
kubectl get all -n chaos-testing

Write-Host ""
Write-Host "== Prometheus: Online-Boutique CPU series count =="
Invoke-PrometheusQuery -MonitoringNamespace $MonitoringNamespace -Query "count(container_cpu_usage_seconds_total{namespace=`"$OnlineBoutiqueNamespace`"})"

Write-Host ""
Write-Host "== Prometheus: Online-Boutique memory series count =="
Invoke-PrometheusQuery -MonitoringNamespace $MonitoringNamespace -Query "count(container_memory_working_set_bytes{namespace=`"$OnlineBoutiqueNamespace`"})"

Write-Host ""
Write-Host "== Prometheus: Online-Boutique restart metrics =="
Invoke-PrometheusQuery -MonitoringNamespace $MonitoringNamespace -Query "sum by (pod, container) (kube_pod_container_status_restarts_total{namespace=`"$OnlineBoutiqueNamespace`"})"

Write-Host ""
Write-Host "== Prometheus: frontend blackbox probe, if enabled =="
Invoke-PrometheusQuery -MonitoringNamespace $MonitoringNamespace -Query "probe_success{job=`"online-boutique-frontend-blackbox`"}"
