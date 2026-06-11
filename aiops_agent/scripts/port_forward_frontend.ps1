param(
    [string]$Namespace = "online-boutique",
    [int]$LocalPort = 8088
)

$ErrorActionPreference = "Stop"

kubectl wait --for=condition=available deployment/frontend -n $Namespace --timeout=180s
Write-Host "Frontend URL: http://127.0.0.1:$LocalPort"
kubectl port-forward -n $Namespace service/frontend "$LocalPort`:80"
