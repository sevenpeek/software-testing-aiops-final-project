# USAD 微服务异常检测大作业

本项目用于完成“软件测试与维护（2026 年春）”大作业，论文选择：

> USAD: UnSupervised Anomaly Detection on Multivariate Time Series, KDD 2020.

项目在课程前四次实验工具链基础上重新组织实验流程、数据采集、故障注入、算法复现和结果分析。前四次实验的工具和环境可以复用，但本目录中的实验数据、运行证据和报告结论均为大作业独立生成。

## 当前实验口径

为了对齐第三档评分标准，本项目不再只停留在可控示例数据，而是形成了两层实验闭环：

- USAD 论文复现闭环：使用 `data/sample_kpi_metrics.csv` 作为可控示例 KPI 数据，验证 USAD 窗口化、训练、异常评分、阈值判定和重构误差解释流程。
- 第三档增强闭环：在 Minikube 中部署 Google Online Boutique 复杂开源微服务系统，并新增自研 `anomaly-detector` 与 `online-boutique-probe-exporter` 两个微服务，补充 Selenium、JMeter、Prometheus/Grafana 和 ChaosMesh 实证证据。

故障证据需要明确区分：

- Online Boutique 真实 KPI 数据采集阶段使用 `kubectl scale deployment/productcatalogservice --replicas=0` 制造可重复、可标注的故障窗口，然后恢复为 1 个副本。
- 后续验证阶段实际安装并执行 ChaosMesh `PodChaos`，证明故障注入工具链可用，证据保存在 `docs/`。

## 目录结构

- `src/generate_sample_data.py`：生成示例多变量 KPI 时间序列。
- `src/usad_numpy.py`：纯 NumPy 实现的轻量 USAD 复现模型。
- `src/run_usad.py`：训练、检测、评估与结果图生成入口。
- `src/export_prometheus.py`：从 Prometheus HTTP API 导出指标为 CSV。
- `src/collect_online_boutique_metrics.py`：采集 Online Boutique HTTP 与 Kubernetes API KPI，并执行 scale 故障窗口。
- `src/collect_online_boutique_chaosmesh_metrics.py`：执行 ChaosMesh PodChaos，同时采集 Online Boutique 真实 KPI。
- `src/build_report.py`：生成 Word 大作业报告。
- `services/anomaly-detector/`：自研 USAD 异常检测 HTTP 微服务。
- `services/online-boutique-probe-exporter/`：自研 Online Boutique 应用探针 Prometheus exporter。
- `k8s/`：自研微服务 Kubernetes 部署清单。
- `monitoring/lightweight-monitoring.yaml`：轻量 Prometheus/Grafana/kube-state-metrics 配置。
- `tests/selenium/`：Online Boutique UI 自动化测试脚本与运行入口。
- `tests/jmeter/`：Online Boutique 压力测试 `.jmx` 与运行入口。
- `scripts/chaos-online-boutique-productcatalog-podkill.yaml`：ChaosMesh PodChaos 实际注入配置。
- `outputs/`：示例数据 USAD 输出。
- `outputs_online_boutique_real/`：Online Boutique 真实 KPI USAD 输出。
- `outputs_online_boutique_chaosmesh/`：ChaosMesh 注入期间采集的真实 KPI USAD 输出。
- `outputs_selenium/`：Selenium 测试结果 JSON 与页面截图。
- `outputs_jmeter/`：JMeter `.jtl`、HTML 报告与摘要。
- `docs/`：部署、监控、测试、ChaosMesh 和截图证据。
- `report/`：Word/PDF 大作业报告。

## 快速运行 USAD 复现

在 `final_project` 目录下执行：

```powershell
python src/generate_sample_data.py --out data/sample_kpi_metrics.csv
python src/run_usad.py --input data/sample_kpi_metrics.csv --out outputs
```

若本机 Python 缺少依赖：

```powershell
pip install -r requirements.txt
```

输出包括：

- `outputs/anomaly_scores.csv`
- `outputs/metrics_summary.txt`
- `outputs/anomaly_score.png`
- `outputs/reconstruction_error.png`

## Online Boutique 真实 KPI 实验

真实 KPI 数据文件：

- `data/online_boutique_real_metrics.csv`

USAD 运行结果：

- `outputs_online_boutique_real/anomaly_scores.csv`
- `outputs_online_boutique_real/metrics_summary.txt`
- `outputs_online_boutique_real/anomaly_score.png`
- `outputs_online_boutique_real/reconstruction_error.png`

已记录结果：120 个采样点、15 个 KPI、窗口大小 6、Precision 0.6071、Recall 0.9714、F1 0.7473。

## ChaosMesh KPI 闭环补强

