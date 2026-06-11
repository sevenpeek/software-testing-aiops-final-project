# 软件测试与维护大作业：Online-Boutique 运维实验与 KPIRoot 复现

本仓库是“软件测试与维护”课程期末大作业的项目仓库，围绕
`JoinFyc/Online-Boutique` 开源微服务系统完成部署、监控、故障注入、黑盒测试与论文算法复现。

需要说明的是：本课程大作业以小组形式完成，基本要求是复现两篇异常检测/故障诊断相关论文。本仓库记录的是本人负责的部分，复现论文为：

```text
ISSRE 2024 - KPIRoot: Efficient Monitoring Metric-based Root Cause Localization in Large-scale Cloud Systems
```

另一篇论文的复现与智能体封装工作由组内其他成员负责，不包含在本仓库中。

## 项目内容

本仓库完成的内容包括：

- 阶段一：部署 Online-Boutique 微服务系统。
- 阶段二：使用 Prometheus、Grafana、Blackbox Exporter 与 ChaosMesh 完成监控、故障注入和数据采集。
- 阶段三：使用 Selenium 和 JMeter 完成前端功能测试与性能测试。
- 阶段四：基于阶段二采集的故障数据，复现 ISSRE24-KPIRoot 的核心根因定位算法。

## 目录结构

```text
chaos/       ChaosMesh 故障注入配置
data/        实验采集数据、测试数据与 KPIRoot 输出结果
docs/        各阶段执行记录与说明文档
papers/      本仓库复现论文原文
reports/     最终实验报告 PDF
grafana/     Grafana Dashboard 配置
monitoring/  Blackbox Exporter 等监控配置
scripts/     部署、恢复、数据导出、测试与算法运行脚本
src/         KPIRoot 复现源码
tests/       Selenium、JMeter 与 KPIRoot 测试文件
```

## 阶段四：ISSRE24-KPIRoot 复现

论文原文见：[ISSRE24-KPIRoot](papers/ISSRE24-KPIRoot.pdf)。

KPIRoot 的任务是：当系统级 KPI 出现异常后，根据多个候选服务 KPI 的变化趋势，定位最可能导致异常的根因 KPI。

本仓库将原论文的 Cloud H 主机集群/VM 场景适配到 Online-Boutique 微服务场景：

| 原论文概念 | 本项目映射 |
| --- | --- |
| Host/cluster alarm KPI | 聚合 CPU、聚合内存、前端探针延迟等系统级 KPI |
| VM KPI | 各微服务的 CPU、内存、文件系统、运行状态等 KPI |
| Root-cause VM | 被 ChaosMesh 注入故障的目标服务 |

已实现的核心步骤：

1. 读取阶段二导出的 `kpi_matrix.csv`。
2. 构造系统级告警 KPI，例如 `synthetic_total_cpu`、`synthetic_total_memory`。
3. 对 KPI 进行标准化与 PAA 降维。
4. 将 PAA 序列转换为 SAX 符号序列。
5. 根据故障注入元数据选择异常窗口。
6. 计算 SAX-Jaccard 相似度。
7. 计算 Granger 风格的因果得分。
8. 使用 `0.9 * similarity + 0.1 * causality` 生成 KPIRoot 综合得分。
9. 输出根因 KPI 排名，并进行消融对比。

## 阶段四结果

主要结果保存在：

```text
data/phase4/kpiroot/summary.csv
data/phase4/kpiroot/ablation_summary.csv
docs/PHASE4_KPIROOT.md
```

三组故障数据上的结果如下：

| 故障场景 | 告警 KPI | Top-1 KPI | 真实根因服务排名 |
| --- | --- | --- | ---: |
| `stress-paymentservice-cpu-001` | `synthetic_total_cpu` | `cpu__paymentservice` | 1 |
| `stress-frontend-cpu-001` | `synthetic_total_cpu` | `cpu__frontend` | 1 |
| `pod-kill-paymentservice-001` | `synthetic_total_memory` | `memory__paymentservice` | 1 |

消融实验显示：在本项目较短的课程实验时序数据上，`causality_only` 排名不稳定；`similarity_only` 与 `kpiroot_combined` 均能将真实根因服务排在第一。报告中应重点展示两组 CPU Stress 场景，Pod Kill 可作为补充或边界案例。

## 运行方式

运行阶段四 KPIRoot 复现：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-phase4-kpiroot.ps1
```

运行 KPIRoot 单元测试：

```powershell
.\.conda\python.exe -m pytest .\tests\kpiroot -v -o "cache_dir=.pytest_cache"
```

若要重新打开 Online-Boutique 前端，可参考：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\resume-online-boutique.ps1
```

## 大作业报告

最终实验报告见：[大作业报告（PDF）](reports/final_report/2311901_王新杰_2312385_王子祺_软件测试与维护大作业报告.pdf)。

报告内容覆盖 Online-Boutique 微服务系统部署、Prometheus/Grafana 监控与故障数据采集、Selenium/JMeter 测试、ISSRE24-KPIRoot 论文方法复现、实验结果、消融实验、局限分析和参与者贡献说明。

## 文档索引

- [大作业报告（PDF）](reports/final_report/2311901_王新杰_2312385_王子祺_软件测试与维护大作业报告.pdf)
- [复现论文：ISSRE24-KPIRoot](papers/ISSRE24-KPIRoot.pdf)
- [阶段一部署记录](docs/PHASE1_DEPLOYMENT.md)
- [阶段二监控与数据采集说明](docs/PHASE2_MONITORING_AND_DATA_COLLECTION.md)
- [阶段二执行记录](docs/PHASE2_EXECUTION_LOG.md)
- [阶段三测试计划](docs/PHASE3_TESTING_PLAN.md)
- [阶段三执行记录](docs/PHASE3_EXECUTION_LOG.md)
- [阶段四 KPIRoot 复现说明](docs/PHASE4_KPIROOT.md)

## 备注

本仓库中的脚本、配置、实验数据和结果图表可用于课程报告与答辩展示。最终小组报告中还需要合并另一篇论文的复现结果，以及组内其他成员负责的智能体封装部分。
