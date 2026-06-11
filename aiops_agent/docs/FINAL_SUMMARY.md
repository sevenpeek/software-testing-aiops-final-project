# AIOps Agent 最终总结

## 项目目标

本项目面向 Online Boutique 微服务系统，构建一个智能运维 Agent，将异常检测、根因定位、Kubernetes 运行证据、Prometheus 实时指标和 dry-run 恢复建议串联起来，形成“异常发现 -> 根因定位 -> 证据查询 -> 诊断报告 -> 恢复建议”的闭环。

项目重点不是重新训练模型，而是把组员已有论文复现成果集成为可演示、可解释、可扩展的智能运维流程。

## 系统整体架构

整体架构由五类能力组成：

- USAD 异常检测结果读取：判断系统 KPI 时间序列中是否出现异常窗口。
- KPIRoot 根因定位结果读取：在异常发生后给出候选根因指标和根因服务排名。
- Kubernetes 只读证据查询：查询 Pod、Deployment、Service、Event 和日志。
- Prometheus 实时指标查询：查询在线 CPU、内存和容器指标。
- Recovery dry-run：根据证据生成恢复建议和命令草案，但不执行真实恢复命令。

核心入口包括：

- `aiops_agent/run_agent.py`：规则编排型 hybrid AIOps Agent，适合稳定演示。
- `aiops_agent/veadk_agent.py`：VeADK / LLM Agent 风格封装层，适合展示工具调用式智能体。
- `aiops_agent/watch_agent.py`：自动巡检触发器，定时检查 Prometheus CPU 指标并在超过阈值时归档诊断报告。
- `aiops_agent/dashboard_app.py`：Streamlit 本地 Web 控制台，用于展示状态、运行诊断、查看报告和触发演示操作。
- `aiops_agent/realtime_pipeline_agent.py`：端到端实时 AIOps 流水线入口，用于采集 Prometheus 实时指标、构建 USAD/KPIRoot 输入并编排诊断。

## 与组员 USAD / KPIRoot 项目的关系

`external_projects/usad_anomaly_detection` 是组员的 USAD 异常检测论文复现项目，本项目只读取其已有输出文件，例如 `anomaly_scores.csv` 和 `metrics_summary.txt`。

`external_projects/kpiroot_fault_diagnosis` 是组员的 KPIRoot 根因定位论文复现项目，本项目只读取其已有输出文件，例如 `summary.csv`、`ablation_summary.csv`、`ranking.csv` 和 `summary.json`。

本项目不修改组员代码，不重新运行 USAD 训练，也不重新运行 KPIRoot phase4。`aiops_agent` 是最终集成和演示代码目录。

## Agent 工作流程

1. 加载 `aiops_agent/config.json`。
2. 读取 USAD 输出，判断是否存在异常窗口。
3. 读取 KPIRoot 输出，得到 Top1 根因指标和根因服务。
4. 根据 Top1 服务执行 Kubernetes 只读查询。
5. 根据 Top1 服务执行 Prometheus 实时指标查询。
6. 根据离线算法结果和在线证据生成 dry-run 恢复建议。
7. 生成 `aiops_agent/outputs/diagnosis_report.md`。

在自动巡检模式下，`watch_agent.py` 会循环查询 Prometheus 中 Top1 服务的实时 CPU rate。当 CPU rate 超过 `recovery.cpu_pressure_threshold` 时，自动触发完整诊断，并将报告保存为 `auto_diagnosis_YYYYMMDD_HHMMSS.md`。

在端到端实时流水线模式下，`realtime_pipeline_agent.py` 会采集最近 N 分钟 Prometheus 指标，生成 runtime CSV，将其适配为 USAD/KPIRoot 输入，并在 dry-run 模式下输出外部算法运行计划。只有显式 `--execute-external` 时才尝试运行外部项目，且输出目录位于 `aiops_agent/runtime_outputs`，不覆盖同学原始结果。

实时流水线进一步支持分阶段低成本执行：`--execute-usad-only` 只运行 USAD，`--execute-kpiroot-only` 只运行 KPIRoot，`--execute-external` 同时运行两者。USAD 参数可通过 `--usad-epochs`、`--usad-window`、`--usad-train-ratio` 控制，推荐先用 `--usad-epochs 1` 做低成本集成验证。

## run_agent.py 和 veadk_agent.py 的区别

