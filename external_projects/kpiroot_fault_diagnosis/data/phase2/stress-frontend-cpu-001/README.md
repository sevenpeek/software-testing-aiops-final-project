# Stress Frontend CPU 001

This dataset records a ChaosMesh CPU stress fault injected into Online-Boutique's `frontend` service.

## Timeline

- Baseline start: `2026-06-05T03:14:44.9566104+08:00`
- Fault apply time: `2026-06-05T03:20:10.5531737+08:00`
- Chaos creation time: `2026-06-05T03:20:10+08:00`
- Fault confirmed time: `2026-06-05T03:20:10.8167056+08:00`
- Estimated fault end: `2026-06-05T03:25:10+08:00`
- Recovery confirmed time: `2026-06-05T03:31:06.2251035+08:00`
- Export window: `2026-06-05T03:14:44+08:00` to `2026-06-05T03:31:30+08:00`

## Validation

The experiment is normal. During the fault window, `cpu__frontend` increased from a baseline average of about `0.016` to a fault-window average of about `0.170`, with a maximum of about `0.200`. This makes `frontend` the strongest CPU signal in the dataset.

The frontend probe duration also increased during the fault window, with a maximum of about `0.225s`, while `alarm_frontend_probe_success` remained `1`. All Online-Boutique Pods recovered to `Running`, and no ChaosMesh objects remained after cleanup.

`processed/kpi_matrix.csv` contains 68 rows and 60 columns.

## Screenshot Index

- `screenshots/01_terminal_frontend_stresschaos_created.png`
- `screenshots/02_grafana_frontend_cpu_spike_overview.png`
- `screenshots/03_grafana_frontend_probe_duration_success.png`
- `screenshots/04_terminal_recovery_cleanup_no_chaos.png`

## Data Files

- `prometheus_raw/*.csv`: raw Prometheus query_range outputs.
- `processed/kpi_matrix.csv`: wide KPI matrix for later algorithm reproduction.
- `processed/series_labels.json`: label metadata for each processed KPI column.
