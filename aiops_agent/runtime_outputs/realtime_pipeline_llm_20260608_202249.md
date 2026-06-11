# LLM 智能诊断总结

## 1. 结论

当前 paymentservice 存在 CPU 压力异常，建议进入 CPU 压力排查。恢复动作保持 dry-run，未执行真实恢复命令。

## 2. 关键证据

- data_source_mode: `realtime_runtime`
- execute_mode: `execute_usad_kpiroot`
- Prometheus service_cpu_rate: `0.19992530323045513`
- USAD has_anomaly: `True`
- USAD anomaly_windows: `1`
- USAD max_anomaly_score: `260281.05532229732`
- KPIRoot top_service: `paymentservice`
- KPIRoot top_metric: `cpu__paymentservice`
- Kubernetes health_status: `healthy`
- recovery_decision: `cpu_pressure_investigation`
- risk_level: `medium`

## 3. 根因分析

Prometheus 当前 service_cpu_rate=0.19992530323045513，超过 CPU 压力阈值或表现出明显升高；USAD 检测到异常窗口，KPIRoot 将 Top1 根因定位到 `cpu__paymentservice`，对应服务 `paymentservice`。因此本次更符合 paymentservice CPU 压力故障。

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
Final Agent Diagnosis:
LLM API call failed: 'gbk' codec can't encode character '\u2705' in position 64: illegal multibyte sequence. Running deterministic fallback diagnosis.
Fallback diagnosis completed.
{
  "has_anomaly": true,
  "top_service": "paymentservice",
  "top_metric": "cpu__paymentservice",
  "kubernetes_health_status": "healthy",
  "prometheus_available": true,
  "service_cpu_rate": 0.19982511825922417,
  "service_memory_working_set_mib": 54.1875,
  "recovery_decision": "cpu_pressure_investigation",
  "recovery_risk_level": "medium",
  "dry_run": true,
  "report_path": "D:\\software-test-final-aiops\\aiops_agent\\outputs\\diagnosis_report.md"
}
```
