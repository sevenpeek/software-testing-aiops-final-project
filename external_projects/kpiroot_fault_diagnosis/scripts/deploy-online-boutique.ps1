param(
    [string]$Namespace = "online-boutique"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$manifest = Join-Path $repoRoot "Online-Boutique\release\kubernetes-manifests.yaml"

if (-not (Test-Path $manifest)) {
    throw "Manifest not found: $manifest"
}

minikube start

$existingNamespace = kubectl get namespace $Namespace --ignore-not-found
if (-not $existingNamespace) {
    kubectl create namespace $Namespace
}

kubectl apply -n $Namespace -f $manifest
kubectl wait --for=condition=available deployment --all -n $Namespace --timeout=300s
kubectl get pods -n $Namespace -o wide
kubectl get svc -n $Namespace -o wide
