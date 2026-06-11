# 截图检查清单

建议在最终汇报材料中准备以下截图。截图前注意不要展示完整 API Key、本机 kubeconfig 或其他敏感信息。

## 基础环境截图

- Online Boutique 前端页面，证明系统可访问。
- `online-boutique` namespace 中 Pod 全部 Running。
- `paymentservice` Pod、Deployment、Service 状态。
- Prometheus 查询可用性，例如 `up` 或 paymentservice CPU 指标查询结果。

## Baseline 正常状态截图

- baseline 运行 `python aiops_agent\run_agent.py --config aiops_agent\config.json` 的终端输出。
- 终端中 `Kubernetes health_status: healthy`。
- 终端中 `Recovery decision: observe`。
- `diagnosis_report_baseline.md` 的基本信息、USAD、KPIRoot、Prometheus 和恢复建议章节。

## CPU Stress 故障注入截图

- ChaosMesh `paymentservice-cpu-stress` 注入成功。
- `kubectl get stresschaos -n chaos-testing` 输出。
- CPU stress 期间 Agent 运行输出。
- 终端中 `Prometheus service_cpu_rate` 升高。
- 终端中 `Recovery decision: cpu_pressure_investigation`。
- `diagnosis_report_cpu_stress.md` 中 Prometheus 实时指标证据章节。
- `diagnosis_report_cpu_stress.md` 中“恢复建议与执行保护”章节。

## Recovered 恢复后截图

- 删除 ChaosMesh 故障后，Pod 仍为 Running。
- recovered 运行 `run_agent.py` 的终端输出。
- 终端中 `Recovery decision: observe`。
- `diagnosis_report_recovered.md` 的恢复建议章节。

## 报告关键章节截图

- `# AIOps Agent 智能运维诊断报告` 标题。
- “异常检测结果（USAD）”章节。
- “根因定位结果（KPIRoot）”章节。
- “Kubernetes 运行证据”章节。
- “Prometheus 实时指标证据”章节。
- “Agent 综合诊断”章节。
- “恢复建议与执行保护”章节。
- “当前版本局限”章节。

## VeADK / 火山方舟截图

- `veadk_agent.py` deterministic fallback 运行输出。
- 火山方舟 `--llm` 模式启动输出。
- `[Agent Tool Call] ...` 工具调用输出。
- LLM 最终诊断结论输出。
- `diagnosis_report_llm_cpu_stress.md` 或对应 LLM 场景报告。

## Dashboard 截图

- Streamlit 页面标题“AIOps Agent 智能运维控制台”。
- 左侧栏“LLM API 设置”，只展示 `ARK_API_KEY detected: True/False`、`ARK_MODEL` 和 `ARK_BASE_URL`，不要展示完整 API Key。
- Tab 1“系统总览”：系统名、namespace、hybrid 模式、dry-run、当前服务和状态摘要。确认 `Online Boutique`、`online-boutique`、`paymentservice` 完整显示，没有省略号。
- Tab 2“故障注入”：Service、Duration、CPU Load、Workers 自定义参数，以及红色安全提示。
- Tab 3“检测中心”：检测方式和执行模式二维选择。
- “一次检测 + 本地规则模式”输出。
- “一次检测 + LLM 智能体模式”输出。
- “自动巡检 + 本地规则模式”输出和 auto_diagnosis 报告路径。可截取自动巡检运行提示，说明右上角 Stop 是 Streamlit 正在执行任务的正常提示。
- “自动巡检 + LLM 智能体模式”输出和 llm_diagnosis 文本路径。
- Tab 4“自动巡检日志”：`watch_history.csv` 表格、triggered=true 记录、llm_enabled / llm_executed 字段。
- Tab 4 的日志管理按钮：刷新自动巡检日志、归档当前日志、清空当前日志。
- 归档成功提示，展示 `watch_history_archive_YYYYMMDD_HHMMSS.csv` 路径。
- 清空日志提示，说明不会删除诊断报告文件。
- Tab 5“报告中心”：报告 Markdown 内容、文件修改时间和文件大小，选择框显示文件名和修改时间。
- 检测中心输出区域：固定高度日志框、recovery decision、risk level、diagnosis_report 路径、auto_diagnosis 路径和 LLM 输出路径。
- Tab 6“端到端实时流水线”：duration_minutes、step_seconds、执行模式、USAD epochs/window/train ratio、KPIRoot scenario/alarm 参数区。
- Tab 6 中 Prometheus CSV 路径、USAD input 路径、KPIRoot input 路径。
- Tab 6 中 `realtime_pipeline_report_*.md` 展示区域。
- Tab 6 中 dry-run 提示，说明不会真正运行 external_projects。
- Tab 6 中 execute USAD only / execute KPIRoot only / execute USAD + KPIRoot 的安全提示，说明输出写入 `aiops_agent/runtime_outputs`。

## 安全截图提醒

- 不要截图完整 `ARK_API_KEY`。
- 不要截图完整 `OPENAI_API_KEY`。
- 不要截图本机 kubeconfig 内容。
- 如需展示环境变量，只展示变量名或遮挡中间内容，例如 `ARK_API_KEY=sk-****`。
- 不要展示完整支付相关日志字段；报告日志已脱敏，但仍建议检查截图内容。
- 不要截图 `.env` 或任何包含密钥的终端历史。
# 多类型故障实验截图补充

- Dashboard “故障实验中心”中故障类型下拉框，展示 CPU、内存、Pod Kill、网络延迟四种类型。
- CPU 压力故障参数区：Duration、CPU Load、Workers。
- 内存压力故障参数区：Memory Size 默认 `128MB`，并显示实验性提示。
- Pod Kill 故障说明：只杀一个 Pod，不执行 Deployment scale 或 rollout restart。
- 网络延迟故障说明：当前缺少 latency/error rate 指标，需要后续扩展。
- “故障实验中心”的红色安全提示：故障注入会修改 ChaosMesh 实验对象，但恢复动作仍为 dry-run。
- 诊断报告中的“故障实验上下文”章节，展示 `fault_type`、`target_service`、`fault_status`、检测依据和局限。
- Kubernetes 运行证据中 Pod restart count、Pod ready、Pod phase、Deployment available 字段。
# Dashboard 最终六 Tab 截图补充

- 顶部六个 Tab：系统总览、实时故障实验、端到端 AIOps 诊断、结果与报告中心、高级工具、项目架构说明。
- 系统总览中的能力摘要卡片：ChaosMesh、Prometheus、USAD、KPIRoot、Agent、LLM、dry-run。
- 实时故障实验中推荐目标 `paymentservice` 和 CPU 压力故障已完整验证提示。
- 端到端 AIOps 诊断中执行模式下拉框，尤其是 `execute USAD + KPIRoot（推荐演示）`。
- 端到端 AIOps 诊断运行后的流程状态卡片和 `data_source_mode`。
- 结果与报告中心的五类分组：Agent 诊断报告、自动巡检报告与日志、端到端 AIOps 报告、USAD 实时输出、KPIRoot 实时输出。
- 高级工具中的兼容说明，证明离线读取方案已弱化为调试入口。
- 项目架构说明中的完整主流程。