为了让阶段二和阶段四完全闭合，项目新增了直接使用 ChaosMesh PodChaos 的 KPI 采集入口：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_chaosmesh_kpi_usad.ps1
```

该脚本会采集 120 个 Online Boutique KPI 采样点，在第 45 个采样点执行 `scripts/chaos-online-boutique-productcatalog-podkill.yaml`，将第 45-74 个采样点标记为故障窗口，并自动运行 USAD。

核心产物：

- `data/online_boutique_chaosmesh_metrics.csv`
- `outputs_online_boutique_chaosmesh/anomaly_scores.csv`
- `outputs_online_boutique_chaosmesh/metrics_summary.txt`
- `outputs_online_boutique_chaosmesh/anomaly_score.png`
- `outputs_online_boutique_chaosmesh/reconstruction_error.png`
- `docs/chaosmesh_kpi_collection_evidence.md`

## Selenium 与 JMeter

Selenium 脚本位于：

```powershell
tests/selenium/online_boutique_ui_test.py
```

当前本机已完成基础 Chrome headless 验证，并补充 Edge 浏览器兼容性验证，覆盖首页、商品详情页和购物车页。Firefox 作为可选浏览器保留在多浏览器脚本参数中；若本机未安装，对应结果会标记为 failed，不影响已安装浏览器的结果。

`.tools/python_lib` 是为了本机运行 Selenium 临时安装的依赖缓存，不属于项目源码。最终打包提交时建议不包含 `.tools/`；需要复现 Selenium 时可执行：

```powershell
pip install -r tests/selenium/requirements.txt
```

JMeter 测试计划位于：

```powershell
tests/jmeter/online_boutique_load_test.jmx
```

已生成 HTML 报告与摘要：

- `outputs_jmeter/html/index.html`
- `outputs_jmeter/jmeter_summary.txt`
- `docs/screenshots/jmeter_online_boutique_report.png`

本次 JMeter 结果为 240 samples、错误率 0.00%、平均响应时间 15.83 ms。

新增 10/30/50 并发对比脚本：

```powershell
$env:JMETER_HOME='D:\path\to\apache-jmeter-5.6.3'
powershell -ExecutionPolicy Bypass -File tests/jmeter/run_jmeter_matrix.ps1
```

输出：

- `outputs_jmeter_matrix/jmeter_matrix_summary.csv`
- `outputs_jmeter_matrix/jmeter_matrix_summary.md`
- `outputs_jmeter_matrix/threads_10/html/index.html`
- `outputs_jmeter_matrix/threads_30/html/index.html`
- `outputs_jmeter_matrix/threads_50/html/index.html`

Selenium 新增多浏览器兼容性入口：

```powershell
powershell -ExecutionPolicy Bypass -File tests/selenium/run_selenium_matrix.ps1 -Browsers chrome,edge,firefox
```

输出：

- `outputs_selenium_matrix/selenium_browser_matrix_summary.csv`
- `outputs_selenium_matrix/selenium_browser_matrix_summary.md`
- 各浏览器独立截图目录。

已记录 Edge 结果：`passed`，首页约 1220 ms，商品页约 197 ms，购物车约 84 ms。

## Prometheus/Grafana 与应用性能指标

项目新增 `online-boutique-probe-exporter`，让 Prometheus 可以采集应用层关键指标，而不只依赖 Kubernetes 状态指标：

- `online_boutique_probe_requests_total`
- `online_boutique_probe_success_total`
- `online_boutique_probe_error_total`
- `online_boutique_probe_latency_ms`
- `online_boutique_probe_last_status_code`
- `online_boutique_probe_last_response_bytes`

Grafana 仪表盘截图：

- `docs/screenshots/grafana_online_boutique_app_metrics_dashboard.png`

Prometheus 查询证据：

- `docs/prometheus_probe_requests.json`
- `docs/prometheus_probe_latency.json`
- `docs/prometheus_probe_errors.json`

## ChaosMesh 实证

ChaosMesh 已实际安装并对 Online Boutique 执行过 PodChaos：

```powershell
kubectl apply -f scripts/chaos-online-boutique-productcatalog-podkill.yaml
```

证据口径：

- `PodChaos` 状态出现 `Selected=True`、`AllInjected=True`。
- 事件包含 `Successfully apply chaos`。
- 原 `productcatalogservice` Pod 被杀掉后由 Deployment 自动重建，新 Pod 恢复为 `1/1 Running`。

证据文件：

- `docs/chaosmesh_pods.txt`
- `docs/chaosmesh_crds.txt`
- `docs/chaosmesh_productcatalog_after.txt`
- `docs/testing_chaos_prometheus_evidence.md`

截图口径建议：报告只放关键结果区域，例如 Grafana 核心面板、JMeter 汇总表、Selenium 页面截图、USAD 异常分数图和 ChaosMesh 状态摘要；避免放入无关终端、聊天窗口或调试过程。

## 报告生成

```powershell
python src/build_report.py
```

生成文件位于：

- `report/2311467_李响_2313163_陈祖名_软件测试与维护大作业报告.docx`
- `report/2311467_李响_2313163_陈祖名_软件测试与维护大作业报告.pdf`
