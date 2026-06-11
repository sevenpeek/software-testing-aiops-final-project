param(
    [string]$Namespace = "online-boutique"
)

$ErrorActionPreference = "Stop"

kubectl get ns

kubectl get namespace $Namespace *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Namespace online-boutique does not exist. Please deploy Online Boutique first."
    exit 1
}

kubectl get pods -n $Namespace -o wide
kubectl get deploy -n $Namespace
kubectl get svc -n $Namespace
kubectl get events -n $Namespace --sort-by=.lastTimestamp
