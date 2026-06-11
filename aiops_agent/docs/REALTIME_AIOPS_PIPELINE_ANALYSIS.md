# Realtime AIOps Pipeline Analysis

本文档记录对 `external_projects/usad_anomaly_detection` 和 `external_projects/kpiroot_fault_diagnosis` 的只读调查结果，并说明 aiops_agent 新增端到端实时流水线的安全边界。

## 1. USAD 项目调查

项目路径：

```text
external_projects/usad_anomaly_detection
```

主要文件：

- README：`external_projects/usad_anomaly_detection/README.md`
- requirements：`external_projects/usad_anomaly_detection/requirements.txt`
- 核心入口：`external_projects/usad_anomaly_detection/src/run_usad.py`
- USAD 实现：`external_projects/usad_anomaly_detection/src/usad_numpy.py`
- 示例输入：`external_projects/usad_anomaly_detection/data/sample_kpi_metrics.csv`
- Online Boutique 已有输入：
  - `data/online_boutique_real_metrics.csv`
  - `data/online_boutique_chaosmesh_metrics.csv`
- aiops_agent 当前读取的已有输出：
  - `outputs_online_boutique_real/anomaly_scores.csv`
  - `outputs_online_boutique_real/metrics_summary.txt`
  - `outputs_online_boutique_chaosmesh/anomaly_scores.csv`
  - `outputs_online_boutique_chaosmesh/metrics_summary.txt`

### USAD 入口参数

`src/run_usad.py` 使用 argparse，支持：

```text
--input <csv>
--out <output_dir>
--window
--epochs
--train-ratio
--title
```

因此 USAD 支持指定新数据集路径和输出目录。只要将 `--out` 指向 `aiops_agent/runtime_outputs/usad_realtime_*`，就可以避免覆盖同学已有输出。

### USAD 输入格式

USAD 读取 CSV，特殊列包括：

- `timestamp`
- `label`
- `sample_index`
- `fault_active`

除这些元数据列以外的列都会作为指标列。若没有 `label` 列，则代码默认全部为 0。

### USAD 运行性质

`run_usad.py` 是训练 + 推理一体流程。它会：

1. 读取输入 CSV。
2. 按 `train-ratio` 划分前段数据作为训练窗口。
3. 训练 NumPy 版 USAD。
4. 输出异常分数、阈值、预测标签、summary 和图片。

这意味着实时执行可能有一定耗时；本项目默认 dry-run，不自动重跑。

### USAD 输出覆盖风险

如果使用默认 `--out outputs` 或原有输出目录，会覆盖已有结果。因此实时流水线只允许将输出写入：

```text
aiops_agent/runtime_outputs/usad_realtime_YYYYMMDD_HHMMSS
```

## 2. KPIRoot 项目调查

项目路径：

```text
external_projects/kpiroot_fault_diagnosis
```

主要文件：

- README：`external_projects/kpiroot_fault_diagnosis/README.md`
- requirements：`external_projects/kpiroot_fault_diagnosis/requirements.txt`
- PowerShell 入口：`scripts/run-phase4-kpiroot.ps1`
- Python CLI 入口：`src/kpiroot/cli.py`
- 数据读取：`src/kpiroot/data.py`
- 当前 aiops_agent 读取的已有输出：
  - `data/phase4/kpiroot/summary.csv`
  - `data/phase4/kpiroot/ablation_summary.csv`
  - `data/phase4/kpiroot/<scenario>/ranking.csv`
  - `data/phase4/kpiroot/<scenario>/summary.json`

### KPIRoot 入口参数

`src/kpiroot/cli.py` 支持：

```text
--phase2-dir <phase2_data_dir>
--output-dir <output_dir>
--report <report_path>
--scenario
--alarm
--paa-size
--lambda-weight
--alphabet-size
--granger-lag
```

因此 KPIRoot 支持指定新的输入目录和输出目录。相比 PowerShell 脚本，直接调用 Python CLI 更适合实时流水线，因为可以将 `--output-dir` 指向 `aiops_agent/runtime_outputs/kpiroot_realtime_*`。

### KPIRoot 输入格式

KPIRoot 不是直接读取单个 CSV，而是读取 phase2 场景目录：

```text
phase2/<scenario>/processed/kpi_matrix.csv
phase2/<scenario>/metadata.yaml
```

`kpi_matrix.csv` 需要包含：

- `timestamp` 列，通常为 epoch 秒。
- 候选 KPI 列，例如 `cpu__paymentservice`、`memory__frontend`。

`metadata.yaml` 用于说明故障场景、期望根因和时间窗口。KPIRoot 会基于 metadata 选择异常窗口；如果信息不足，会退回趋势检测逻辑。

### KPIRoot 与 USAD 的关系

当前 KPIRoot 项目不直接依赖 USAD 输出。它读取独立的 KPI 矩阵和 metadata，根据系统级告警 KPI 与候选 KPI 进行排序。

实时流水线中，USAD 与 KPIRoot 共享 Prometheus 采集得到的同一批实时 KPI 数据，但 KPIRoot 不需要读取 USAD 的 `anomaly_scores.csv`。

### KPIRoot 输出覆盖风险

`scripts/run-phase4-kpiroot.ps1` 固定输出到：

```text
external_projects/kpiroot_fault_diagnosis/data/phase4/kpiroot
```

直接运行该脚本会覆盖已有阶段四输出。因此实时流水线默认不调用该脚本，而是规划调用 Python CLI，并将输出写入：

```text
aiops_agent/runtime_outputs/kpiroot_realtime_YYYYMMDD_HHMMSS
```

## 3. 实时流水线新增实现

