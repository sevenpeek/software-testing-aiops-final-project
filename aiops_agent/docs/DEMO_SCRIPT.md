# AIOps Agent 演示脚本

本文档用于答辩或组内演示。所有恢复动作默认 dry-run，不自动执行真实恢复命令。

## 1. 正常状态运行 run_agent.py

确认 Online Boutique、Prometheus 和 kubectl 环境可用后，在项目根目录运行：

```powershell
python aiops_agent\run_agent.py --config aiops_agent\config.json
```

重点观察终端输出：

```text
USAD has_anomaly: ...
KPIRoot top_service: paymentservice
Kubernetes health_status: healthy
Prometheus service_cpu_rate: ...
Recovery decision: observe
Report generated: ...
```

展示正常状态报告：

```text
aiops_agent/outputs/diagnosis_report_baseline.md
```

讲解重点：

- USAD 提供“是否异常”的离线证据。
- KPIRoot 提供“可能在哪里”的根因排名。
- Kubernetes 和 Prometheus 提供当前在线运行证据。
- 正常状态下恢复建议为 `observe`。

## 2. 注入 paymentservice CPU 压力

由演示者人工执行 ChaosMesh 注入脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\apply_paymentservice_cpu_stress.ps1
```

说明：

- 该脚本会应用 `aiops_agent/chaos/paymentservice_cpu_stress.yaml`。
- 目标为 `online-boutique` namespace 中 `app=paymentservice` 的 Pod。
- 压力持续时间为 2 分钟。
- 这是人工触发的故障注入，不由 Agent 自动执行。

等待 30 到 60 秒，让 Prometheus 采集到 CPU 指标变化。

## 3. CPU 压力期间运行 run_agent.py

再次运行：

```powershell
python aiops_agent\run_agent.py --config aiops_agent\config.json
```

重点观察终端输出：

```text
Prometheus service_cpu_rate: ...
Recovery decision: cpu_pressure_investigation
Recovery risk_level: medium
Recovery dry_run: True
```

展示压力场景报告：

```text
aiops_agent/outputs/diagnosis_report_cpu_stress.md
```

讲解重点：

- KPIRoot Top1 指标为 `cpu__paymentservice`。
- Prometheus 实时 CPU 指标超过 `recovery.cpu_pressure_threshold`。
- Agent 将恢复决策从 `observe` 改为 `cpu_pressure_investigation`。
- 报告中可能出现 `kubectl rollout restart` 命令草案，但明确标注为需人工确认后执行。

## 4. 删除故障

由演示者人工执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\delete_paymentservice_cpu_stress.ps1
```

等待 1 到 2 分钟，让服务和 Prometheus 指标恢复。

## 5. 恢复后再次运行 run_agent.py

再次运行：

```powershell
python aiops_agent\run_agent.py --config aiops_agent\config.json
```

重点观察：

```text
Kubernetes health_status: healthy
Prometheus service_cpu_rate: ...
Recovery decision: observe
```

展示恢复后报告：

```text
aiops_agent/outputs/diagnosis_report_recovered.md
```

讲解重点：

- CPU 压力解除后，实时指标下降。
- Agent 恢复建议回到 `observe`。
- 说明 Agent 的恢复建议会随在线证据变化。

## 6. 运行 veadk_agent.py fallback

无 API Key 或不希望调用外部模型时，运行：

```powershell
python aiops_agent\veadk_agent.py --config aiops_agent\config.json --alert "Online Boutique paymentservice CPU anomaly"
```

讲解重点：

- 这是 VeADK / LLM Agent 风格入口的 deterministic fallback。
- 不需要 API Key。
- 不调用外部 API。
- 仍然会复用本地完整诊断流程并生成报告。

## 7. 配置 API Key 后运行 veadk_agent.py --llm

如需展示火山方舟 OpenAI-compatible tool calling，先在 PowerShell 设置环境变量：

```powershell
$env:ARK_API_KEY="your_ark_api_key"
$env:ARK_MODEL="your_model_or_endpoint_id"
$env:ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
```

运行：

```powershell
python aiops_agent\veadk_agent.py --config aiops_agent\config.json --alert "Online Boutique paymentservice CPU anomaly" --llm
```

可展示：

```text
[Agent Tool Call] query_usad_result
[Agent Tool Call] query_kpiroot_result
[Agent Tool Call] query_kubernetes_evidence
[Agent Tool Call] query_prometheus_metrics
[Agent Tool Call] generate_recovery_plan
```

讲解重点：

- `--llm` 是显式开关，不加就不会调用外部模型。
- API Key 只从环境变量读取，不写入代码或 `config.json`。
- 工具结果传给 LLM 时只传摘要，不传完整 Kubernetes 日志。

## 8. dry-run 安全保护说明

演示最后强调：

