# AIOps Agent Fault-Injection Test Plan

本测试计划用于验证 Agent 在 `paymentservice` CPU 压力异常时，是否能根据 Prometheus 实时指标改变恢复建议。

注意：本文档只描述测试流程。不要在未确认环境和风险前执行 Chaos 注入。

## 1. Baseline 正常状态

运行：

```powershell
python aiops_agent\run_agent.py --config aiops_agent\config.json
```

预期：

```text
recovery decision = observe
```

可保存 baseline 报告：

```powershell
copy aiops_agent\outputs\diagnosis_report.md aiops_agent\outputs\diagnosis_report_baseline.md
```

## 2. 注入 CPU 压力

运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\apply_paymentservice_cpu_stress.ps1
```

该脚本会应用 `aiops_agent/chaos/paymentservice_cpu_stress.yaml`，对 `online-boutique` namespace 中 `app=paymentservice` 的 Pod 注入 2 分钟 CPU 压力。

## 3. 压力期间运行 Agent

等待 30 到 60 秒后运行：

```powershell
python aiops_agent\run_agent.py --config aiops_agent\config.json
```

预期：

```text
Prometheus service_cpu_rate 升高
recovery decision = cpu_pressure_investigation
```

保存压力场景报告：

```powershell
copy aiops_agent\outputs\diagnosis_report.md aiops_agent\outputs\diagnosis_report_cpu_stress.md
```

## 4. 删除故障

运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File aiops_agent\scripts\delete_paymentservice_cpu_stress.ps1
```

## 5. 恢复后再次运行

等待 1 到 2 分钟后运行：

```powershell
python aiops_agent\run_agent.py --config aiops_agent\config.json
```

预期：

```text
recovery decision = observe
```

保存恢复后报告：

```powershell
copy aiops_agent\outputs\diagnosis_report.md aiops_agent\outputs\diagnosis_report_recovered.md
```

## 6. 安全边界

- Agent 的恢复动作仍为 dry-run。
- `kubectl rollout restart` 只会作为报告中的命令草案出现，不会由 Agent 自动执行。
- Chaos apply/delete 脚本需要人工主动运行。
- 不要修改 `external_projects` 中同学项目。
