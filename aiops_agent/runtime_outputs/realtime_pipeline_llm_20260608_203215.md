# LLM 智能诊断总结

## 1. 结论

当前 paymentservice 存在 CPU 压力异常，建议进入 CPU 压力排查。恢复动作保持 dry-run，未执行真实恢复命令。

## 2. 关键证据

- data_source_mode: `realtime_runtime`
- execute_mode: `execute_usad_kpiroot`
- Prometheus service_cpu_rate: `0.08196149604283051`
- USAD has_anomaly: `True`
- USAD anomaly_windows: `1`
- USAD max_anomaly_score: `2.092640141755246`
- KPIRoot top_service: `paymentservice`
- KPIRoot top_metric: `cpu__paymentservice`
- Kubernetes health_status: `healthy`
- recovery_decision: `cpu_pressure_investigation`
- risk_level: `medium`

## 3. 根因分析

Prometheus 当前 service_cpu_rate=0.08196149604283051，超过 CPU 压力阈值或表现出明显升高；USAD 检测到异常窗口，KPIRoot 将 Top1 根因定位到 `cpu__paymentservice`，对应服务 `paymentservice`。因此本次更符合 paymentservice CPU 压力故障。

## 4. 建议动作

- 保留 USAD、KPIRoot、Pipeline 和 Agent 诊断报告，作为本次故障实验证据。
- 查看 `paymentservice` 近期变更、日志和 Kubernetes Event。
- 检查流量峰值、资源 request/limit，以及是否存在资源竞争。
- 必要时由人工确认后再考虑重启、扩容或调整资源配置。
- 系统不会自动执行 `kubectl rollout restart`。

## 5. 安全说明

- external_projects 原始输出未被覆盖。
- 本次优先使用 `aiops_agent/runtime_outputs` 中的实时结果；如输出缺失，Pipeline report 会标注 fallback。
- 恢复动作保持 dry-run。
- API Key 只通过环境变量或当前会话传入，不写入总结文件。

## LLM 调用信息

- llm_mode: `volcengine_ark`
- llm_warning: `N/A`

## 原始 LLM / Agent 输出摘录

```text
ARK_API_KEY detected. Using Volcengine Ark OpenAI-compatible mode.
[Agent Tool Call] run_full_diagnosis
[Agent Tool Call] query_usad_result
[Agent Tool Call] query_kpiroot_result
[Agent Tool Call] query_kubernetes_evidence
[Agent Tool Call] query_prometheus_metrics
[Agent Tool Call] generate_recovery_plan
Final Agent Diagnosis:
# Realtime Online Boutique Anomaly Pipeline Diagnosis Result
## 1. Overall Anomaly Summary
- Anomaly detected: **Yes**
- Top affected service: `paymentservice`
- Top anomalous metric: `cpu__paymentservice`
- Global Kubernetes cluster health status: **Healthy**
- Recovery decision type: `cpu_pressure_investigation`
- Recovery risk level: Medium (all operations run in dry-run mode, no real mutation executed)

## 2. USAD Anomaly Detection Output
- Total anomaly windows found: 1
- Max anomaly score: 2.0926
- Alert threshold: 2.0887
- The anomaly score slightly exceeds the predefined threshold, confirming the existence of an abnormal deviation from normal baseline patterns. No extra warnings detected.

## 3. KPIRoot Root Cause Ranking Output
- Top root cause service: `paymentservice`
- Top root cause metric: `cpu__paymentservice`
- Root cause confidence score: 0.9 (very high correlation)
The root cause analysis confirms that the abnormal CPU usage of the paymentservice is the primary driver of the detected anomaly.

## 4. Kubernetes Evidence Check for paymentservice
- No warning events found for the paymentservice pods/deployments
- Kubernetes runtime status is healthy, no crash loops, pod evictions or scheduling abnormalities detected.

## 5. Prometheus Metrics for paymentservice
- Current service CPU usage rate: ~19.8% (far above the 5% CPU pressure threshold)
- Current service memory working set: 53.56 MiB (well below the 150 MiB memory pressure threshold, memory usage is normal)
- Total running containers for paymentservice: 1
The metrics confirm that the anomaly is specifically related to elevated CPU pressure, not memory issues.

## 6. Dry-Run Recovery Plan
All actions below are only recommended drafts, no automatic recovery will be executed, manual confirmation is required before any real operation:
1. First, further inspect the paymentservice runtime logs, pod detailed CPU profiling data to confirm the root cause of unexpected CPU elevation
2. Verify if there are unexpected business request spikes, infinite loops, or inefficient code paths leading to the higher CPU usage
3. If CPU pressure persists after investigation, you can consider manually scaling the paymentservice replicas or restarting the pod after full confirmation.
### Safety Notes
- The whole pipeline runs in dry-run mode, no Kubernetes mutation operations are triggered
- All restart/scale commands are displayed only as reference suggestions
- Current memory usage is completely normal, no memory-related actions are needed.

Full diagnosis report file path: `D:\software-test-final-aiops\aiops_agent\outputs\diagnosis_report.md`
```
