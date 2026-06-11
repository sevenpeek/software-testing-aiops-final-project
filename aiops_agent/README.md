# aiops_agent

本目录是我的智能运维 Agent 代码。

第一版是离线版，只读取同学两个最终项目已有输出：

- USAD 异常检测输出。
- KPIRoot 根因定位输出。

本项目不会修改 `external_projects`，不会运行 USAD 训练脚本，不会运行 KPIRoot phase4 脚本，也不会执行任何恢复动作。

运行方式：

```powershell
python aiops_agent\run_agent.py --config aiops_agent\config.json
```

默认报告输出：

```text
aiops_agent/outputs/diagnosis_report.md
```

## 第二阶段：Kubernetes 只读证据查询

第二阶段增加 Kubernetes 只读证据查询能力。Agent 会根据 KPIRoot Top1 服务自动查询：

- Pod 状态。
- Deployment 状态。
- Service 状态。
- Namespace 内近期 Event。
- 根因服务日志尾部。

Kubernetes 日志采集会进行脱敏处理，默认会屏蔽 `credit_card_number`、`credit_card_cvv`、`credit_card_expiration_year` 和 `credit_card_expiration_month` 等敏感格式字段。报告只展示有限行数日志，避免输出过长和暴露敏感格式字段。

本阶段仍然只执行只读查询，不执行恢复动作，不会执行 `rollout restart`，不会删除 Pod，也不会修改集群状态。

运行前需要保证：

- Minikube 可用。
- `kubectl` 可用。
- Online Boutique 已部署在 `online-boutique` namespace 中。

运行命令仍然是：

```powershell
python aiops_agent\run_agent.py --config aiops_agent\config.json
```

## 第三阶段：Prometheus 实时指标查询

第三阶段加入 Prometheus 实时指标查询。当前实现通过 `kubectl exec` 进入 `monitoring` namespace 中的 `prometheus-deployment`，在 Pod 内部访问：

```text
http://localhost:9090/api/v1/query
```

本阶段主要查询 cAdvisor/container 指标，例如：

- Online Boutique namespace 下的容器 CPU 指标序列数量。
- Online Boutique 总 CPU rate。
- KPIRoot Top1 服务的 CPU rate。
- KPIRoot Top1 服务的 memory working set。
- KPIRoot Top1 服务的容器指标数量。

由于当前 kube-state-metrics 可能不可用或处于 ImagePullBackOff，本阶段暂不依赖 `kube_pod_*`、`kube_deployment_*` 等 kube-state 指标。

Prometheus 查询仍然是只读操作，不执行恢复动作，不修改 Kubernetes 集群状态。

运行命令仍然是：

```powershell
python aiops_agent\run_agent.py --config aiops_agent\config.json
```

## 第四阶段：恢复建议生成

第四阶段增加恢复建议 / 恢复计划生成功能。Agent 会根据 USAD、KPIRoot、Kubernetes 和 Prometheus 的综合证据生成：

- 恢复决策。
- 风险等级。
- 推荐动作。
- 建议命令草案。
- 安全说明。

默认配置为：

```json
{
  "dry_run": true,
  "execute_recovery": false
}
```

本阶段不执行真实恢复命令，不会自动执行 `kubectl rollout restart`、`kubectl delete`、`kubectl apply` 等修改集群状态的命令。报告中的恢复命令仅作为人工复核草案展示。

如未来需要自动恢复，必须同时开启配置，并进行人工确认。

## VeADK / LLM Agent 封装层

本项目核心功能由 `run_agent.py` 的规则编排流程实现。`veadk_agent.py` 是参考老师“使用智能体进行智能运维”教程增加的 Agent 封装层。

该层将以下能力封装为可调用工具：

- USAD 异常检测结果查询。
- KPIRoot 根因定位结果查询。
- Kubernetes Pod / Deployment / Service / Event / Log 只读证据查询。
- Prometheus 实时指标查询。
- dry-run 恢复建议生成。
- 完整诊断报告生成。

默认不需要 API Key，`veadk_agent.py` 会运行 deterministic fallback，直接调用本地完整诊断流程。即使环境中存在 API Key，不加 `--llm` 时也仍然运行 deterministic fallback，避免演示时误调用外部模型。

有 OpenAI-compatible API Key 且显式加上 `--llm` 时，可进行 tool calling 风格的多轮诊断。LLM 模式只接收摘要字段，不会接收完整 Kubernetes 日志原文；默认不执行真实恢复命令。

无 API Key fallback：

```powershell
python aiops_agent\veadk_agent.py --config aiops_agent\config.json --alert "paymentservice CPU anomaly"
```

安装可选依赖：

```powershell
pip install -r aiops_agent\requirements-veadk.txt
```