新增模块：

- `aiops_agent/tools/realtime_prometheus_collector.py`
- `aiops_agent/tools/realtime_dataset_adapter.py`
- `aiops_agent/tools/external_pipeline_tool.py`
- `aiops_agent/realtime_pipeline_agent.py`

流程：

1. 通过 `kubectl exec` 访问 Prometheus 的 `query_range` API。
2. 采集 Online Boutique 最近 N 分钟服务级 CPU 和 Memory。
3. 输出统一 CSV：`prometheus_realtime_YYYYMMDD_HHMMSS.csv`。
4. 生成 USAD 输入：`usad_input_YYYYMMDD_HHMMSS.csv`。
5. 生成 KPIRoot 输入：`kpiroot_input_YYYYMMDD_HHMMSS.csv`，并适配为 `kpiroot_phase2/<scenario>/processed/kpi_matrix.csv`。
6. 默认 dry-run，只输出将要执行的 USAD/KPIRoot 命令。
7. 如果显式 `--execute-external` 且未指定 `--dry-run`，才尝试运行外部算法。
8. 运行 aiops_agent 诊断并生成实时流水线报告。

## 4. dry-run 与 execute-external

dry-run 模式：

- 采集 Prometheus 实时数据。
- 构建 USAD/KPIRoot 输入。
- 不运行外部 USAD/KPIRoot。
- 使用当前已有 external outputs 或 runtime outputs 生成诊断报告。
- 生成 `realtime_pipeline_report_*.md`。

execute-external 模式：

- 需要显式添加 `--execute-external`。
- 会尝试调用 USAD `run_usad.py`。
- 会尝试调用 KPIRoot Python CLI。
- 输出目录仍位于 `aiops_agent/runtime_outputs`。
- 不覆盖 external_projects 原始输出。

分阶段低成本执行模式：

- `--execute-usad-only`：只运行 USAD，不运行 KPIRoot。
- `--execute-kpiroot-only`：只运行 KPIRoot，不运行 USAD。
- `--execute-external`：运行 USAD + KPIRoot。

USAD 低成本参数：

- `--usad-epochs 1`
- `--usad-window 5`
- `--usad-train-ratio 0.7`

KPIRoot runtime 参数：

- `--kpiroot-scenario realtime-paymentservice-cpu`
- `--kpiroot-alarm paymentservice`

所有外部运行输出都写入 `aiops_agent/runtime_outputs`，不覆盖 `external_projects` 原始输出。

## 5. 当前仍需组员确认的部分

- USAD 实时输入是否需要更多业务指标，例如 frontend latency、status code、probe success，而不仅是 container CPU / memory。
- USAD 在仅 5 分钟数据上训练 + 推理是否稳定，是否需要已有模型推理模式。
- KPIRoot 的 realtime metadata 中故障窗口如何精确定义。
- KPIRoot 对短窗口实时数据的 PAA 参数是否需要重新调优。
- 如果要真正做到在线推理，是否应将 USAD/KPIRoot 封装为长期运行服务，而不是每次调用脚本。

## 6. 安全结论

当前实现可以安全 dry-run：

- 不删除 external_projects 文件。
- 不覆盖 external_projects 输出。
- 不执行 Kubernetes 修改命令。
- 不执行真实恢复命令。
- 不写入 API Key。

如果需要启用 execute-external，建议先由 USAD/KPIRoot 项目负责人确认实时输入格式和运行耗时，再在本机演示环境中手动开启。
# 多类型故障扩展分析补充

实时流水线现在不再只面向单一 CPU 压力实验，而是预留了四类故障上下文：

- `cpu_stress`：已完整验证。Prometheus `service_cpu_rate` 能在故障注入期间捕获升高，USAD/KPIRoot 与 Agent 恢复建议的演示链路最完整。
- `memory_stress`：实验性。需要关注 `service_memory_working_set_mib`、Pod OOM/Event、容器 memory limit。默认注入参数使用 `128MB`，避免本地集群压力过大。
- `pod_kill`：实验性。主要证据来自 Kubernetes Pod phase、ready、restart count、Deployment available 和 Event。Prometheus 中如 kube-state-metrics 不可用，则不要强依赖重启次数指标。
- `network_delay`：待扩展。当前 Prometheus 查询尚未包含应用层 latency/error rate，因此只能结合基础指标、Event 和日志做 manual review。后续需要补充请求延迟、错误率和调用链指标。

当前完整验证场景仍是 `paymentservice` CPU 压力。其他故障类型已经接入 Dashboard、ChaosMesh manifest 生成、Kubernetes/Prometheus 证据字段和 recovery decision 规则，但 USAD/KPIRoot 的实时输入窗口、metadata 和算法解释仍需与组员进一步确认。
# 端到端实时 AIOps 主流程补充

当前前端主流程已经切换为端到端实时 AIOps：故障注入后，Prometheus 采集当前实时指标，生成 USAD/KPIRoot runtime 输入，真实运行 USAD/KPIRoot，再由 aiops_agent 读取本次 runtime 输出生成诊断和 dry-run 恢复建议。

`realtime_pipeline_agent.py` 的 pipeline report 增加 `data_source_mode`：

- `realtime_runtime`：本次 runtime USAD/KPIRoot 输出可用，诊断基于实时算法结果。
- `offline_fallback`：本次执行未覆盖完整 runtime 输出，已回退到已有输出或兼容路径。
- `dry_run_plan_only`：只采集数据和规划命令，不运行 external_projects。

正式演示推荐 `execute USAD + KPIRoot`，但默认仍保持 dry-run，避免误运行外部算法。
