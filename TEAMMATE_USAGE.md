# 大作业项目交接说明

这份项目用于“软件测试与维护（2026 年春）”大作业，论文选择 KDD 2020 的 USAD：

> USAD: UnSupervised Anomaly Detection on Multivariate Time Series.

项目已经完成算法复现、Online Boutique 复杂微服务部署证据、自研微服务、Selenium/JMeter 测试、Prometheus/Grafana 监控截图、ChaosMesh 故障注入证据和 Word/PDF 报告初稿。你主要可以基于这些材料继续整理最终文档或 PPT。

## 1. 先看哪些文件

建议阅读顺序：

1. `README.md`
   - 项目总体说明。
   - 当前实验口径。
   - 第三档增强内容。

2. `EXPERIMENT.md`
   - 实验步骤说明。
   - Selenium/JMeter/Prometheus/Grafana/ChaosMesh 证据索引。

3. `report/2311467_李响_软件测试与维护大作业报告.docx`
   - 已生成的 Word 报告，可继续润色。

4. `docs/`
   - 部署、监控、测试、故障注入和截图证据。

5. `outputs_*`
   - 算法运行结果、测试结果和图片输出。

## 2. 项目核心结论口径

写报告时请保持下面这个口径，避免前后矛盾：

- 算法论文复现：使用 USAD 对多变量 KPI 时间序列做无监督异常检测。
- 示例复现数据：`data/sample_sockshop_metrics.csv`，用于可控验证 USAD 流程。
- 第三档真实系统：Online Boutique，已部署到 Minikube。
- 自研微服务 1：`anomaly-detector`，把 USAD 检测封装成 HTTP 服务。
- 自研微服务 2：`online-boutique-probe-exporter`，把 Online Boutique 前端请求数、响应时间、错误数等应用性能指标暴露给 Prometheus。
- 真实 KPI 采集阶段：为了得到边界清晰、可标注的故障窗口，使用 `kubectl scale` 将 `productcatalogservice` 缩放到 0，再恢复到 1。
- ChaosMesh 阶段：后续补充的实际故障注入验证，证明 PodChaos 能成功杀掉 Online Boutique 的 `productcatalogservice` Pod 并触发重建。
- Selenium：本机以 Chrome headless 作为代表浏览器完成 UI 自动化验证，未覆盖 Edge/Firefox。

## 3. 重要目录

- `src/`
  - USAD 算法、数据采集、报告生成脚本。

- `services/anomaly-detector/`
  - 自研异常检测微服务。

- `services/online-boutique-probe-exporter/`
  - 自研 Prometheus 应用性能指标采集微服务。

- `k8s/`
  - 自研服务部署清单。

- `monitoring/`
  - Prometheus/Grafana/kube-state-metrics 轻量监控配置。

- `tests/selenium/`
  - Selenium UI 自动化测试脚本。

- `tests/jmeter/`
  - JMeter 压测计划 `.jmx`。

- `scripts/`
  - ChaosMesh 故障注入 YAML。

- `docs/screenshots/`
  - Grafana 和 JMeter 截图。

- `outputs_selenium/`
  - Selenium 截图和 JSON 结果。

- `outputs_jmeter/`
  - JMeter 结果和 HTML 报告。

- `outputs_online_boutique_real/`
  - Online Boutique 真实 KPI 的 USAD 输出。

## 4. 如何重新运行 USAD

进入项目根目录：

```powershell
cd final_project
```

安装基础依赖：

```powershell
pip install -r requirements.txt
```

运行示例数据复现：

```powershell
python src/generate_sample_data.py --out data/sample_sockshop_metrics.csv
python src/run_usad.py --input data/sample_sockshop_metrics.csv --out outputs
```

运行 Online Boutique 真实 KPI 检测：

```powershell
python src/run_usad.py --input data/online_boutique_real_metrics.csv --out outputs_online_boutique_real --window 6 --epochs 120 --train-ratio 0.35
```

生成报告：

```powershell
python src/build_report.py
```

## 5. 如何运行 Selenium

先确保 Online Boutique 前端能通过 `http://127.0.0.1:8080` 访问。

安装 Selenium：

```powershell
pip install -r tests/selenium/requirements.txt
```

运行：

```powershell
powershell -ExecutionPolicy Bypass -File tests/selenium/run_selenium.ps1
```

输出：

- `outputs_selenium/selenium_result.json`
- `outputs_selenium/selenium_home.png`
- `outputs_selenium/selenium_product.png`
- `outputs_selenium/selenium_cart.png`

## 6. 如何运行 JMeter

需要本机已安装 Apache JMeter，并设置 `JMETER_HOME`。例如：

```powershell
$env:JMETER_HOME='D:\path\to\apache-jmeter-5.6.3'
powershell -ExecutionPolicy Bypass -File tests/jmeter/run_jmeter.ps1
```

输出：

- `outputs_jmeter/online_boutique_load_test.jtl`
- `outputs_jmeter/html/index.html`
- `outputs_jmeter/jmeter_summary.txt`

## 7. 监控和故障注入证据

Prometheus/Grafana 证据：

- `docs/prometheus_grafana_evidence.md`
- `docs/prometheus_probe_requests.json`
- `docs/prometheus_probe_latency.json`
- `docs/prometheus_probe_errors.json`
- `docs/screenshots/grafana_online_boutique_app_metrics_dashboard.png`

ChaosMesh 证据：

- `docs/testing_chaos_prometheus_evidence.md`
- `docs/chaosmesh_pods.txt`
- `docs/chaosmesh_crds.txt`
- `docs/chaosmesh_productcatalog_after.txt`

JMeter/Selenium 证据：

- `docs/screenshots/jmeter_online_boutique_report.png`
- `outputs_selenium/selenium_*.png`
- `outputs_selenium/selenium_result.json`

## 8. 打包说明

本交接包不包含 `.tools/` 目录。`.tools/python_lib` 只是本机运行 Selenium 时的依赖缓存，不属于源码。复现 Selenium 时按上面的安装命令重新安装即可。

如果老师或队友只看文档，不需要重新部署集群，重点看：

- `README.md`
- `EXPERIMENT.md`
- `TEAMMATE_USAGE.md`
- `report/`
- `docs/`
- `outputs_*`

如果需要复现实验，则需要 Docker Desktop、Minikube、kubectl、Python、JMeter、Chrome 和 Selenium。
