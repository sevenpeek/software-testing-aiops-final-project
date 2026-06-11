param(
    [ValidateSet("cpu_stress", "memory_stress", "pod_kill", "network_delay")]
    [string]$FaultType = "cpu_stress",
    [string]$Service = "paymentservice",
    [string]$ChaosNamespace = "chaos-testing"
)

$ErrorActionPreference = "Stop"

switch ($FaultType) {
    "cpu_stress" {
        $resource = "stresschaos"
        $chaosName = "$Service-cpu-stress"
    }
    "memory_stress" {
        $resource = "stresschaos"
        $chaosName = "$Service-memory-stress"
    }
    "pod_kill" {
        $resource = "podchaos"
        $chaosName = "$Service-pod-kill"
    }
    "network_delay" {
        $resource = "networkchaos"
        $chaosName = "$Service-network-delay"
    }
}

Write-Host "Deleting ChaosMesh fault if it exists."
Write-Host "FaultType: $FaultType"
Write-Host "Service: $Service"
Write-Host "Resource: $resource"
Write-Host "Name: $chaosName"
Write-Host "ChaosNamespace: $ChaosNamespace"
Write-Host "This script does not restart deployments."

kubectl delete $resource $chaosName -n $ChaosNamespace --ignore-not-found
Write-Host "Chaos objects after deletion:"
kubectl get stresschaos,podchaos,networkchaos -n $ChaosNamespace