设置环境变量示例：

```powershell
set OPENAI_API_KEY=your_key
set OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
set OPENAI_MODEL=your-model
```

OpenAI-compatible LLM 运行：

```powershell
python aiops_agent\veadk_agent.py --config aiops_agent\config.json --alert "Online Boutique paymentservice may have CPU anomaly" --llm
```

### 火山方舟 API Key 适配

如需启用火山方舟 LLM tool calling，请只通过环境变量传入凭据，不要把 API Key 写入代码或 `config.json`。

需要设置：

- `ARK_API_KEY`
- `ARK_MODEL`
- 可选 `ARK_BASE_URL`，默认 `https://ark.cn-beijing.volces.com/api/v3`

Windows PowerShell 示例：

```powershell
$env:ARK_API_KEY="your_ark_api_key"
$env:ARK_MODEL="your_model_or_endpoint_id"
$env:ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
```

运行：

```powershell
python aiops_agent\veadk_agent.py --config aiops_agent\config.json --alert "Online Boutique paymentservice CPU anomaly" --llm
```

LLM 模式不会执行真实恢复命令；恢复建议仍然受 `execute_recovery=false` / `dry_run=true` 保护。恢复命令只作为人工复核草案展示。

## 故障注入测试

项目提供 Chaos Mesh 测试文件，用于对 `paymentservice` 注入短时间 CPU 压力，验证 Agent 是否会根据 Prometheus 实时指标改变恢复建议。

测试文件：

```text
aiops_agent/chaos/paymentservice_cpu_stress.yaml
aiops_agent/scripts/apply_paymentservice_cpu_stress.ps1
aiops_agent/scripts/delete_paymentservice_cpu_stress.ps1
aiops_agent/docs/TEST_PLAN.md
```

注入 CPU 压力：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\apply_paymentservice_cpu_stress.ps1
```

删除 CPU 压力：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\delete_paymentservice_cpu_stress.ps1
```

该测试用于观察 `recovery decision` 是否从 `observe` 变为 `cpu_pressure_investigation`。所有恢复动作仍为 dry-run，`kubectl rollout restart` 只作为命令草案展示，不会由 Agent 自动执行。

## Online Boutique 部署说明

`external_projects` 是组员项目，不应修改。Online Boutique 的部署文件应放在本项目自己的目录：

```text
aiops_agent/k8s/online-boutique/kubernetes-manifests.yaml
```

部署命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\deploy_online_boutique.ps1
```

检查命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\check_online_boutique.ps1
```

