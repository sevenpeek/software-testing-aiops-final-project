# 大作业实验说明

## 1. 实验目标

选择 KDD 2020 论文 `USAD: UnSupervised Anomaly Detection on Multivariate Time Series`，在微服务运维场景下复现其核心思想：使用多变量 KPI 时间序列训练无监督异常检测模型，并识别故障窗口。

本实验与前四次课程实验相互独立。可以复用 Docker、Minikube、Kubernetes、Prometheus、Grafana、Selenium、JMeter、ChaosMesh 等工具，但不复用前四次实验报告中的结论。

## 2. 第三档实现范围

当前项目已按第三档目标补强：

- 复杂开源微服务系统：Online Boutique 已部署到 Minikube。
- 自研微服务 1：`anomaly-detector`，提供 `/health`、`/detect`、`/summary`，将 USAD 检测封装为 HTTP 服务。
- 自研微服务 2：`online-boutique-probe-exporter`，定期访问 Online Boutique 前端并暴露 Prometheus 应用性能指标。
- 自动化测试：补充 Selenium UI 测试脚本和 JMeter `.jmx` 压测计划。
- 真实故障验证：真实 KPI 采集阶段使用 `kubectl scale` 标注故障窗口；后续补充 ChaosMesh PodChaos 实际注入证据。
- 监控展示：补充 Prometheus 查询证据和 Grafana 应用性能仪表盘截图。

## 3. 数据来源

实验包含两类数据：

1. 示例 SockShop KPI 数据：`data/sample_sockshop_metrics.csv`
   - 用于可控复现 USAD 算法流程。
   - 包含正常窗口和人工构造故障窗口。

2. Online Boutique 真实 KPI 数据：`data/online_boutique_real_metrics.csv`
   - 由 `src/collect_online_boutique_metrics.py` 采集。
   - KPI 来自前端 HTTP 探测结果与 Kubernetes API 状态。
   - 故障阶段通过将 `productcatalogservice` 缩放到 0 个副本实现，恢复阶段再缩放回 1 个副本。

Online Boutique 真实 KPI 结果：

- 样本数：120
- KPI 数量：15
- 窗口大小：6
- Precision：0.6071
- Recall：0.9714
- F1：0.7473

## 4. USAD 复现步骤

生成示例数据：

```powershell
python src/generate_sample_data.py --out data/sample_sockshop_metrics.csv
```

运行 USAD：

```powershell
python src/run_usad.py --input data/sample_sockshop_metrics.csv --out outputs
```

运行 Online Boutique 真实 KPI 检测：

```powershell
python src/run_usad.py --input data/online_boutique_real_metrics.csv --out outputs_online_boutique_real --window 6 --epochs 120 --train-ratio 0.35
```

核心输出：

- `outputs/anomaly_scores.csv`
- `outputs/metrics_summary.txt`
- `outputs/anomaly_score.png`
- `outputs/reconstruction_error.png`
- `outputs_online_boutique_real/anomaly_score.png`
- `outputs_online_boutique_real/reconstruction_error.png`

## 5. Selenium 测试

脚本：

```powershell
tests/selenium/online_boutique_ui_test.py
```

运行入口：

```powershell
tests/selenium/run_selenium.ps1
```

当前本机以 Chrome headless 作为代表浏览器完成验证，覆盖：

- 打开 Online Boutique 首页。
- 进入商品详情页。
- 访问购物车页面。
- 保存页面截图与耗时 JSON。

输出：

- `outputs_selenium/selenium_result.json`
- `outputs_selenium/selenium_home.png`
- `outputs_selenium/selenium_product.png`
- `outputs_selenium/selenium_cart.png`

说明：未额外覆盖 Edge/Firefox，多浏览器兼容性属于后续改进项。

提交说明：`.tools/python_lib` 是本机 Selenium 依赖缓存，不建议作为源码提交。若删除该目录，可使用以下命令重新安装 Selenium：

```powershell
pip install -r tests/selenium/requirements.txt
```

## 6. JMeter 测试

测试计划：

```powershell
tests/jmeter/online_boutique_load_test.jmx
```

运行入口：

```powershell
tests/jmeter/run_jmeter.ps1
```

测试覆盖首页、商品页、购物车页。已生成：

- `outputs_jmeter/online_boutique_load_test.jtl`
- `outputs_jmeter/html/index.html`
- `outputs_jmeter/jmeter_summary.txt`
- `docs/screenshots/jmeter_online_boutique_report.png`

实际结果：240 samples，错误率 0.00%，平均响应时间 15.83 ms，最大响应时间 81 ms。

## 7. Prometheus/Grafana 监控

监控配置：

```powershell
monitoring/lightweight-monitoring.yaml
```

应用性能指标由 `online-boutique-probe-exporter` 提供，包括请求数、成功数、错误数、响应时间、HTTP 状态码和响应字节数。

证据文件：

- `docs/prometheus_grafana_evidence.md`
- `docs/prometheus_probe_requests.json`
- `docs/prometheus_probe_latency.json`
- `docs/prometheus_probe_errors.json`
- `docs/screenshots/grafana_online_boutique_app_metrics_dashboard.png`

## 8. ChaosMesh 故障注入

配置文件：

```powershell
scripts/chaos-online-boutique-productcatalog-podkill.yaml
```

执行命令：

```powershell
kubectl apply -f scripts/chaos-online-boutique-productcatalog-podkill.yaml
```

已保存证据：

- `docs/chaosmesh_pods.txt`
- `docs/chaosmesh_crds.txt`
- `docs/chaosmesh_productcatalog_after.txt`
- `docs/testing_chaos_prometheus_evidence.md`

实验口径说明：

- 真实 KPI 数据采集为了稳定标注故障窗口，使用 `kubectl scale` 进行可重复故障注入。
- ChaosMesh 是后续补充的实际工具链验证，证明 PodChaos 可以对 Online Boutique 成功注入故障并触发 Pod 重建。

## 9. 报告与证据

报告：

- `report/2311467_李响_软件测试与维护大作业报告.docx`
- `report/2311467_李响_软件测试与维护大作业报告.pdf`

证据索引：

- `docs/online_boutique_deployment_evidence.md`
- `docs/anomaly_detector_deployment_evidence.md`
- `docs/online_boutique_real_usad_evidence.md`
- `docs/testing_chaos_prometheus_evidence.md`
- `docs/prometheus_grafana_evidence.md`
