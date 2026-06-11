# 阶段二：监控与数据采集说明

本文件概述阶段二最终形成的监控架构、采集指标和数据格式。具体执行时间线与故障数据验证见 [阶段二执行记录](PHASE2_EXECUTION_LOG.md)。

## 阶段目标

阶段二的目标不是单纯打开 Prometheus 和 Grafana，而是为后续论文复现构造可用的时序数据集。完成后的系统需要满足：

- Prometheus 能采集 Kubernetes 集群与 Online-Boutique 工作负载指标。
- Grafana 能以 Dashboard 形式展示关键服务状态。
- ChaosMesh 能向 Online-Boutique 注入可控故障。
- 每组故障均保留 baseline、fault、recovery 三段时间窗口。
- Prometheus 数据能导出为阶段四 KPIRoot 可读取的 KPI 矩阵。

## 与 KPIRoot 的关系

ISSRE24-KPIRoot 需要一条告警 KPI 和多条候选底层 KPI，并根据相似度与时序因果关系定位根因 KPI。本项目将论文中的主机集群/VM 场景映射到 Online-Boutique 微服务场景：

| KPIRoot 概念 | 阶段二采集对象 |
| --- | --- |
| Alarm KPI | 聚合 CPU、聚合内存、前端探针耗时、前端探针成功率 |
| Candidate KPI | 各服务 CPU、内存、文件系统读写、重启次数、Pod Running 状态 |
| Ground truth | ChaosMesh 故障注入的目标服务和故障类型 |

因此，阶段二数据目录中的 `metadata.yaml` 记录了目标服务、故障类型、注入时间窗口和预期根因；`processed/kpi_matrix.csv` 则作为阶段四算法输入。

## 监控组件

阶段二复用了此前实验中的 `monitoring` 命名空间，并补充 Online-Boutique 相关配置。

| 组件 | 作用 |
| --- | --- |
| Prometheus | 采集 Kubernetes、cadvisor、kube-state-metrics、node-exporter 与 Blackbox 指标 |
| Grafana | 展示 Online-Boutique 运维 Dashboard |
| Blackbox Exporter | 从集群内探测 Online-Boutique frontend 可用性与响应耗时 |
| ChaosMesh | 注入 CPU Stress、Pod Kill 等故障 |

Blackbox Exporter 配置文件：

```text
monitoring/blackbox-exporter.yaml
```

Grafana Dashboard 配置文件：

```text
grafana/online-boutique-maintenance-dashboard.json
```

## 关键 PromQL

数据导出脚本围绕以下指标构造 KPI 矩阵：

```promql
sum by (pod) (
  rate(container_cpu_usage_seconds_total{namespace="online-boutique"}[1m])
)
```

```promql
sum by (pod) (
  container_memory_working_set_bytes{namespace="online-boutique"}
)
```

```promql
sum by (pod, container) (
  kube_pod_container_status_restarts_total{namespace="online-boutique"}
)
```

```promql
kube_pod_status_phase{namespace="online-boutique", phase="Running"}
```

```promql
probe_success{job="online-boutique-frontend-blackbox"}
```

```promql
probe_duration_seconds{job="online-boutique-frontend-blackbox"}
```

文件系统读写指标也被保留，用于提供更完整的候选 KPI 集合：

```promql
sum by (pod) (
  rate(container_fs_reads_bytes_total{namespace="online-boutique"}[1m])
)
```

```promql
sum by (pod) (
  rate(container_fs_writes_bytes_total{namespace="online-boutique"}[1m])
)
```

## 故障场景设计

阶段二最终采集了三组故障数据：

| 场景 | ChaosMesh 类型 | 目标服务 | 采集目的 |
| --- | --- | --- | --- |
| `stress-paymentservice-cpu-001` | `StressChaos` | `paymentservice` | 验证 CPU 异常能否定位到 paymentservice |
| `pod-kill-paymentservice-001` | `PodChaos` | `paymentservice` | 验证 Pod 替换类故障在服务级矩阵中的表现 |
| `stress-frontend-cpu-001` | `StressChaos` | `frontend` | 验证前端 CPU 异常与服务质量指标变化的关系 |

每组故障均包含正常基线、故障注入和恢复观察窗口。CPU Stress 场景的指标变化更明显，是阶段二和阶段四分析中的主要证据；Pod Kill 场景保留为补充案例。

## 数据目录格式

阶段二数据统一存放在：

```text
data/phase2/<scenario_id>/
```

每组数据的结构如下：

```text
metadata.yaml
prometheus_raw/
processed/
screenshots/
```

主要文件含义：

| 文件 | 作用 |
| --- | --- |
| `metadata.yaml` | 记录故障类型、目标服务、时间窗口、预期根因 |
| `prometheus_raw/*.csv` | Prometheus `query_range` 原始导出结果 |
| `processed/kpi_matrix.csv` | 按时间对齐后的宽表 KPI 矩阵 |
| `processed/series_labels.json` | KPI 列与原始 Prometheus label 的对应关系 |
| `screenshots/` | 实验过程截图证据 |

`kpi_matrix.csv` 的第一列为时间戳，其余列为阶段四使用的 KPI 序列。典型列名包括：

```text
cpu__paymentservice
memory__paymentservice
running__paymentservice
alarm_frontend_probe_duration
alarm_frontend_probe_success
synthetic_total_cpu
synthetic_total_memory
```

其中 `synthetic_total_cpu`、`synthetic_total_memory` 等聚合告警 KPI 在阶段四读取数据时构造，用于模拟 KPIRoot 论文中的系统级告警指标。

## 导出脚本

数据导出脚本：

```text
scripts/export-prometheus-range.py
```

典型导出命令格式：

```powershell
.\FinalProject\.conda\python.exe .\FinalProject\scripts\export-prometheus-range.py `
  --prometheus-url http://127.0.0.1:9090 `
  --start "2026-06-05THH:mm:ss+08:00" `
  --end "2026-06-05THH:mm:ss+08:00" `
  --step 15 `
  --output .\FinalProject\data\phase2\<scenario_id>
```

实际执行时，`--start` 与 `--end` 使用实验记录中的真实时间。阶段二已完成的数据集中，这些时间已写入各自的 `metadata.yaml` 和执行记录。

## 阶段产物

阶段二保留的关键产物：

- 监控配置：`monitoring/blackbox-exporter.yaml`
- Grafana Dashboard：`grafana/online-boutique-maintenance-dashboard.json`
- ChaosMesh 清单：`chaos/*.yaml`
- 数据导出脚本：`scripts/export-prometheus-range.py`
- 故障数据：`data/phase2/stress-paymentservice-cpu-001/`
- 故障数据：`data/phase2/pod-kill-paymentservice-001/`
- 故障数据：`data/phase2/stress-frontend-cpu-001/`

这些产物共同构成阶段四 KPIRoot 复现的数据基础。
