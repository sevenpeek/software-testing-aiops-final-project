# 打包与交付指南

本文档说明将项目发给组员或提交作业时建议包含和排除的内容。

## 建议包含的文件

核心 Agent 目录：

```text
aiops_agent/
```

建议保留：

- `aiops_agent/config.json`
- `aiops_agent/run_agent.py`
- `aiops_agent/veadk_agent.py`
- `aiops_agent/tools/`
- `aiops_agent/scripts/`
- `aiops_agent/chaos/`
- `aiops_agent/k8s/`
- `aiops_agent/docs/`
- `aiops_agent/README.md`
- `aiops_agent/requirements-veadk.txt`
- `aiops_agent/outputs/diagnosis_report_baseline.md`
- `aiops_agent/outputs/diagnosis_report_cpu_stress.md`
- `aiops_agent/outputs/diagnosis_report_recovered.md`
- `aiops_agent/outputs/diagnosis_report_llm_cpu_stress.md`，如已生成。

组员论文复现输出：

```text
external_projects/usad_anomaly_detection/outputs_online_boutique_real/
external_projects/usad_anomaly_detection/outputs_online_boutique_chaosmesh/
external_projects/kpiroot_fault_diagnosis/data/phase4/kpiroot/
```

如果组员要直接运行 Agent，需要保留 USAD 和 KPIRoot 的关键输出文件：

- USAD `anomaly_scores.csv`
- USAD `metrics_summary.txt`
- KPIRoot `summary.csv`
- KPIRoot `ablation_summary.csv`
- KPIRoot 各场景 `ranking.csv`
- KPIRoot 各场景 `summary.json`

## 不要包含的文件

不要打包任何 API Key 或本机凭据：

- 不要包含写有 `ARK_API_KEY` 的文件。
- 不要包含写有 `OPENAI_API_KEY` 的文件。
- 不要包含 `.env`，除非确认里面没有真实密钥。
- 不要包含本机 kubeconfig，例如 `C:\Users\<user>\.kube\config`。

不要打包本地运行环境和缓存：

- 不要包含虚拟环境目录，例如 `.venv/`、`venv/`。
- 不要包含 `__pycache__/`。
- 不要包含 `.pytest_cache/`。
- 不要包含 IDE 缓存目录。
- 不要包含临时下载文件。

不要包含会暴露个人环境的信息：

- 本机绝对路径截图。
- 未脱敏日志。
- 完整 API Key。
- 个人代理配置。

## 推荐打包方式

推荐从项目根目录打包，保留项目相对路径结构。这样 `config.json` 中的相对路径可以继续工作。

建议打包前检查：

```powershell
Get-ChildItem aiops_agent -Recurse -Directory -Filter __pycache__
Get-ChildItem aiops_agent -Recurse -Include *.pyc
```

如果需要清理缓存，可以手动删除 `__pycache__` 和 `.pyc` 文件，但不要删除 `external_projects` 中同学项目的关键输出。

## 组员运行前检查

组员如果只查看报告，不需要 Kubernetes、Prometheus、ChaosMesh 或 API Key。

组员如果要运行完整 hybrid Agent，需要准备：

- Python 环境。
- `external_projects` 中 USAD / KPIRoot 关键输出文件。
- 可用的 `kubectl`。
- 已部署的 Online Boutique。
- 可访问的 Prometheus。

组员如果要运行 LLM tool calling，需要额外设置：

- `ARK_API_KEY`
- `ARK_MODEL`
- 可选 `ARK_BASE_URL`

API Key 只通过环境变量设置，不要写入代码、README 示例以外的真实配置或 `config.json`。
