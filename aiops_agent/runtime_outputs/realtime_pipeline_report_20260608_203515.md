# Realtime AIOps Pipeline Report

Generated at: 2026-06-08T20:35:22
dry_run: False
execute_mode: execute_usad_kpiroot
data_source_mode: realtime_runtime

## Realtime data collection

- duration_minutes: 5
- step_seconds: 15
- prometheus_csv: `D:\software-test-final-aiops\aiops_agent\runtime_data\prometheus_realtime_20260608_203515.csv`
- prometheus_meta: `D:\software-test-final-aiops\aiops_agent\runtime_data\prometheus_realtime_20260608_203515.meta.json`
- usad_input_csv: `D:\software-test-final-aiops\aiops_agent\runtime_data\usad_input_20260608_203518.csv`
- kpiroot_input_csv: `D:\software-test-final-aiops\aiops_agent\runtime_data\kpiroot_input_20260608_203518.csv`
- kpiroot_phase2_dir: `D:\software-test-final-aiops\aiops_agent\runtime_data\kpiroot_phase2`

## USAD execution

- executed: True
- success: True
- output_dir: `D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_203518`
- command:

```text
D:\Users\27403\anaconda3\envs\aiops\python.exe D:\software-test-final-aiops\external_projects\usad_anomaly_detection\src\run_usad.py --input D:\software-test-final-aiops\aiops_agent\runtime_data\usad_input_20260608_203518.csv --out D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_203518 --epochs 1 --window 5 --train-ratio 0.7 --title Realtime USAD anomaly score on Online Boutique metrics
```

- expected_outputs:
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_203518\anomaly_scores.csv`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_203518\metrics_summary.txt`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_203518\anomaly_score.png`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_203518\reconstruction_error.png`

- stdout_tail:

```text
USAD reproduction summary
input: D:\software-test-final-aiops\aiops_agent\runtime_data\usad_input_20260608_203518.csv
rows: 21
metrics: 22
window_size: 5
train_windows: 17
epochs: 1
final_train_loss: 2.554675
threshold: 9.949159
precision: 0.0000
recall: 0.0000
f1: 0.0000
tp/fp/fn/tn: 0/1/0/16

top reconstruction-error metrics:
- currencyservice__memory: 2.592688
- shippingservice__memory: 1.450377
- redis-cart__memory: 1.446284
- adservice__memory: 1.355240
- productcatalogservice__memory: 1.294511
```

- stderr_tail:

```text

```

- warnings:

## KPIRoot execution

- executed: True
- success: True
- output_dir: `D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_203519`
- command:

```text
D:\Users\27403\anaconda3\envs\aiops\python.exe -m kpiroot.cli --phase2-dir D:\software-test-final-aiops\aiops_agent\runtime_data\kpiroot_phase2 --output-dir D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_203519 --report D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_203519\PHASE4_KPIROOT_REALTIME.md --scenario realtime-paymentservice-cpu --alarm paymentservice --paa-size 16
```

- expected_outputs:
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_203519\summary.csv`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_203519\ablation_summary.csv`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_203519\realtime-paymentservice-cpu\ranking.csv`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_203519\realtime-paymentservice-cpu\summary.json`

- stdout_tail:

```text
                scenario_id   alarm_column expected_service                top1  expected_service_rank  hit_at_1  hit_at_3  hit_at_5
realtime-paymentservice-cpu paymentservice   paymentservice cpu__paymentservice                      1      True      True      True

                scenario_id           method                top1  expected_service_rank  hit_at_1  hit_at_3  hit_at_5
realtime-paymentservice-cpu  similarity_only cpu__paymentservice                      1      True      True      True
realtime-paymentservice-cpu   causality_only  memory__redis-cart                     15     False     False     False
realtime-paymentservice-cpu kpiroot_combined cpu__paymentservice                      1      True      True      True
```

- stderr_tail:

```text

```

- warnings:

## Agent diagnosis

- runtime_config: `D:\software-test-final-aiops\aiops_agent\runtime_outputs\runtime_config.json`
- diagnosis_report: `D:\software-test-final-aiops\aiops_agent\outputs\diagnosis_report.md`
- recovery_decision: manual_review
- risk_level: medium
- Prometheus service_cpu_rate: None
- data_source_mode: realtime_runtime

## LLM Summary

- llm_enabled: False
- llm_executed: False
- llm_output_path: `None`
- llm_mode: disabled
- llm_warning: N/A

## Safety notes

- external_projects 原始输出未被覆盖。
- 所有外部算法 runtime 输出均指向 aiops_agent/runtime_outputs。
- 恢复动作保持 dry-run。
- 没有执行 Kubernetes 修改命令。

## Warnings And Limits

- USAD input is canonical CSV compatible with run_usad.py.
- KPIRoot input is adapted to phase2/<scenario>/processed/kpi_matrix.csv with generated metadata.yaml; scenario semantics should be confirmed by the KPIRoot project owners.
- If runtime output paths are None, aiops_agent continues with existing external project outputs.
- run_agent.py uses config.json paths unless a temporary runtime config is generated by realtime_pipeline_agent.

## Raw command plans

```json
{
  "usad": [
    "D:\\Users\\27403\\anaconda3\\envs\\aiops\\python.exe",
    "D:\\software-test-final-aiops\\external_projects\\usad_anomaly_detection\\src\\run_usad.py",
    "--input",
    "D:\\software-test-final-aiops\\aiops_agent\\runtime_data\\usad_input_20260608_203518.csv",
    "--out",
    "D:\\software-test-final-aiops\\aiops_agent\\runtime_outputs\\usad_realtime_20260608_203518",
    "--epochs",
    "1",
    "--window",
    "5",
    "--train-ratio",
    "0.7",
    "--title",
    "Realtime USAD anomaly score on Online Boutique metrics"
  ],
  "kpiroot": [
    "D:\\Users\\27403\\anaconda3\\envs\\aiops\\python.exe",
    "-m",
    "kpiroot.cli",
    "--phase2-dir",
    "D:\\software-test-final-aiops\\aiops_agent\\runtime_data\\kpiroot_phase2",
    "--output-dir",
    "D:\\software-test-final-aiops\\aiops_agent\\runtime_outputs\\kpiroot_realtime_20260608_203519",
    "--report",
    "D:\\software-test-final-aiops\\aiops_agent\\runtime_outputs\\kpiroot_realtime_20260608_203519\\PHASE4_KPIROOT_REALTIME.md",
    "--scenario",
    "realtime-paymentservice-cpu",
    "--alarm",
    "paymentservice",
    "--paa-size",
    "16"
  ]
}
```