`run_agent.py` 是稳定的规则编排入口。它不依赖 API Key，不调用外部 LLM，直接按固定流程调用本地工具，适合答辩时优先演示。

`veadk_agent.py` 是参考老师 VeADK / LLM Agent 教程增加的封装层。它把 USAD、KPIRoot、Kubernetes、Prometheus、Recovery 和完整诊断流程封装为 Agent 可调用工具。无 API Key 时运行 deterministic fallback；配置火山方舟或 OpenAI-compatible API Key 并显式添加 `--llm` 后，可以展示 tool calling 风格的多轮诊断。

`watch_agent.py` 是轻量自动巡检入口。它不替代 `run_agent.py`，而是在 Prometheus 指标超过阈值时自动调用现有诊断流程，并归档带时间戳的报告。

`dashboard_app.py` 是本地网页控制台入口。它把命令行能力包装成可视化页面，使项目从命令行工具扩展为可视化智能运维原型系统。

## Kubernetes 证据查询能力

Agent 会根据 KPIRoot Top1 服务自动查询：

- Pod 状态。
- Deployment 状态。
- Service 状态。
- Namespace 近期 Event。
- 服务日志尾部。

查询命令均为只读命令。日志会进行敏感字段脱敏，报告中只展示有限行数，避免泄露支付相关字段。

## Prometheus 实时指标查询能力

Agent 通过 `kubectl exec` 进入 `monitoring` namespace 中的 Prometheus Deployment，在 Pod 内部访问 `localhost:9090` 查询 Prometheus API。

当前主要查询 cAdvisor/container 指标：

- Online Boutique 容器 CPU 指标序列数量。
- Online Boutique 总 CPU rate。
- Top1 根因服务 CPU rate。
- Top1 根因服务 memory working set。
- Top1 根因服务容器指标数量。

由于 kube-state-metrics 当前可能不可用，本阶段不依赖 `kube_pod_*`、`kube_deployment_*` 等 kube-state 指标。

## ChaosMesh 故障注入验证结果

项目提供 `paymentservice` CPU 压力故障注入 YAML 和 PowerShell 脚本，用于验证 Agent 是否能根据实时指标改变恢复建议。

已完成的演示报告包括：

- `diagnosis_report_baseline.md`：正常状态，恢复建议为 `observe`。
- `diagnosis_report_cpu_stress.md`：CPU 压力期间，Prometheus CPU 指标升高，恢复建议变为 `cpu_pressure_investigation`。
- `diagnosis_report_recovered.md`：删除故障并等待恢复后，恢复建议回到 `observe`。
- `diagnosis_report_llm_cpu_stress.md` 或同类 LLM 报告：展示 VeADK / 火山方舟 tool calling 风格入口在压力场景下的诊断结果。

## dry-run 恢复建议与安全保护

恢复模块只生成建议，不执行真实恢复动作。默认配置为：

```json
{
  "execute_recovery": false,
  "dry_run": true
}
```

即使报告中出现 `kubectl rollout restart` 这类命令，也只是“需人工确认后执行”的命令草案，Agent 不会自动运行。

安全边界包括：

- 不执行 `kubectl delete`。
- 不执行 `kubectl apply`。
- 不执行 `kubectl rollout restart`。
- 不删除 Pod。
- 不修改 Kubernetes 集群状态。
- 不把 API Key 写入代码或配置文件。

## 火山方舟 / VeADK / LLM Agent 封装说明

`veadk_agent.py` 支持两种模式：

- deterministic fallback：默认模式，不需要 API Key，不调用外部 API。
- LLM tool calling：需要显式添加 `--llm`，并通过环境变量配置 API Key 和模型。

火山方舟适配使用环境变量：

- `ARK_API_KEY`
- `ARK_MODEL`
- `ARK_BASE_URL`，可选，默认 `https://ark.cn-beijing.volces.com/api/v3`

LLM 模式只向模型传递摘要字段，例如异常状态、Top1 服务、Top1 指标、Kubernetes 健康状态、Prometheus CPU / 内存摘要、恢复决策和报告路径，不传完整 Kubernetes 日志。

## 自动巡检触发器

`watch_agent.py` 面向持续演示或长时间观察场景。典型运行命令为：

```powershell
python aiops_agent\watch_agent.py --config aiops_agent\config.json --interval 30 --max-rounds 10
```

