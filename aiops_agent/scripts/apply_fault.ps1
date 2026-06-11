param(
    [ValidateSet("cpu_stress", "memory_stress", "pod_kill", "network_delay")]
    [string]$FaultType = "cpu_stress",
    [string]$Service = "paymentservice",
    [string]$Namespace = "online-boutique",
    [string]$ChaosNamespace = "chaos-testing",
    [string]$Duration = "2m",
    [int]$CpuLoad = 80,
    [int]$Workers = 1,
    [string]$MemorySize = "128MB",
    [string]$Latency = "100ms",
    [string]$Jitter = "10ms"
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")
$generatedDir = Join-Path $projectRoot "aiops_agent\chaos\generated"
if (-not (Test-Path -LiteralPath $generatedDir)) {
    New-Item -ItemType Directory -Path $generatedDir | Out-Null
}

switch ($FaultType) {
    "cpu_stress" {
        $kind = "StressChaos"
        $resource = "stresschaos"
        $chaosName = "$Service-cpu-stress"
        $manifest = Join-Path $generatedDir "$($Service)_cpu_stress_runtime.yaml"
        $yaml = @"
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: $chaosName
  namespace: $ChaosNamespace
spec:
  mode: one
  selector:
    namespaces:
      - $Namespace
    labelSelectors:
      app: $Service
  stressors:
    cpu:
      workers: $Workers
      load: $CpuLoad
  duration: "$Duration"
"@
    }
    "memory_stress" {
        $kind = "StressChaos"
        $resource = "stresschaos"
        $chaosName = "$Service-memory-stress"
        $manifest = Join-Path $generatedDir "$($Service)_memory_stress_runtime.yaml"
        $yaml = @"
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: $chaosName
  namespace: $ChaosNamespace
spec:
  mode: one
  selector:
    namespaces:
      - $Namespace
    labelSelectors:
      app: $Service
  stressors:
    memory:
      workers: $Workers
      size: "$MemorySize"
  duration: "$Duration"
"@
    }
    "pod_kill" {
        $kind = "PodChaos"
        $resource = "podchaos"
        $chaosName = "$Service-pod-kill"
        $manifest = Join-Path $generatedDir "$($Service)_pod_kill_runtime.yaml"
        $yaml = @"
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: $chaosName
  namespace: $ChaosNamespace
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - $Namespace
    labelSelectors:
      app: $Service
"@
    }
    "network_delay" {
        $kind = "NetworkChaos"
        $resource = "networkchaos"
        $chaosName = "$Service-network-delay"
        $manifest = Join-Path $generatedDir "$($Service)_network_delay_runtime.yaml"
        $yaml = @"
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: $chaosName
  namespace: $ChaosNamespace
spec:
  action: delay
  mode: one
  selector:
    namespaces:
      - $Namespace
    labelSelectors:
      app: $Service
  delay:
    latency: "$Latency"
    correlation: "0"
    jitter: "$Jitter"
  duration: "$Duration"
"@
    }
}

Set-Content -LiteralPath $manifest -Value $yaml -Encoding UTF8

Write-Host "About to apply ChaosMesh fault."
Write-Host "FaultType: $FaultType"
Write-Host "Kind: $kind"
Write-Host "Resource: $resource"
Write-Host "Service: $Service"
Write-Host "Namespace: $Namespace"
Write-Host "ChaosNamespace: $ChaosNamespace"
Write-Host "Duration: $Duration"
Write-Host "CpuLoad: $CpuLoad"
Write-Host "Workers: $Workers"
Write-Host "MemorySize: $MemorySize"
Write-Host "Latency: $Latency"
Write-Host "Jitter: $Jitter"
Write-Host "Manifest: $manifest"
Write-Host "This script only creates a ChaosMesh experiment object. It does not restart deployments."

kubectl apply -f $manifest
kubectl get $resource -n $ChaosNamespace
kubectl describe $resource $chaosName -n $ChaosNamespace
