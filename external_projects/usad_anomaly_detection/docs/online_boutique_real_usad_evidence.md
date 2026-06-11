# Online Boutique 真实 KPI + USAD 检测记录

实验时间：2026-06-02

## 1. 数据来源

本次实验不再使用示例数据，而是从已部署的 Online Boutique 实时采集 KPI。由于当前集群未安装 metrics-server，且 Online Boutique 前端未暴露 `/metrics`，本项目采用如下真实数据源：

- 前端 HTTP 实际访问响应时间。
- 前端 HTTP 状态码、成功/失败标记、响应字节数。
- Kubernetes API 中的 Pod Running 数、NotReady 数、总重启次数。
- Online Boutique 关键 Deployment 的 Ready Ratio。

采集脚本：

```text
src/collect_online_boutique_metrics.py
```

输出文件：

```text
data/online_boutique_real_metrics.csv
```

## 2. 故障注入方式

本次实验使用 Kubernetes 原生命令模拟服务故障：

```powershell
kubectl scale deployment productcatalogservice --replicas=0 -n online-boutique
```

故障持续 30 个采样点后恢复：

```powershell
kubectl scale deployment productcatalogservice --replicas=1 -n online-boutique
```

故障目标：

```text
productcatalogservice
```

故障影响：

- 商品详情页和商品目录依赖受影响。
- 前端请求可能出现错误状态码或响应时间波动。
- `productcatalogservice_ready_ratio` 降至 0。

## 3. 真实数据 USAD 本地运行结果

运行命令：

```powershell
python src\run_usad.py --input data\online_boutique_real_metrics.csv --out outputs_online_boutique_real --window 6 --epochs 120 --train-ratio 0.35
```

结果：

```text
rows: 120
metrics: 15
window_size: 6
train_windows: 37
threshold: 0.209006
precision: 0.6071
recall: 0.9714
f1: 0.7473
tp/fp/fn/tn: 34/22/1/58
```

Top reconstruction-error metrics：

```text
frontend_status_code: 71.397721
frontend_latency_ms: 4.238709
frontend_response_bytes: 1.488691
frontend_success: 0.360147
productcatalogservice_ready_ratio: 0.348493
```

## 4. 集群内 anomaly-detector 运行真实数据

为避免 `latest` 镜像缓存，使用唯一标签重建镜像：

```powershell
docker build --no-cache -f services\anomaly-detector\Dockerfile -t anomaly-detector:realdata .
minikube image load anomaly-detector:realdata
kubectl set image deployment/anomaly-detector anomaly-detector=anomaly-detector:realdata -n monitoring
kubectl rollout status deployment/anomaly-detector -n monitoring --timeout=180s
```

Pod 内确认真实数据存在：

```text
/app/data/online_boutique_real_metrics.csv
/app/data/sample_kpi_metrics.csv
```

端口转发：

```powershell
kubectl port-forward svc/anomaly-detector 8088:8088 -n monitoring
```

调用 `/detect`：

```powershell
Invoke-WebRequest -UseBasicParsing -Method Post `
  -Uri http://127.0.0.1:8088/detect `
  -Body '{"input":"data/online_boutique_real_metrics.csv","out":"outputs_online_boutique_in_cluster","window":6,"epochs":120}' `
  -ContentType 'application/json'
```

返回：

```json
{
  "status": "ok",
  "summary": {
    "rows": "120",
    "metrics": "15",
    "precision": "0.6071",
    "recall": "0.9714",
    "f1": "0.7473"
  }
}
```

## 5. 闭环说明

至此，本项目形成完整第三档闭环：

1. 更复杂开源微服务系统 Online Boutique 已部署。
2. 自研 anomaly-detector 微服务已部署到 Kubernetes。
3. 对 Online Boutique 执行真实故障注入。
4. 采集真实 Online Boutique KPI。
5. 用真实 KPI 运行 USAD。
6. anomaly-detector 服务通过 HTTP API 返回真实数据检测结果。