它会定时查询 Prometheus 中 `paymentservice` 或 KPIRoot Top1 服务的 CPU rate，并与 `config.json` 中的 `recovery.cpu_pressure_threshold` 比较。超过阈值后，自动触发完整诊断并保存报告。

该模块仍保持安全边界：

- 不执行真实恢复命令。
- 不修改 `external_projects`。
- 不重新运行 USAD / KPIRoot。
- 不自动执行 ChaosMesh 注入。

## 本地 Web 控制台

`dashboard_app.py` 使用 Streamlit 实现本地网页 Dashboard。页面标题为“AIOps Agent 智能运维控制台”，包含：

- Tab 1：系统总览，展示 Online Boutique、namespace、hybrid 模式、dry-run 策略和当前状态摘要。
- Tab 2：故障注入，支持自定义 Service、Duration、CPU Load 和 Workers 后创建或删除 ChaosMesh StressChaos。
- Tab 3：检测中心，以“检测方式 + 执行模式”的二维结构组织诊断能力。
- Tab 4：自动巡检日志，读取 `watch_history.csv`，展示触发记录、报告路径和 LLM 输出路径，并支持归档或清空当前日志。
- Tab 5：报告中心，浏览 `diagnosis_report*.md` 和 `auto_diagnosis_*.md`。
- Tab 6：端到端实时流水线，展示实时 Prometheus 采集、USAD/KPIRoot 输入构建、dry-run / execute-external 和 pipeline report。

Dashboard 让项目从命令行工具扩展为可视化智能运维原型系统。需要注意的是，Dashboard 中的故障注入按钮会创建或删除 ChaosMesh StressChaos 对象，应只在演示环境中人工点击；恢复动作仍然保持 dry-run。

左侧栏提供 LLM API 设置。API Key 通过 `st.text_input(..., type="password")` 输入，只保存在当前 Streamlit 会话中，不写入代码、`config.json`、README 或日志。页面只显示 `ARK_API_KEY detected: True/False`、模型名和 Base URL，不显示完整 Key。用户也可以继续使用系统环境变量 `ARK_API_KEY` / `ARK_MODEL`。

Dashboard 已优化为适合课程演示截图的宽屏布局。系统总览、检测中心、自动巡检日志和报告中心都采用更清晰的卡片、日志框和报告区域，关键文本可以完整换行显示，避免系统名、namespace、服务名和报告路径被省略。

自动巡检默认演示参数调整为 `interval=5`、`max_rounds=3`、`cooldown=60`、`trigger_once=True`。运行自动巡检时，Streamlit 右上角出现 Stop 是任务正在执行的正常提示，页面会在 `watch_agent.py` 子进程结束后展示完整输出。

检测中心支持四种组合：

- 一次检测 + 本地规则模式：运行 `run_agent.py`，生成稳定诊断报告。
- 一次检测 + LLM 智能体模式：运行 `veadk_agent.py --llm`，展示 tool calling 风格诊断。
- 自动巡检 + 本地规则模式：运行 `watch_agent.py`，Prometheus 超阈值后自动触发本地诊断。
- 自动巡检 + LLM 智能体模式：Prometheus 超阈值后先运行本地诊断，再运行 `veadk_agent.py --llm` 并保存摘要。

`watch_agent.py` 新增 `--cooldown`、`--trigger-once` 和 `--history-file` 参数。每轮巡检都会向 `aiops_agent/outputs/watch_history.csv` 追加记录，包含 CPU rate、阈值、是否触发、恢复决策、风险等级、报告路径、LLM 是否启用和是否执行等字段。

`watch_history.csv` 是持久化巡检日志，刷新页面或重启 Streamlit 后不会自动清空。Dashboard 支持将当前日志归档为 `watch_history_archive_YYYYMMDD_HHMMSS.csv`，也支持清空当前 `watch_history.csv`。清空日志不会删除 `diagnosis_report*.md`、`auto_diagnosis_*.md` 或 `llm_diagnosis_*.txt`，因此适合在演示前先归档并清理旧记录，避免截图被历史测试数据干扰。

## 端到端实时流水线

新增实时流水线让项目从“读取已有 external outputs”升级为“可采集当前在线指标并生成算法输入”的原型：

```text
Online Boutique running
-> Prometheus query_range
-> prometheus_realtime_*.csv
-> usad_input_*.csv / kpiroot_input_*.csv
-> external USAD/KPIRoot dry-run or execute-external
-> aiops_agent final diagnosis
```