- `agent.enable_recovery=false`。
- `recovery.execute_recovery=false`。
- `recovery.dry_run=true`。
- Agent 不执行 `kubectl delete`。
- Agent 不执行 `kubectl apply`。
- Agent 不执行 `kubectl rollout restart`。
- 恢复命令只作为人工复核草案展示。

## 9. 本地网页 Dashboard 演示流程

安装 Streamlit：

```powershell
pip install -r aiops_agent\requirements-dashboard.txt
```

启动本地网页控制台：

```powershell
streamlit run aiops_agent\dashboard_app.py
```

浏览器会打开本地 Streamlit 页面，标题为：

```text
AIOps Agent 智能运维控制台
```

推荐演示步骤：

1. 打开 Dashboard。
2. 可选：在左侧栏配置 LLM API，或不配置 API Key 直接使用本地规则模式。
3. 在“系统总览”Tab 点击“刷新当前状态”，展示 Kubernetes health_status、Prometheus available、CPU rate、memory working set、recovery decision 和 risk level。
4. 在“检测中心”Tab 选择“一次检测 + 本地规则模式”，点击“运行一次本地诊断”，观察正常状态下 decision 为 `observe`。
5. 在“故障注入”Tab 设置 Service、Duration、CPU Load、Workers，点击“注入 CPU 压力”。注意该按钮会创建 ChaosMesh StressChaos 对象，只能在演示环境中使用。
6. 等待 30 到 60 秒。
7. 回到“检测中心”Tab，再次运行“一次检测 + 本地规则模式”，观察 recovery decision 变为 `cpu_pressure_investigation`。
8. 选择“自动巡检 + 本地规则模式”，设置 interval、max_rounds、cooldown 和 trigger_once，启动自动巡检，观察自动触发诊断并写入 `watch_history.csv`。
9. 如已配置 `ARK_API_KEY` / `ARK_MODEL`，选择“一次检测 + LLM 智能体模式”，观察 `[Agent Tool Call]` 输出和最终诊断结论。
10. 可选展示“自动巡检 + LLM 智能体模式”，超过阈值后会先运行本地诊断，再保存 LLM 输出摘要。
11. 在“故障注入”Tab 点击“删除 CPU 压力”，删除 ChaosMesh StressChaos 对象。
12. 等待 1 到 2 分钟后再次运行诊断，观察 decision 回到 `observe`。

Dashboard 中的故障注入按钮会修改 ChaosMesh 实验对象，但不会执行服务重启；Agent 恢复动作仍然是 dry-run。

Dashboard 已优化为适合演示的宽屏布局。系统名、namespace、服务名、状态值和报告路径使用可换行卡片展示，截图时不会被省略为 `Online Bouti...` 或 `paymen...`。

自动巡检推荐演示参数：

- interval：5
- max_rounds：3
- cooldown：60
- trigger_once：True

自动巡检运行时，Streamlit 页面右上角可能出现 Stop，这是 Streamlit 正在运行子进程的正常提示，不代表程序错误。等待 `watch_agent.py` 执行结束后，页面会一次性展示输出。

Dashboard 页面结构：

- Tab 1：系统总览。
- Tab 2：故障注入。
- Tab 3：检测中心。
- Tab 4：自动巡检日志。
- Tab 5：报告中心。
- Tab 6：端到端实时流水线。

演示前建议进入“自动巡检日志”Tab：

1. 如已有旧记录，点击“归档当前日志”，保存为 `watch_history_archive_YYYYMMDD_HHMMSS.csv`。
2. 如需干净截图，再点击“清空当前日志”。
3. 也可以勾选“归档后清空当前日志”，一次完成归档和清空。

清空日志只会删除 `watch_history.csv`，不会删除 baseline、cpu_stress、recovered、llm_cpu_stress、auto_diagnosis 或 llm_diagnosis 文件。

检测中心的二维组合：

- 一次检测 + 本地规则模式。
- 一次检测 + LLM 智能体模式。
- 自动巡检 + 本地规则模式。
- 自动巡检 + LLM 智能体模式。

左侧栏 LLM API 设置只把 API Key 保存到当前 Streamlit 会话，不写入任何文件；也可以继续使用系统环境变量 `ARK_API_KEY` / `ARK_MODEL`。

## 10. 自动巡检演示流程

自动巡检入口：

```powershell
python aiops_agent\watch_agent.py --config aiops_agent\config.json --interval 30 --max-rounds 10
```

演示说明：

- `watch_agent.py` 会定时查询 Prometheus 中 Top1 服务的 CPU rate。
- 当 CPU rate 超过 `recovery.cpu_pressure_threshold` 时，会自动运行一次完整诊断。
- 生成的报告会归档为 `aiops_agent/outputs/auto_diagnosis_YYYYMMDD_HHMMSS.md`。
- `--cooldown 60` 表示触发一次诊断后 60 秒内不重复触发。
- `--trigger-once` 表示检测到一次异常并完成诊断后退出。
- `--history-file aiops_agent\outputs\watch_history.csv` 可指定巡检历史 CSV。
- 如果显式添加 `--llm` 且本机配置了 `ARK_API_KEY` 和 `ARK_MODEL`，异常触发后还会运行 `veadk_agent.py --llm`，并保存摘要到 `llm_diagnosis_YYYYMMDD_HHMMSS.txt`。
- 自动巡检不执行真实恢复命令。
- `watch_history.csv` 是持久化日志，可在 Dashboard 中归档或清空。

