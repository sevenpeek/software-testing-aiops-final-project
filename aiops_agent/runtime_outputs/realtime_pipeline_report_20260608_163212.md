# Realtime AIOps Pipeline Report

Generated at: 2026-06-08T16:32:16
dry_run: False
execute_mode: execute_kpiroot_only

## Realtime data collection

- duration_minutes: 5
- step_seconds: 15
- prometheus_csv: `D:\software-test-final-aiops\aiops_agent\runtime_data\prometheus_realtime_20260608_163212.csv`
- prometheus_meta: `D:\software-test-final-aiops\aiops_agent\runtime_data\prometheus_realtime_20260608_163212.meta.json`
- usad_input_csv: `D:\software-test-final-aiops\aiops_agent\runtime_data\usad_input_20260608_163215.csv`
- kpiroot_input_csv: `D:\software-test-final-aiops\aiops_agent\runtime_data\kpiroot_input_20260608_163215.csv`
- kpiroot_phase2_dir: `D:\software-test-final-aiops\aiops_agent\runtime_data\kpiroot_phase2`

## USAD execution

- executed: False
- success: False
- output_dir: `D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_163215`
- command:

```text
D:\Users\27403\anaconda3\envs\aiops\python.exe D:\software-test-final-aiops\external_projects\usad_anomaly_detection\src\run_usad.py --input D:\software-test-final-aiops\aiops_agent\runtime_data\usad_input_20260608_163215.csv --out D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_163215 --epochs 1 --window 5 --train-ratio 0.7 --title Realtime USAD anomaly score on Online Boutique metrics
```

- expected_outputs:
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_163215\anomaly_scores.csv`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_163215\metrics_summary.txt`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_163215\anomaly_score.png`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\usad_realtime_20260608_163215\reconstruction_error.png`

- stdout_tail:

```text

```

- stderr_tail:

```text

```

- warnings:
  - USAD realtime execution skipped because dry_run=True or execute=False.

## KPIRoot execution

- executed: True
- success: False
- output_dir: `D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_163215`
- command:

```text
D:\Users\27403\anaconda3\envs\aiops\python.exe -m kpiroot.cli --phase2-dir D:\software-test-final-aiops\aiops_agent\runtime_data\kpiroot_phase2 --output-dir D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_163215 --report D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_163215\PHASE4_KPIROOT_REALTIME.md --scenario realtime-paymentservice-cpu --alarm paymentservice --paa-size 16
```

- expected_outputs:
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_163215\summary.csv`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_163215\ablation_summary.csv`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_163215\realtime-paymentservice-cpu\ranking.csv`
  - `D:\software-test-final-aiops\aiops_agent\runtime_outputs\kpiroot_realtime_20260608_163215\realtime-paymentservice-cpu\summary.json`

- stdout_tail:

```text

```

- stderr_tail:

```text
Traceback (most recent call last):
  File "D:\Users\27403\anaconda3\envs\aiops\lib\runpy.py", line 187, in _run_module_as_main
    mod_name, mod_spec, code = _get_module_details(mod_name, _Error)
  File "D:\Users\27403\anaconda3\envs\aiops\lib\runpy.py", line 110, in _get_module_details
    __import__(pkg_name)
  File "D:\software-test-final-aiops\external_projects\kpiroot_fault_diagnosis\src\kpiroot\__init__.py", line 3, in <module>
    from .algorithm import KPIRootConfig, run_kpiroot
  File "D:\software-test-final-aiops\external_projects\kpiroot_fault_diagnosis\src\kpiroot\algorithm.py", line 9, in <module>
    from scipy.stats import norm
ModuleNotFoundError: No module named 'scipy'
```

- warnings:
  - KPIRoot execution finished but expected output files were not all found or return code was non-zero.

## Agent diagnosis

- runtime_config: `D:\software-test-final-aiops\aiops_agent\runtime_outputs\runtime_config.json`
- diagnosis_report: `D:\software-test-final-aiops\aiops_agent\outputs\diagnosis_report.md`
- recovery_decision: manual_review
- risk_level: medium
- Prometheus service_cpu_rate: None

## Safety notes

- external_projects 原始输出未被覆盖。
- 所有外部算法 runtime 输出均指向 aiops_agent/runtime_outputs。
- 恢复动作保持 dry-run。
- 没有执行 Kubernetes 修改命令。

## Warnings And Limits

- USAD input is canonical CSV compatible with run_usad.py.
- KPIRoot input is adapted to phase2/<scenario>/processed/kpi_matrix.csv with generated metadata.yaml; scenario semantics should be confirmed by the KPIRoot project owners.
- USAD realtime execution skipped because dry_run=True or execute=False.
- KPIRoot execution finished but expected output files were not all found or return code was non-zero.
- If runtime output paths are None, aiops_agent continues with existing external project outputs.
- run_agent.py uses config.json paths unless a temporary runtime config is generated by realtime_pipeline_agent.

## Raw command plans

```json
{
  "usad": [
    "D:\\Users\\27403\\anaconda3\\envs\\aiops\\python.exe",
    "D:\\software-test-final-aiops\\external_projects\\usad_anomaly_detection\\src\\run_usad.py",
    "--input",
    "D:\\software-test-final-aiops\\aiops_agent\\runtime_data\\usad_input_20260608_163215.csv",
    "--out",
    "D:\\software-test-final-aiops\\aiops_agent\\runtime_outputs\\usad_realtime_20260608_163215",
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
    "D:\\software-test-final-aiops\\aiops_agent\\runtime_outputs\\kpiroot_realtime_20260608_163215",
    "--report",
    "D:\\software-test-final-aiops\\aiops_agent\\runtime_outputs\\kpiroot_realtime_20260608_163215\\PHASE4_KPIROOT_REALTIME.md",
    "--scenario",
    "realtime-paymentservice-cpu",
    "--alarm",
    "paymentservice",
    "--paa-size",
    "16"
  ]
}
```