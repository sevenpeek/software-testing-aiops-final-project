param(
    [string]$Namespace = "online-boutique",
    [int]$LocalPort = 8088,
    [int]$TimeoutSeconds = 300,
    [switch]$SkipRolloutRestart,
    [switch]$NoPortForward
)

$ErrorActionPreference = "Stop"

function Remove-TerminalPods {
    param(
        [string]$Namespace
    )

    $pods = @()
    $pods += @(kubectl get pods -n $Namespace --field-selector=status.phase=Failed -o name --ignore-not-found)
    $pods += @(kubectl get pods -n $Namespace --field-selector=status.phase=Succeeded -o name --ignore-not-found)
    $pods = @($pods | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

    if ($pods.Count -gt 0) {
        Write-Host "Deleting terminal pods left by the previous Minikube session..."
        kubectl delete -n $Namespace $pods --ignore-not-found
    }
}

function Wait-DeploymentsReady {
    param(
        [string]$Namespace,
        [int]$TimeoutSeconds
    )

    $deployments = @(kubectl get deployment -n $Namespace -o name)
    if ($deployments.Count -eq 0) {
        throw "No deployments found in namespace '$Namespace'."
    }

    foreach ($deployment in $deployments) {
        kubectl rollout status $deployment -n $Namespace --timeout="${TimeoutSeconds}s"
    }

    kubectl wait --for=condition=available deployment --all -n $Namespace --timeout="${TimeoutSeconds}s"
}

function Restart-Deployments {
    param(
        [string]$Namespace
    )

    $deployments = @(kubectl get deployment -n $Namespace -o name)
    if ($deployments.Count -eq 0) {
        throw "No deployments found in namespace '$Namespace'."
    }

    foreach ($deployment in $deployments) {
        kubectl rollout restart $deployment -n $Namespace
    }
}

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

    kubectl get endpointslices -n $Namespace -l kubernetes.io/service-name=frontend -o wide
    throw "Frontend service has no ready endpoint after ${TimeoutSeconds}s."
}

minikube start

$namespaceExists = kubectl get namespace $Namespace --ignore-not-found
if (-not $namespaceExists) {
    Write-Host "Namespace '$Namespace' does not exist. Deploying Online Boutique first..."
    & (Join-Path $PSScriptRoot "deploy-online-boutique.ps1") -Namespace $Namespace
}
else {
    $deployments = @(kubectl get deployment -n $Namespace -o name --ignore-not-found)
    if ($deployments.Count -eq 0) {
        Write-Host "Namespace '$Namespace' exists but has no deployments. Deploying Online Boutique first..."
        & (Join-Path $PSScriptRoot "deploy-online-boutique.ps1") -Namespace $Namespace
    }
}

Remove-TerminalPods -Namespace $Namespace

if (-not $SkipRolloutRestart) {
    Write-Host "Restarting Online Boutique deployments to recover cleanly after reboot..."
    Restart-Deployments -Namespace $Namespace
}

Wait-DeploymentsReady -Namespace $Namespace -TimeoutSeconds $TimeoutSeconds
Remove-TerminalPods -Namespace $Namespace
Wait-FrontendEndpoint -Namespace $Namespace -TimeoutSeconds $TimeoutSeconds

kubectl get pods -n $Namespace -o wide

if ($NoPortForward) {
    Write-Host ""
    Write-Host "Online Boutique is ready. Port forwarding was skipped because -NoPortForward was set."
    exit 0
}

Write-Host ""
Write-Host "Frontend will be available at http://127.0.0.1:$LocalPort"
Write-Host "Keep this terminal open while using the frontend."
& (Join-Path $PSScriptRoot "port-forward-frontend.ps1") -Namespace $Namespace -LocalPort $LocalPort -TimeoutSeconds $TimeoutSeconds
