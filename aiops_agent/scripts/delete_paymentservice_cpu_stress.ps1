param(
    [string]$Service = "paymentservice",
    [string]$ChaosNamespace = "chaos-testing"
)

$ErrorActionPreference = "Stop"

Write-Host "Deleting paymentservice-cpu-stress through the generic fault cleanup script."
& (Join-Path $PSScriptRoot "delete_fault.ps1") `
    -FaultType cpu_stress `
    -Service $Service `
    -ChaosNamespace $ChaosNamespace