## 11. 端到端实时流水线演示流程

命令行 dry-run：

```powershell
python aiops_agent\realtime_pipeline_agent.py --config aiops_agent\config.json --duration-minutes 5 --step-seconds 15 --dry-run
```

Dashboard 演示：

1. 打开“端到端实时流水线”Tab。
2. 设置 `duration_minutes=5`、`step_seconds=15`。
3. 保持 `dry_run=True`、`execute_external=False`。
4. 点击“仅采集实时 Prometheus 数据”，生成 `prometheus_realtime_*.csv`。
5. 点击“构建 USAD/KPIRoot 输入”，生成 `usad_input_*.csv`、`kpiroot_input_*.csv` 和 KPIRoot phase2 runtime 目录。
6. 点击“运行实时 AIOps 流水线”，展示 pipeline 输出和 `realtime_pipeline_report_*.md`。
7. 点击“查看最新 pipeline report”，展示本次流水线报告。

说明：

- dry-run 不会真正运行 external_projects 中 USAD/KPIRoot。
- execute USAD only、execute KPIRoot only、execute USAD + KPIRoot 只有在明确选择并二次确认后才会尝试运行外部项目。
- 当前仍需组员确认 USAD/KPIRoot 的实时输入格式后，再建议开启 execute-external。
- 实时流水线不执行真实恢复命令。

低成本真实执行建议：

1. 先运行 dry-run。
2. 再运行：

```powershell
python aiops_agent\realtime_pipeline_agent.py --config aiops_agent\config.json --duration-minutes 5 --step-seconds 15 --execute-usad-only --usad-epochs 1 --usad-window 5 --usad-train-ratio 0.7
```

3. 再考虑：

```powershell
python aiops_agent\realtime_pipeline_agent.py --config aiops_agent\config.json --duration-minutes 5 --step-seconds 15 --execute-kpiroot-only --kpiroot-scenario realtime-paymentservice-cpu --kpiroot-alarm paymentservice
```

所有输出都写入 `aiops_agent/runtime_outputs`，不会覆盖 `external_projects` 原始输出。
# 多类型故障实验演示补充

推荐演示顺序：

1. 在 Dashboard 打开“故障实验中心”。
2. 选择目标服务，默认推荐 `paymentservice`。
3. 选择 `CPU 压力故障（已验证）`，保持 `Duration=2m`、`CPU Load=80`、`Workers=1`，点击“注入故障”。
4. 等待 30 到 60 秒，在“检测中心”或“端到端实时流水线”运行诊断，观察 `recovery decision` 变为 `cpu_pressure_investigation`。
5. 点击“清理故障”，等待服务恢复后再次诊断，观察 decision 回到 `observe`。
6. 可切换到 `内存压力故障（实验性）`、`Pod Kill 故障（实验性）` 或 `网络延迟故障（待扩展）` 展示框架能力，但需要说明这些场景的端到端算法解释仍需校准。

命令行示例：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\apply_fault.ps1 -FaultType memory_stress -Service paymentservice -Duration 2m -MemorySize 128MB -Workers 1
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\delete_fault.ps1 -FaultType memory_stress -Service paymentservice
```

安全口径：故障注入只由用户手动点击或手动执行脚本触发；Agent 只生成 dry-run 恢复建议，不自动重启服务，不执行 `kubectl rollout restart`。
# 最终推荐演示流程补充

1. 打开 Dashboard，先展示“系统总览”，说明 Online Boutique、Prometheus、USAD、KPIRoot、Agent 和 dry-run 恢复保护均已接入。
2. 进入“实时故障实验”，选择 `paymentservice` 和 `CPU 压力故障（已完整验证）`。
3. 手动点击“注入故障”，等待故障窗口产生实时指标。
4. 进入“端到端 AIOps 诊断”，选择 `execute USAD + KPIRoot（推荐演示）`，确认安全提示后运行。
5. 展示流程状态卡片、Prometheus CSV、USAD input、KPIRoot input、Pipeline report、diagnosis_report 和 recovery decision。
6. 进入“结果与报告中心”，分别展示 Agent 诊断报告、端到端 AIOps report、USAD runtime 输出和 KPIRoot runtime 输出。
7. 回到“实时故障实验”清理故障。
8. 再运行一次端到端诊断，确认恢复后 decision 回到 `observe`。

旧的本地规则一次检测、LLM fallback 和自动巡检仍可在“高级工具”中展示，但不再作为主线。
