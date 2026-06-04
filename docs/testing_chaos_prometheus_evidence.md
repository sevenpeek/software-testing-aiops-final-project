# Testing, ChaosMesh, and Prometheus Application Metrics Evidence

## 1. Selenium Functional Test

Test script:

```text
tests/selenium/online_boutique_ui_test.py
```

Run command:

```powershell
powershell -ExecutionPolicy Bypass -File tests\selenium\run_selenium.ps1
```

Result file:

```text
outputs_selenium/selenium_result.json
```

Observed result:

```text
status: passed
open_home latency: 723.52 ms
open_product latency: 108.18 ms
open_cart latency: 70.04 ms
product URL: http://127.0.0.1:8080/product/OLJCESPC7Z
```

Screenshots:

```text
outputs_selenium/selenium_home.png
outputs_selenium/selenium_product.png
outputs_selenium/selenium_cart.png
```

## 2. JMeter Load Test

Test plan:

```text
tests/jmeter/online_boutique_load_test.jmx
```

Run command:

```powershell
$env:JMETER_HOME='D:\文档\PPT\软件测试与维护\lab3\apache-jmeter-5.6.3'
powershell -ExecutionPolicy Bypass -File tests\jmeter\run_jmeter.ps1
```

JMeter output:

```text
outputs_jmeter/online_boutique_load_test.jtl
outputs_jmeter/html/index.html
outputs_jmeter/jmeter_summary.txt
```

Observed summary:

```text
total_samples: 240
success_samples: 240
error_samples: 0
error_rate: 0.00%
avg_latency_ms: 15.83
min_latency_ms: 5
max_latency_ms: 81
labels: GET Cart Page, GET Home Page, GET Product Page
```

Screenshot:

```text
docs/screenshots/jmeter_online_boutique_report.png
```

## 3. Prometheus Application Metrics

To make Prometheus collect application-level performance data, the project adds a small exporter:

```text
services/online-boutique-probe-exporter/app.py
k8s/online-boutique-probe-exporter.yaml
```

The exporter continuously probes the Online Boutique frontend and exposes:

```text
online_boutique_probe_requests_total
online_boutique_probe_success_total
online_boutique_probe_error_total
online_boutique_probe_latency_ms
online_boutique_probe_last_status_code
online_boutique_probe_last_response_bytes
online_boutique_probe_last_success
```

Prometheus query evidence:

```text
docs/prometheus_probe_requests.json
docs/prometheus_probe_latency.json
docs/prometheus_probe_errors.json
```

Observed example:

```text
online_boutique_probe_requests_total = 10+ samples during the first verification window
online_boutique_probe_latency_ms ~= 100 ms
online_boutique_probe_error_total = 0
```

Grafana screenshot with application metrics:

```text
docs/screenshots/grafana_online_boutique_app_metrics_dashboard.png
```

## 4. ChaosMesh Fault Injection

ChaosMesh was installed by Helm:

```powershell
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh `
  --namespace chaos-mesh --create-namespace `
  --set chaosDaemon.runtime=docker `
  --set chaosDaemon.socketPath=/var/run/docker.sock `
  --set dashboard.create=false
```

Evidence files:

```text
docs/chaosmesh_pods.txt
docs/chaosmesh_crds.txt
```

Fault injection YAML:

```text
scripts/chaos-online-boutique-productcatalog-podkill.yaml
```

Run command:

```powershell
kubectl apply -f scripts\chaos-online-boutique-productcatalog-podkill.yaml
```

Observed PodChaos status before cleanup:

```text
Type: Selected, Status: True
Type: AllInjected, Status: True
Event: Successfully apply chaos for online-boutique/productcatalogservice-7d7957447b-fgl72
```

Observed recovery:

```text
Old pod: productcatalogservice-7d7957447b-fgl72
New pod: productcatalogservice-7d7957447b-4vpvt
New pod status: 1/1 Running
```

After evidence collection, the one-shot PodChaos object was deleted to avoid leaving active fault objects in the cluster:

```powershell
kubectl delete podchaos online-boutique-productcatalog-pod-kill -n online-boutique
```

