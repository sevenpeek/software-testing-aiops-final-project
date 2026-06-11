# 阶段二：执行记录

执行日期：2026-06-05

本阶段在阶段一部署的 Online-Boutique 基础上，完成 Prometheus/Grafana 监控接入、Blackbox 前端探针、ChaosMesh 故障注入和 Prometheus 数据导出。导出的 KPI 矩阵作为阶段四 KPIRoot 复现的主要输入。

## 集群与监控状态

实验开始前检查了三个命名空间：

| 命名空间 | 用途 | 状态 |
| --- | --- | --- |
| `online-boutique` | 被测微服务系统 | 12 个业务 Pod 正常运行 |
| `monitoring` | Prometheus、Grafana、kube-state-metrics、node-exporter | 正常运行 |
| `chaos-testing` | ChaosMesh 控制组件 | 正常运行 |

Prometheus 已能采集 Online-Boutique 的容器与 Pod 指标，验证过的主要查询包括：

```promql
container_cpu_usage_seconds_total{namespace="online-boutique"}
container_memory_working_set_bytes{namespace="online-boutique"}
kube_pod_container_status_restarts_total{namespace="online-boutique"}
kube_pod_status_phase{namespace="online-boutique"}
```

## Frontend Blackbox Probe

为获得更接近“系统级告警 KPI”的服务质量指标，阶段二增加了 Blackbox Exporter 对 Online-Boutique 前端的探测。

新增文件：

- `monitoring/blackbox-exporter.yaml`
- `scripts/enable-blackbox-frontend-probe.ps1`

Prometheus 中新增的 scrape job：

```text
online-boutique-frontend-blackbox
```

验证结果：

```text
probe_success{job="online-boutique-frontend-blackbox"} = 1
```

该探针生成的 `probe_success` 和 `probe_duration_seconds` 后续被导出为 `alarm_frontend_probe_success` 与 `alarm_frontend_probe_duration`。

## Grafana Dashboard

阶段二创建了 Online-Boutique 专用 Dashboard：

```text
grafana/online-boutique-maintenance-dashboard.json
```

Dashboard 面板覆盖以下指标：

- Pod CPU 使用率
- Pod 内存工作集
- 容器重启次数
- Pod Running 状态
- 前端探针耗时
- 前端探针成功率
- 文件系统读写速率

实验中曾遇到 Grafana v7.5.5 对新版 `timeseries` panel 支持不兼容的问题，随后将面板类型调整为 legacy `graph`，并将 Prometheus 数据源改为集群内地址：

```text
http://prometheus.monitoring.svc.cluster.local:9090
```

重新导入后，Grafana 能正常通过数据源查询 Online-Boutique 的 12 条 CPU 序列。

## ChaosMesh 故障定义

阶段二准备了可复用的故障注入清单：

- `chaos/stress-paymentservice-cpu.yaml`
- `chaos/pod-kill-paymentservice.yaml`
- `chaos/stress-frontend-cpu.yaml`
- `chaos/network-delay-checkoutservice.yaml`

清单通过如下命令进行客户端侧校验：

```powershell
kubectl apply --dry-run=client -f .\FinalProject\chaos
```

实际采集数据时使用了前三组故障。实验结束后均检查并清理了 `online-boutique` 命名空间中的 ChaosMesh 对象。

## 数据导出方式

Prometheus 数据通过脚本导出：

```text
scripts/export-prometheus-range.py
```

每组数据目录包含：

```text
metadata.yaml
prometheus_raw/*.csv
processed/kpi_matrix.csv
processed/series_labels.json
screenshots/
```

其中 `processed/kpi_matrix.csv` 是阶段四 KPIRoot 复现使用的宽表时序矩阵，`metadata.yaml` 记录故障类型、目标服务、时间窗口和真实根因。

## Baseline 数据

正常状态样本保存在：

```text
data/phase2/baseline-sample/
```

该样本用于验证 Prometheus 查询、导出脚本和矩阵转换流程。处理后的矩阵规模为：

| 数据集 | 行数 | 列数 |
| --- | ---: | ---: |
| `baseline-sample` | 14 | 60 |

## 故障数据集

阶段二最终保留三组故障数据：

