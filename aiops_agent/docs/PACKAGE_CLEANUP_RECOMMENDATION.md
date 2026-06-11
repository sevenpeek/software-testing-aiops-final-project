# Package Cleanup Recommendation

本文档用于项目交接和打包前清点。当前仅给出清理建议，不执行任何删除、移动、压缩或集群操作。

## 1. 项目核心目录说明

项目根目录主要包含：

- `aiops_agent/`：本人实现的端到端实时 AIOps Agent、Dashboard、工具脚本、文档和运行产物，是最终交付核心目录。
- `external_projects/`：组员提供的 USAD 异常检测项目和 KPIRoot 根因定位项目，是实时重跑和离线 fallback 的算法来源。
- `references/`：老师教程和 Agent 教程，适合作为答辩背景资料保留。
- `third_party/`：第三方依赖或参考材料，是否随包发送取决于组内约定。
- `docs/`、`outputs/`、`archives/`：根目录级历史材料，建议打包前人工确认用途。

`aiops_agent/` 内部核心结构：

- `dashboard_app.py`：Streamlit 本地 Web 控制台主入口。
- `realtime_pipeline_agent.py`：端到端实时 AIOps 流水线入口。
- `run_agent.py`：兼容旧版规则编排诊断入口。
- `veadk_agent.py`：VeADK / 火山方舟 / OpenAI-compatible LLM Agent 封装入口。
- `watch_agent.py`：自动巡检入口。
- `tools/`：USAD、KPIRoot、Kubernetes、Prometheus、Recovery、Report、Chaos、Realtime pipeline 工具实现。
- `scripts/`：Online Boutique 部署检查脚本、ChaosMesh 故障注入/清理脚本。
- `chaos/`：固定和 runtime ChaosMesh YAML。
- `docs/`：项目说明、演示脚本、截图清单、打包说明。
- `outputs/`：Agent 诊断报告、baseline/cpu/recovered/LLM 示例报告、自动巡检报告。
- `runtime_data/`：Prometheus 实时采集数据、USAD/KPIRoot runtime 输入、KPIRoot phase2 runtime 输入。
- `runtime_outputs/`：实时重跑 USAD/KPIRoot 输出、pipeline report、LLM 总结、runtime_config。

## 2. 必须保留的文件和目录

建议交接包必须保留：

- `aiops_agent/config.json`
- `aiops_agent/dashboard_app.py`
- `aiops_agent/realtime_pipeline_agent.py`
- `aiops_agent/run_agent.py`
- `aiops_agent/veadk_agent.py`
- `aiops_agent/watch_agent.py`
- `aiops_agent/tools/`
- `aiops_agent/scripts/`
- `aiops_agent/chaos/paymentservice_cpu_stress.yaml`
- `aiops_agent/chaos/generated/` 中最新 runtime YAML 可作为示例保留
- `aiops_agent/k8s/`
- `aiops_agent/docs/`
- `aiops_agent/README.md`
- `aiops_agent/requirements-dashboard.txt`
- `aiops_agent/requirements-veadk.txt`

如果接收方需要直接运行端到端实时 AIOps，还应保留：

- `external_projects/usad_anomaly_detection/`
- `external_projects/kpiroot_fault_diagnosis/`

如果只做代码审阅或展示截图，可以不把完整 `runtime_data/` 和 `runtime_outputs/` 全量发送，但建议保留一组成功示例输出。

## 3. 可删除的缓存文件

发现以下缓存类内容，可在确认后删除：

- `aiops_agent/__pycache__/`
- `aiops_agent/tools/__pycache__/`
- `external_projects/kpiroot_fault_diagnosis/src/kpiroot/__pycache__/`
- `external_projects/usad_anomaly_detection/src/__pycache__/`
- `*.pyc` 文件

注意：本次未执行删除。若要清理，建议只在打包副本中清理，不直接动同学的 `external_projects` 原件。

未发现 `.pytest_cache`。

## 4. 建议归档的运行产物

当前运行产物数量较多：

- `aiops_agent/runtime_data/`：约 102 个文件，包含多轮 Prometheus CSV、USAD input、KPIRoot input 和 metadata。
- `aiops_agent/runtime_outputs/`：约 249 个文件，包含多轮 USAD/KPIRoot runtime 输出、pipeline report、LLM summary。
- `aiops_agent/outputs/`：约 15 个报告文件，包含多轮自动巡检报告。

