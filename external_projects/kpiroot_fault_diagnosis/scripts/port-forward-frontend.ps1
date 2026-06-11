param(
    [string]$Namespace = "online-boutique",
    [int]$LocalPort = 8088,
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"

function Wait-FrontendEndpoint {
    param(
        [string]$Namespace,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $address = kubectl get endpointslices -n $Namespace -l kubernetes.io/service-name=frontend -o jsonpath='{.items[0].endpoints[0].addresses[0]}' 2>$null
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($address)) {
            Write-Host "Frontend endpoint is ready: $address"
            return
        }

        Start-Sleep -Seconds 2
    }

    kubectl get pods -n $Namespace -o wide
    kubectl get endpointslices -n $Namespace -l kubernetes.io/service-name=frontend -o wide
    throw "Frontend service has no ready endpoint after ${TimeoutSeconds}s. Run resume-online-boutique.ps1 first."
}

kubectl get namespace $Namespace | Out-Null
kubectl wait --for=condition=available deployment/frontend -n $Namespace --timeout="${TimeoutSeconds}s"
Wait-FrontendEndpoint -Namespace $Namespace -TimeoutSeconds $TimeoutSeconds

Write-Host ""
Write-Host "Frontend will be available at http://127.0.0.1:$LocalPort"
Write-Host "Keep this terminal open while using the frontend."
kubectl port-forward -n $Namespace service/frontend "${LocalPort}:80"