默认 dry-run 的原因：

- USAD 当前入口是训练 + 推理一体，实时运行可能耗时。
- KPIRoot 需要 phase2 场景目录和 metadata，实时故障窗口仍需组员确认。
- 直接运行外部项目固定脚本可能覆盖已有输出，因此本项目只使用 runtime 目录。

推荐启用顺序：

1. dry-run 验证 Prometheus 实时数据。
2. `--execute-usad-only --usad-epochs 1` 验证 USAD 集成。
3. `--execute-kpiroot-only` 验证 KPIRoot runtime phase2 输入。
4. `--execute-external` 串联 USAD + KPIRoot。

所有运行输出都写入 `aiops_agent/runtime_outputs`，不覆盖 `external_projects` 原始输出。

相关分析见 `aiops_agent/docs/REALTIME_AIOPS_PIPELINE_ANALYSIS.md`。

## 当前局限

- USAD 和 KPIRoot 使用的是已有离线输出，离线故障场景和在线故障注入场景仍需要在最终演示中说明对应关系。
- Prometheus 当前主要依赖 cAdvisor/container 指标，暂不依赖 kube-state-metrics。
- Kubernetes 证据查询是只读的，不包含自动修复执行。
- LLM Agent 层主要用于展示 tool calling 风格，稳定诊断仍建议优先使用 `run_agent.py`。
- 自动恢复没有开启，恢复命令仍需人工确认。
- Dashboard 中的 ChaosMesh 注入/删除按钮属于演示辅助操作，会修改 ChaosMesh 实验对象，需要人工确认后点击。
- Dashboard 中的 LLM 配置仅保存在当前会话，页面刷新或清除后需要重新设置。
- 端到端实时流水线的 execute-external 仍需组员确认 USAD/KPIRoot 输入格式后再启用。
- USAD 是训练 + 推理一体，不是纯在线推理；短窗口结果仅适合演示和集成验证。
- KPIRoot 的实时 metadata 和短窗口参数仍需组员确认。

## 后续改进方向

- 让 USAD 和 KPIRoot 支持统一的在线数据窗口输入。
- 增加 Prometheus 指标模板库，覆盖延迟、错误率、吞吐量和资源限制等指标。
- 在 kube-state-metrics 恢复后接入重启次数、Deployment 可用副本数等状态指标。
- 增加服务名映射表，处理指标名、Deployment 名、Service 名不完全一致的情况。
- 增加报告对比功能，自动比较 baseline、cpu_stress 和 recovered 三个阶段。
- 在严格审批机制下探索半自动恢复，但默认仍保持 dry-run。
# 多类型故障实验框架补充

项目现在支持四类常见故障实验：

- CPU 压力故障：`cpu_stress`，已完整验证，使用 ChaosMesh `StressChaos`，主要检测 `service_cpu_rate`。
- 内存压力故障：`memory_stress`，实验性，使用 ChaosMesh `StressChaos`，主要检测 `service_memory_working_set_mib`，默认内存压力为 `128MB`。
- Pod Kill 故障：`pod_kill`，实验性，使用 ChaosMesh `PodChaos`，主要检测 Pod phase、ready、restart count、Deployment available 和 Kubernetes Event。
- 网络延迟故障：`network_delay`，待扩展，使用 ChaosMesh `NetworkChaos`；当前缺少应用层 latency/error rate 指标，因此诊断结果以 manual review 为主。

Dashboard 的“故障实验中心”支持选择故障类型和目标服务，并按故障类型动态显示参数。当前算法解释最完整的场景仍是 `paymentservice` CPU 压力故障；其他故障类型已经接入框架，但端到端 USAD/KPIRoot 解释仍需继续校准。
# Dashboard 最终整合补充

Dashboard 当前采用六个 Tab：系统总览、实时故障实验、端到端 AIOps 诊断、结果与报告中心、高级工具、项目架构说明。主流程已经从“读取已有离线 USAD/KPIRoot 输出”升级为“端到端实时 AIOps”：Prometheus 采集当前故障窗口数据，生成 runtime 输入，真实运行 USAD 和 KPIRoot，再由 Agent 汇总 Kubernetes、Prometheus、Recovery 与可选 LLM 证据生成报告。

离线结果读取能力仍保留在高级工具中，用于兼容、调试和课程答辩时解释早期版本；正式演示建议优先使用“端到端 AIOps 诊断”。