建议：

1. 打包前先复制一组成功端到端输出到 `aiops_agent/examples/` 或单独压缩包，例如 `examples/realtime_cpu_success/`。
2. 保留最新成功演示链路对应的：
   - `prometheus_realtime_*.csv`
   - `usad_input_*.csv`
   - `kpiroot_input_*.csv`
   - `usad_realtime_*`
   - `kpiroot_realtime_*`
   - `realtime_pipeline_report_*.md`
   - `realtime_pipeline_llm_*.md`
   - `diagnosis_report.md`
3. 其余早期多轮历史运行产物建议归档或在打包副本中清理。

不建议直接删除最新成功演示用输出，尤其是：

- 最新 `realtime_pipeline_report_*.md`
- 最新 `realtime_pipeline_llm_*.md`
- 最新 `usad_realtime_*`
- 最新 `kpiroot_realtime_*`
- 最新 `runtime_config.json`

## 5. 建议保留的示例输出

建议保留以下报告作为演示对照：

- `aiops_agent/outputs/diagnosis_report.md`
- `aiops_agent/outputs/diagnosis_report_baseline.md`
- `aiops_agent/outputs/diagnosis_report_cpu_stress.md`
- `aiops_agent/outputs/diagnosis_report_recovered.md`
- `aiops_agent/outputs/diagnosis_report_llm_cpu_stress.md`

建议保留一组最新端到端 realtime 示例：

- `aiops_agent/runtime_outputs/realtime_pipeline_report_20260608_203515.md`
- `aiops_agent/runtime_outputs/usad_realtime_20260608_203518/`
- `aiops_agent/runtime_outputs/kpiroot_realtime_20260608_203519/`
- `aiops_agent/runtime_data/prometheus_realtime_20260608_203515.csv`
- `aiops_agent/runtime_data/usad_input_20260608_203518.csv`
- `aiops_agent/runtime_data/kpiroot_input_20260608_203518.csv`

建议保留一份 LLM 总结示例：

- `aiops_agent/runtime_outputs/realtime_pipeline_llm_20260608_203215.md`

如果要展示“LLM 输出过短后自动 fallback 总结”的演进，也可保留：

- `aiops_agent/runtime_outputs/realtime_pipeline_llm_20260608_200842.txt`

但该旧 txt 文件只适合说明问题来源，不适合作为最终演示主输出。

## 6. API Key 泄露风险检查

本次只做路径级扫描，不打印匹配内容，避免泄露敏感信息。

检查结论：

- 未发现 `.env`。
- 未发现 `secrets.toml`。
- 未发现明显以敏感文件名保存的 token/credential/key 文件。
- 多个源码和文档中出现 `ARK_API_KEY`、`OPENAI_API_KEY`、`api_key` 字样，属于环境变量名称、示例说明或检测状态说明。
- `runtime_outputs/realtime_pipeline_llm_*.md/.txt` 中出现 `ARK_API_KEY detected` 之类状态文本，表示检测到环境变量，不应包含完整 Key。
- `SCREENSHOT_CHECKLIST.md` 中存在类似 `sk-****` 的遮罩示例，建议保留为安全提醒。

打包前仍建议人工复查：

- 不要包含真实 API Key。
- 不要包含 `.env`、PowerShell 历史、终端截图中的完整 Key。
- 不要包含本机 kubeconfig。
- 不要把 `ARK_API_KEY`、`OPENAI_API_KEY` 的真实值写入 `config.json`、README 或报告。

## 7. 打包前检查清单

- [ ] 确认 `aiops_agent/config.json` 中没有 API Key。
- [ ] 确认 `aiops_agent/README.md` 和 `aiops_agent/docs/` 中只有示例变量名，没有真实 Key。
- [ ] 确认 `runtime_outputs/realtime_pipeline_llm_*.md/.txt` 没有完整 API Key。
- [ ] 清理或排除 `__pycache__/` 和 `*.pyc`。
- [ ] 如需瘦身，归档旧的 `auto_diagnosis_*.md`。
- [ ] 如需瘦身，归档旧的 `runtime_data/prometheus_realtime_*`、`usad_input_*`、`kpiroot_input_*`。
- [ ] 如需瘦身，归档旧的 `runtime_outputs/usad_realtime_*`、`kpiroot_realtime_*`、`realtime_pipeline_report_*`。
- [ ] 保留一组成功 CPU 压力端到端示例输出。
- [ ] 保留 baseline / cpu_stress / recovered / llm_cpu_stress 示例报告。
- [ ] 确认是否需要把 `external_projects/` 一并发送。
- [ ] 确认不要包含本机 kubeconfig、虚拟环境、依赖缓存和 IDE 临时目录。

