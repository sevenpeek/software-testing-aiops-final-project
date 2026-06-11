param(
    [string]$Namespace = "online-boutique",
    [string]$ManifestPath = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")
if (-not $ManifestPath) {
    $ManifestPath = Join-Path $projectRoot "aiops_agent\k8s\online-boutique\kubernetes-manifests.yaml"
}

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    Write-Error "Missing Kubernetes manifest. Please place kubernetes-manifests.yaml under aiops_agent/k8s/online-boutique/"
    exit 1
}

kubectl get namespace $Namespace *> $null
if ($LASTEXITCODE -ne 0) {
    kubectl create namespace $Namespace
}

kubectl apply -n $Namespace -f $ManifestPath
kubectl wait --for=condition=available deployment --all -n $Namespace --timeout=300s
kubectl get pods -n $Namespace -o wide
kubectl get svc -n $Namespace -o wide