| 数据集 | 故障类型 | 目标服务 | 导出窗口 | 矩阵规模 | 阶段四真实根因 |
| --- | --- | --- | --- | --- | --- |
| `stress-paymentservice-cpu-001` | CPU Stress | `paymentservice` | `2026-06-05T01:50:00+08:00` 至 `2026-06-05T02:18:30+08:00` | 115 行 × 62 列 | `cpu__paymentservice` |
| `pod-kill-paymentservice-001` | Pod Kill | `paymentservice` | `2026-06-05T02:45:55+08:00` 至 `2026-06-05T03:02:30+08:00` | 67 行 × 62 列 | `memory__paymentservice` / `paymentservice` 服务 |
| `stress-frontend-cpu-001` | CPU Stress | `frontend` | `2026-06-05T03:14:44+08:00` 至 `2026-06-05T03:31:30+08:00` | 68 行 × 60 列 | `cpu__frontend` |

### `stress-paymentservice-cpu-001`

故障清单：

```powershell
kubectl apply -f .\FinalProject\chaos\stress-paymentservice-cpu.yaml
```

关键时间：

- 故障应用时间：`2026-06-05T02:05:50.9359678+08:00`
- ChaosMesh 记录的故障开始：`2026-06-05T02:06:14+08:00`
- 故障确认时间：`2026-06-05T02:06:23.7236879+08:00`
- 预计故障结束：`2026-06-05T02:11:14+08:00`
- 恢复确认时间：`2026-06-05T02:18:12.2415593+08:00`

数据检查结果：

- `cpu__paymentservice` baseline 平均值约 `0.00064`。
- `cpu__paymentservice` fault-window 平均值约 `0.16999`。
- `cpu__paymentservice` fault-window 最大值约 `0.20016`。
- `alarm_frontend_probe_success` 保持为 `1.0`。
- `running__paymentservice` 保持为 `1.0`。

该组数据中的 CPU 异常清晰，最适合展示 KPIRoot 将系统级 CPU 告警定位到 `paymentservice` CPU 根因的过程。

### `pod-kill-paymentservice-001`

故障清单：

```powershell
kubectl apply -f .\FinalProject\chaos\pod-kill-paymentservice.yaml
```

关键时间：

- Baseline 开始：`2026-06-05T02:45:55.5019669+08:00`
- 故障应用时间：`2026-06-05T02:51:15.6821586+08:00`
- ChaosMesh 创建时间：`2026-06-05T02:51:17+08:00`
- 故障确认时间：`2026-06-05T02:51:25.1436113+08:00`
- 恢复与清理确认：`2026-06-05T02:59:47.6511894+08:00`

验证结果：

- 原 `paymentservice-85698c8c59-sss44` Pod 被替换为 `paymentservice-85698c8c59-5sx8h`。
- Online-Boutique 所有 Pod 恢复到 `Running`。
- 清理后 `online-boutique` 命名空间中无残留 ChaosMesh 对象。
- `alarm_frontend_probe_success` 在导出窗口内保持为 `1`。

该组故障在整体 Grafana 面板中的变化不如 CPU Stress 明显，因为 Kubernetes 会快速拉起替代 Pod，且处理后的服务级矩阵会弱化单个 Pod 身份变化。该数据集保留为阶段四的边界案例。

### `stress-frontend-cpu-001`

故障清单：

```powershell
kubectl apply -f .\FinalProject\chaos\stress-frontend-cpu.yaml
```

关键时间：

- Baseline 开始：`2026-06-05T03:14:44.9566104+08:00`
- 故障应用时间：`2026-06-05T03:20:10.5531737+08:00`
- ChaosMesh 创建时间：`2026-06-05T03:20:10+08:00`
- 故障确认时间：`2026-06-05T03:20:10.8167056+08:00`
- 预计故障结束：`2026-06-05T03:25:10+08:00`
- 恢复与清理确认：`2026-06-05T03:31:06.2251035+08:00`

数据检查结果：

- `cpu__frontend` baseline 平均值约 `0.016`。
- `cpu__frontend` fault-window 平均值约 `0.170`。
- `cpu__frontend` fault-window 最大值约 `0.200`。
- `alarm_frontend_probe_duration` 在故障窗口内升高，最大值约 `0.225s`。
- `alarm_frontend_probe_success` 保持为 `1`。
- `running__frontend` 保持为 `1`。

该组数据能直接体现前端 CPU 压力对服务质量指标的影响，是阶段四中另一组主要复现案例。

## 阶段结论

阶段二完成了监控、可视化、故障注入和数据导出的闭环。三组故障数据均包含原始 Prometheus 响应、处理后的 KPI 矩阵、元数据和截图证据，可直接支撑阶段四 KPIRoot 的算法复现与结果分析。
