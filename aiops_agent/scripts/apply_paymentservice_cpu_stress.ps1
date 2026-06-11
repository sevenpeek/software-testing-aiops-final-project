param(
    [string]$Service = "paymentservice",
    [string]$Namespace = "online-boutique",
    [string]$ChaosNamespace = "chaos-testing",
    [string]$Duration = "2m",
    [int]$Load = 80,
    [int]$Workers = 1
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "apply_fault.ps1") `
    -FaultType cpu_stress `
    -Service $Service `
    -Namespace $Namespace `
    -ChaosNamespace $ChaosNamespace `
    -Duration $Duration `
    -CpuLoad $Load `
    -Workers $Workers
