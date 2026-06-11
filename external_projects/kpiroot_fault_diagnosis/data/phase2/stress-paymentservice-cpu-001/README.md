# stress-paymentservice-cpu-001

This directory contains the Phase 2 data and evidence for the first injected
fault experiment.

## Fault

- Tool: ChaosMesh
- Kind: StressChaos
- Target service: `paymentservice`
- Fault: CPU stress, 1 worker, 80% load
- Duration: 5 minutes
- Expected root-cause KPI for KPIRoot: `cpu__paymentservice`

## Time Window

- Export start: `2026-06-05T01:50:00+08:00`
- Fault applied: `2026-06-05T02:05:50.9359678+08:00`
- Fault start from ChaosMesh record: `2026-06-05T02:06:14+08:00`
- Fault confirmed: `2026-06-05T02:06:23.7236879+08:00`
- Estimated fault end: `2026-06-05T02:11:14+08:00`
- Recovery confirmed: `2026-06-05T02:18:12.2415593+08:00`
- Export end: `2026-06-05T02:18:30+08:00`

## Data Check

Processed matrix:

```text
processed/kpi_matrix.csv
```

Shape:

```text
rows: 115
columns: 62
```

Key observations:

- `cpu__paymentservice` baseline average: about `0.00064`
- `cpu__paymentservice` fault-window average: about `0.16999`
- `cpu__paymentservice` fault-window max: about `0.20016`
- `alarm_frontend_probe_success` stayed at `1.0`
- `running__paymentservice` stayed at `1.0`

This means the injected CPU stress was successfully reflected in Prometheus
metrics, while the service stayed reachable.

## Screenshots

Screenshots were moved from `FinalProject/screenshot` into:

```text
screenshots/
```

Ordered list:

1. `01_prometheus_targets_all_up.jpeg`
2. `02_prometheus_frontend_probe_success.png`
3. `03_prometheus_online_boutique_cpu_query.png`
4. `04_grafana_baseline_dashboard_overview.png`
5. `05_grafana_baseline_probe_and_status.png`
6. `06_chaosmesh_dashboard_no_experiments.png`
7. `07_terminal_cluster_status_no_active_chaos.png`
8. `08_terminal_stresschaos_created_describe_top.png`
9. `09_terminal_stresschaos_injected_events.png`
10. `10_grafana_fault_paymentservice_cpu_spike.png`
11. `11_grafana_fault_probe_and_status.png`
12. `12_terminal_recovery_pods_running_cleanup.png`