前端端口转发命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\port_forward_frontend.ps1
```

默认前端访问地址：

```text
http://127.0.0.1:8088
```

## 最终演示入口

最终演示建议优先使用稳定入口：

```powershell
python aiops_agent\run_agent.py --config aiops_agent\config.json
```

`run_agent.py` 是规则编排型 hybrid AIOps Agent，会串联 USAD、KPIRoot、Kubernetes 只读证据、Prometheus 实时指标和 dry-run 恢复建议，适合作为答辩主流程。

`veadk_agent.py` 用于展示 VeADK / LLM Agent 风格封装层。无 API Key 时可运行 deterministic fallback：

```powershell
python aiops_agent\veadk_agent.py --config aiops_agent\config.json --alert "Online Boutique paymentservice CPU anomaly"
```

如需展示火山方舟或 OpenAI-compatible tool calling，需要通过环境变量配置 API Key 和模型，并显式添加 `--llm`：

```powershell
python aiops_agent\veadk_agent.py --config aiops_agent\config.json --alert "Online Boutique paymentservice CPU anomaly" --llm
```

API Key 只允许通过环境变量配置，不应写入代码、`config.json` 或提交材料。

所有恢复动作默认 dry-run，不会自动执行真实恢复命令。`kubectl rollout restart` 等命令只作为人工确认后的建议草案展示。

最终演示可参考：

- `aiops_agent/docs/FINAL_SUMMARY.md`
- `aiops_agent/docs/DEMO_SCRIPT.md`
- `aiops_agent/docs/SCREENSHOT_CHECKLIST.md`
- `aiops_agent/docs/PACKAGE_GUIDE.md`

## 自动巡检模式

`watch_agent.py` 提供自动巡检触发器，会定时查询 Prometheus 中 KPIRoot Top1 服务的 CPU rate。当 CPU rate 超过 `config.json` 中的 `recovery.cpu_pressure_threshold` 时，自动运行一次完整诊断，并将报告归档为带时间戳的文件：

```text
aiops_agent/outputs/auto_diagnosis_YYYYMMDD_HHMMSS.md
```

运行示例：

```powershell
python aiops_agent\watch_agent.py --config aiops_agent\config.json --interval 30 --max-rounds 10
```

常用参数：

- `--cooldown 60`：触发一次诊断后 60 秒内不重复触发。
- `--trigger-once`：检测到一次异常并完成诊断后退出。
- `--history-file aiops_agent\outputs\watch_history.csv`：指定自动巡检历史 CSV。
- `--llm`：异常触发后先运行本地诊断，再运行 LLM 智能体诊断。

每轮巡检都会写入 `watch_history.csv`，包括 `service_cpu_rate`、`threshold`、`triggered`、`recovery_decision`、`report_path`、`llm_enabled` 和 `llm_executed` 等字段。

如需在异常触发后同时展示 LLM tool calling，可显式添加 `--llm`，并提前通过环境变量设置 `ARK_API_KEY` 和 `ARK_MODEL`。不加 `--llm` 时不会调用外部模型。

## 本地 Web Dashboard 模式

安装 Streamlit：

```powershell
pip install -r aiops_agent\requirements-dashboard.txt
```

启动 Dashboard：

```powershell
streamlit run aiops_agent\dashboard_app.py
```

页面标题为“AIOps Agent 智能运维控制台”，可用于：

- Tab 1：系统总览，查看项目信息、dry-run 安全策略和当前运行状态。
- Tab 2：故障注入，自定义 Service、Duration、CPU Load、Workers 后注入或删除 CPU 压力。
- Tab 3：检测中心，按“检测方式 + 执行模式”组合运行诊断。
- Tab 4：自动巡检日志，查看 `watch_history.csv`、triggered 记录、报告路径和 LLM 输出路径，并支持归档或清空当前巡检日志。
- Tab 5：报告中心，查看 `diagnosis_report*.md` 和 `auto_diagnosis_*.md`。
- Tab 6：端到端实时流水线，将 Prometheus 实时采集、USAD/KPIRoot 输入适配、算法 dry-run 编排和 Agent 诊断串联起来。

Dashboard 已优化为适合课程演示截图的宽屏布局：系统名、namespace、服务名、状态值和报告路径会使用可换行卡片展示，避免出现省略号。

检测中心支持四种组合：

- 一次检测 + 本地规则模式。
- 一次检测 + LLM 智能体模式。
- 自动巡检 + 本地规则模式。
- 自动巡检 + LLM 智能体模式。

左侧栏提供 LLM API 设置：

- Provider：火山方舟 Ark 或 OpenAI-compatible。
- API Key：密码输入框，仅保存到当前 Streamlit 会话。
- Base URL：默认 `https://ark.cn-beijing.volces.com/api/v3`。
- Model：例如 `doubao-seed-2-0-lite-260428`。

API Key 不会写入代码、`config.json`、README 或日志。也可以继续使用系统环境变量 `ARK_API_KEY` / `ARK_MODEL`。

自动巡检演示推荐参数：

- `interval=5`
- `max_rounds=3`
- `cooldown=60`
- `trigger_once=True`

自动巡检运行时，页面右上角出现 Stop 是 Streamlit 正在执行任务的正常提示，不代表程序错误。页面会在 `watch_agent.py` 子进程结束后一次性显示输出。

自动巡检日志说明：

- `watch_history.csv` 是持久化记录，刷新页面或重启 Streamlit 后不会自动清空。
- Dashboard 支持将当前日志归档为 `watch_history_archive_YYYYMMDD_HHMMSS.csv`。
- Dashboard 支持清空当前 `watch_history.csv`，后续自动巡检会重新生成新日志。
- 建议演示前先归档并清空旧日志，避免上次测试记录干扰截图。
- 清空日志不会删除 `diagnosis_report*.md`、`auto_diagnosis_*.md` 或 `llm_diagnosis_*.txt`。

安全说明：

- Dashboard 中的故障注入按钮会创建或删除 ChaosMesh StressChaos 对象，属于演示环境操作。
- Dashboard 不会执行 `kubectl rollout restart`。
- Agent 恢复动作仍然是 dry-run，不会自动执行真实恢复命令。
- API Key 只通过环境变量配置，不写入代码或 `config.json`。
- Dashboard 左侧栏输入的 API Key 只保存在当前 Streamlit 会话中，不落盘。

## 端到端实时 AIOps 流水线

项目新增实时流水线入口：

```powershell
python aiops_agent\realtime_pipeline_agent.py --config aiops_agent\config.json --duration-minutes 5 --step-seconds 15 --dry-run
```

该流程用于把当前运行中的 Online Boutique 与论文复现项目串联：

```text
Prometheus 最近 N 分钟指标
-> runtime CSV
-> USAD/KPIRoot runtime 输入
-> USAD 异常检测
-> KPIRoot 根因定位
-> aiops_agent 综合诊断报告
```

