$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = "C:\Users\a3838\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $python (Join-Path $PSScriptRoot "online_boutique_ui_test.py")

