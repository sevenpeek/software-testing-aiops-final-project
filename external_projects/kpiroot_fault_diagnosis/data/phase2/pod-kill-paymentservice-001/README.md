# Pod Kill Paymentservice 001

This dataset records a ChaosMesh PodKill fault injected into Online-Boutique's `paymentservice`.

## Timeline

- Baseline start: `2026-06-05T02:45:55.5019669+08:00`
- Fault apply time: `2026-06-05T02:51:15.6821586+08:00`
- Chaos creation time: `2026-06-05T02:51:17+08:00`
- Fault confirmed time: `2026-06-05T02:51:25.1436113+08:00`
- Recovery confirmed time: `2026-06-05T02:59:47.6511894+08:00`
- Export window: `2026-06-05T02:45:55+08:00` to `2026-06-05T03:02:30+08:00`

## Validation

The experiment is normal. The original `paymentservice-85698c8c59-sss44` Pod disappeared after the PodKill, and the replacement `paymentservice-85698c8c59-5sx8h` Pod became Running. The frontend probe success stayed at `1`, so the frontend remained reachable during the experiment.

`processed/kpi_matrix.csv` contains 67 rows and 62 columns. The raw Prometheus files retain exact Pod names, while the processed matrix uses stable service-level names such as `running__paymentservice`, `cpu__paymentservice`, and `memory__paymentservice`.

## Screenshot Index

- `screenshots/01_precheck_all_pods_no_active_chaos.png`
- `screenshots/02_terminal_podkill_created_paymentservice_replaced.png`
- `screenshots/03_grafana_podkill_overview_last30m.png`
- `screenshots/04_grafana_paymentservice_new_pod_series.png`
- `screenshots/05_grafana_paymentservice_old_pod_series.png`
- `screenshots/06_terminal_recovery_cleanup_no_chaos.png`

## Data Files

- `prometheus_raw/*.csv`: raw Prometheus query_range outputs.
- `processed/kpi_matrix.csv`: wide KPI matrix for later algorithm reproduction.
- `processed/series_labels.json`: label metadata for each processed KPI column.
