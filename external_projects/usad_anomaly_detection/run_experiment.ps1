$Python = "python"

if ($args.Count -ge 1) {
  $Python = $args[0]
}

New-Item -ItemType Directory -Force -Path "data" | Out-Null
New-Item -ItemType Directory -Force -Path "outputs" | Out-Null

& $Python "src\generate_sample_data.py" --out "data\sample_kpi_metrics.csv"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python "src\run_usad.py" --input "data\sample_kpi_metrics.csv" --out "outputs"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python "src\build_report.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Experiment completed. Outputs are in outputs/ and report/."
