# 阶段四：ISSRE24-KPIRoot 论文复现

生成时间：2026-06-08T20:00:55

本文档记录本仓库负责的论文复现部分。课程大作业为小组作业，要求复现两篇异常检测/故障诊断相关论文；本仓库复现的是其中一篇：

```text
ISSRE 2024 - KPIRoot: Efficient Monitoring Metric-based Root Cause Localization in Large-scale Cloud Systems
```

另一篇论文的复现结果由组内其他成员负责整合。

## 复现目标

KPIRoot 的目标是在系统级 KPI 出现异常后，从多个底层 KPI 中定位最可能导致异常的根因 KPI。

原论文中的场景是 Cloud H 的主机集群与 VM；本项目将其适配为 Online-Boutique 的微服务监控数据：

| 原论文概念 | 本项目映射 |
| --- | --- |
| Host/cluster alarm KPI | 聚合 CPU、聚合内存、前端探针延迟等系统级 KPI |
| VM KPI | 各微服务的 CPU、内存、文件系统、运行状态等 KPI |
| Root-cause VM | 被 ChaosMesh 注入故障的目标服务 |

## 实现内容

实现文件如下：

- `src/kpiroot/algorithm.py`：PAA、SAX、异常窗口选择、相似度、因果得分与排序逻辑。
- `src/kpiroot/data.py`：阶段二数据读取、元数据解析、合成告警 KPI 构造。
- `src/kpiroot/cli.py`：批量运行、评估、绘图和文档生成。
- `tests/kpiroot/test_algorithm.py`：KPIRoot 复现代码的单元测试。
- `scripts/run-phase4-kpiroot.ps1`：阶段四运行脚本。

已实现的算法流程：

1. 读取阶段二导出的 `kpi_matrix.csv`。
2. 构造合成系统级告警 KPI，例如 `synthetic_total_cpu`、`synthetic_total_memory`。
3. 对 KPI 进行缺失值处理和标准化。
4. 使用 PAA 对时间序列降维。
5. 使用 SAX 将连续数值序列转换为符号序列。
6. 根据故障注入记录选择异常窗口，自动趋势检测作为备用逻辑。
7. 使用 SAX-Jaccard 计算候选 KPI 与告警 KPI 的相似度。
8. 使用 Granger 风格 F 统计量计算候选 KPI 对告警 KPI 的时序因果得分。
9. 使用论文中的权重设置计算综合得分：`0.9 * similarity + 0.1 * normalized_causality`。
10. 输出候选根因 KPI 排名，并进行消融对比。

## 运行方式

运行阶段四实验：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\FinalProject\scripts\run-phase4-kpiroot.ps1
```

运行单元测试：

```powershell
.\FinalProject\.conda\python.exe -m pytest .\FinalProject\tests\kpiroot -v -o "cache_dir=FinalProject\.pytest_cache"
```

## 输出文件

阶段四输出目录：

```text
kpiroot_realtime_20260608_200053
```

主要文件：

- `summary.csv`：三组故障场景的 KPIRoot 总结结果。
- `ablation_summary.csv`：相似度-only、因果-only、综合 KPIRoot 的消融对比。
- `<scenario>/ranking.csv`：每个场景的候选 KPI 排名。
- `<scenario>/score_breakdown.csv`：每个场景的相似度、因果得分和综合得分。
- `<scenario>/topk_scores.png`：Top-K 根因得分图。
- `<scenario>/alarm_top_candidates.png`：告警 KPI 与 Top 候选 KPI 曲线对比图。

## 主实验结果

| 故障场景 | 告警 KPI | 真实根因服务 | Top-1 KPI | 真实根因服务排名 | Hit@1 | Hit@3 | Hit@5 |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| realtime-paymentservice-cpu | `paymentservice` | `paymentservice` | `cpu__paymentservice` | 1 | yes | yes | yes |

## 消融实验结果

消融实验复用同一批 KPI 得分，只改变排序目标：

- `similarity_only`：仅使用 SAX-Jaccard 相似度排序。
- `causality_only`：仅使用归一化后的 Granger 因果得分排序。
- `kpiroot_combined`：使用 KPIRoot 综合得分排序。

| 故障场景 | 方法 | Top-1 KPI | 真实根因服务排名 | Hit@1 | Hit@3 | Hit@5 |
| --- | --- | --- | ---: | --- | --- | --- |
| realtime-paymentservice-cpu | `similarity_only` | `cpu__paymentservice` | 1 | yes | yes | yes |
| realtime-paymentservice-cpu | `causality_only` | `memory__frontend` | 21 | no | no | no |
| realtime-paymentservice-cpu | `kpiroot_combined` | `cpu__paymentservice` | 1 | yes | yes | yes |

## 输出明细

- 总结 CSV：`kpiroot_realtime_20260608_200053/summary.csv`
- 消融总结 CSV：`kpiroot_realtime_20260608_200053/ablation_summary.csv`
- 每个故障场景的输出：
  - `kpiroot_realtime_20260608_200053/realtime-paymentservice-cpu/ranking.csv`
  - `kpiroot_realtime_20260608_200053/realtime-paymentservice-cpu/ablation_summary.csv`
  - `kpiroot_realtime_20260608_200053/realtime-paymentservice-cpu/topk_scores.png`
  - `kpiroot_realtime_20260608_200053/realtime-paymentservice-cpu/alarm_top_candidates.png`

## 结果分析

两组 CPU Stress 场景是最有代表性的复现实验：

- `stress-paymentservice-cpu-001` 中，`synthetic_total_cpu` 出现明显升高，KPIRoot 将 `cpu__paymentservice` 排名第一。
- `stress-frontend-cpu-001` 中，`synthetic_total_cpu` 与 `cpu__frontend` 的变化趋势高度一致，KPIRoot 将 `cpu__frontend` 排名第一。

Pod Kill 场景保留为补充案例。由于 processed 数据将替换前后的 Pod 合并到了服务级别，Pod 身份变化被部分隐藏，因此该场景更适合作为边界情况说明。

消融实验显示，在本课程采集的短时间序列数据上，单独使用 Granger 因果得分并不稳定；SAX 相似度与 KPIRoot 综合得分均能稳定定位真实根因服务。最终报告中建议重点展示两组 CPU Stress 场景，并将 Pod Kill 作为补充说明。

## 与原论文的差异

- 原论文使用 Cloud H 工业环境中的大规模主机集群/VM KPI；本项目使用 Online-Boutique 微服务系统的服务级 KPI。
- 原论文数据规模较大，时间序列更长；本项目故障窗口较短，因此 PAA 参数做了适配。
- 原论文自动检测 alarm KPI 的异常段；本项目优先使用故障注入记录中的时间窗口，自动趋势检测作为备用逻辑。
- 本项目的目标是课程复现与工程验证，因此重点放在算法流程可运行、结果可解释、数据与图表可复查。