## 8. 发给同学时的目录结构建议

推荐完整交接包结构：

```text
software-test-final-aiops/
  aiops_agent/
    README.md
    config.json
    dashboard_app.py
    realtime_pipeline_agent.py
    run_agent.py
    veadk_agent.py
    watch_agent.py
    tools/
    scripts/
    chaos/
    k8s/
    docs/
    outputs/
    runtime_data/        # 可只保留一组示例
    runtime_outputs/     # 可只保留一组示例
  external_projects/
    usad_anomaly_detection/
    kpiroot_fault_diagnosis/
  references/            # 可选
```

瘦身交接包结构：

```text
software-test-final-aiops/
  aiops_agent/
    源码 + docs + scripts + chaos + k8s
    outputs/             # 仅保留代表性报告
    runtime_data/         # 仅保留最新一组输入
    runtime_outputs/      # 仅保留最新一组 USAD/KPIRoot/Pipeline/LLM 输出
  external_projects/      # 如接收方需运行算法，必须保留
```

## 9. external_projects 是否必须随包发送

建议随包发送 `external_projects`，原因：

- 端到端实时 AIOps 的 execute 模式需要调用 USAD 和 KPIRoot 项目代码。
- `aiops_agent` 的 runtime_config 和 fallback 逻辑仍需要读取已有 USAD/KPIRoot 输出。
- 老师或同学复现实验时，需要看到组员论文复现项目与 Agent 编排层的关系。

如果包太大，可以做两种版本：

1. 完整运行版：包含 `external_projects`，可真实重跑 USAD/KPIRoot。
2. 展示精简版：只包含 `aiops_agent` 和一组示例 runtime 输出，用于看 Dashboard、报告和代码结构。

不要删除 `external_projects` 原目录。若要瘦身，建议复制到单独打包目录后再清理缓存。

## 10. runtime_data / runtime_outputs / outputs 处理建议

`runtime_data/`：

- 作用：保存 Prometheus 实时采集 CSV、USAD input、KPIRoot input、metadata、KPIRoot phase2 runtime 输入。
- 建议：保留最新一组成功 CPU 压力实验数据；历史多轮数据可归档或在打包副本中删除。

`runtime_outputs/`：

- 作用：保存 USAD 实时输出、KPIRoot 实时输出、pipeline report、LLM summary、runtime_config。
- 建议：保留最新成功的 `usad_realtime_*`、`kpiroot_realtime_*`、`realtime_pipeline_report_*.md`、`realtime_pipeline_llm_*.md`。
- 其余历史多轮输出可归档，避免交接包过大和 Dashboard 下拉框过长。

`outputs/`：

- 作用：保存 Agent 诊断报告、baseline/cpu/recovered/LLM 示例报告、自动巡检报告。
- 建议：保留 `diagnosis_report.md` 和四个命名示例报告。
- 多个 `auto_diagnosis_*.md` 可归档或只保留最新 1 到 2 个。

## 11. 本次发现的可清理内容摘要

可清理但本次未删除：

- Python 缓存目录：`__pycache__/`
- Python 编译文件：`*.pyc`
- 多轮历史 `auto_diagnosis_*.md`
- 多轮历史 `prometheus_realtime_*.csv` / `.meta.json`
- 多轮历史 `usad_input_*.csv`
- 多轮历史 `kpiroot_input_*.csv`
- 多轮历史 `realtime_dataset_*.meta.json`
- 多轮历史 `realtime_pipeline_report_*.md`
- 多轮历史 `usad_realtime_*`
- 多轮历史 `kpiroot_realtime_*`

建议先复制成功演示样例到 `examples/` 或归档包，再清理历史产物。