默认 `dry-run`，不会真正重跑 `external_projects` 中的 USAD/KPIRoot。默认只会：

- 采集 Prometheus 只读指标；
- 生成 `aiops_agent/runtime_data/prometheus_realtime_*.csv`；
- 生成 `usad_input_*.csv` 和 `kpiroot_input_*.csv`；
- 生成 KPIRoot phase2 runtime 目录；
- 打印将要运行的外部命令；
- 使用当前已有输出继续生成 Agent 诊断；
- 生成 `aiops_agent/runtime_outputs/realtime_pipeline_report_*.md`。

实时流水线支持分阶段执行外部算法：

```powershell
python aiops_agent\realtime_pipeline_agent.py --config aiops_agent\config.json --duration-minutes 5 --step-seconds 15 --execute-usad-only --usad-epochs 1 --usad-window 5 --usad-train-ratio 0.7
```

```powershell
python aiops_agent\realtime_pipeline_agent.py --config aiops_agent\config.json --duration-minutes 5 --step-seconds 15 --execute-kpiroot-only --kpiroot-scenario realtime-paymentservice-cpu --kpiroot-alarm paymentservice
```

```powershell
python aiops_agent\realtime_pipeline_agent.py --config aiops_agent\config.json --duration-minutes 5 --step-seconds 15 --execute-external
```

推荐顺序：

1. 先用 dry-run 验证 Prometheus 实时数据和 runtime 输入。
2. 再用 `--execute-usad-only --usad-epochs 1` 做低成本 USAD 测试。
3. 再尝试 `--execute-kpiroot-only`。
4. 最后再考虑 `--execute-external`。

所有运行输出都会写入 `aiops_agent/runtime_outputs`，不覆盖 `external_projects` 原始输出。启用前建议先阅读：

```text
aiops_agent/docs/REALTIME_AIOPS_PIPELINE_ANALYSIS.md
```

当前仍需组员确认实时 USAD/KPIRoot 输入格式，尤其是 USAD 是否需要更多业务指标，以及 KPIRoot realtime metadata 中故障窗口如何定义。USAD 当前是训练 + 推理一体，不是纯在线推理；短窗口结果主要适合集成验证和课程演示。
# 多类型故障实验框架补充

当前项目已从单一 `paymentservice` CPU 压力场景扩展为多类型故障实验框架：

- `cpu_stress`：CPU 压力故障，ChaosMesh `StressChaos`，已完整验证；主要依据 `service_cpu_rate`，对应恢复建议 `cpu_pressure_investigation`。
- `memory_stress`：内存压力故障，ChaosMesh `StressChaos`，实验性；默认 `MemorySize=128MB`，主要依据 `service_memory_working_set_mib`，对应 `memory_pressure_investigation`。
- `pod_kill`：Pod Kill 故障，ChaosMesh `PodChaos`，实验性；只杀一个 Pod，不修改 Deployment；主要依据 Pod 状态、restart count、Deployment available 和 Kubernetes Event。
- `network_delay`：网络延迟故障，ChaosMesh `NetworkChaos`，待扩展；当前缺少应用层 latency/error rate 指标，因此主要用于扩展演示和人工复核。

通用脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\apply_fault.ps1 -FaultType cpu_stress -Service paymentservice -Duration 2m -CpuLoad 80 -Workers 1
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\delete_fault.ps1 -FaultType cpu_stress -Service paymentservice
```

旧脚本 `apply_paymentservice_cpu_stress.ps1` 和 `delete_paymentservice_cpu_stress.ps1` 已保留兼容。所有 ChaosMesh 注入都必须由用户手动触发；Agent 恢复动作仍保持 `dry-run=true`，不会自动执行 `rollout restart` 或真实恢复命令。
# Dashboard 最终主流程说明

当前 Dashboard 已整合为六个顶部 Tab：

1. 系统总览
2. 实时故障实验
3. 端到端 AIOps 诊断
4. 结果与报告中心
5. 高级工具
6. 项目架构说明

推荐演示主线已经调整为端到端实时 AIOps：实时故障实验选择 `paymentservice` + CPU 压力故障，手动注入故障后进入“端到端 AIOps 诊断”，选择 `execute USAD + KPIRoot`，使用当前 Prometheus 实时数据生成 runtime 输入并真实运行 USAD/KPIRoot，最后由 Agent 生成诊断报告和 dry-run 恢复建议。

旧的 `run_agent.py` 离线输出读取能力仍然保留，但已经放入“高级工具”和兼容说明中，不再作为推荐演示路线。所有 runtime 输出均写入 `aiops_agent/runtime_outputs`，不会覆盖 `external_projects` 原始结果。
