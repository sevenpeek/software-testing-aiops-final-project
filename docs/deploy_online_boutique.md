# Online Boutique 部署指南

当前 `final_project` 尚未实际部署 Online Boutique 或 TrainTicket；已经完成的是 USAD 复现实验、自研 `anomaly-detector` 微服务和第三档升级资产。本指南用于把项目补齐到第三档所需的“更复杂开源微服务系统部署”部分。

推荐部署 Online Boutique。它由 GoogleCloudPlatform/microservices-demo 提供，官方说明其为基于 Kubernetes 的电商微服务示例，由 10 个微服务组成，并且可运行在任意 Kubernetes 集群上。

官方仓库：

- https://github.com/GoogleCloudPlatform/microservices-demo

## 1. 准备 Minikube

建议给 Minikube 分配更多资源。Online Boutique 比 SockShop 更复杂，资源不足时容易出现 `CrashLoopBackOff` 或镜像拉取/启动超时。

```powershell
minikube stop
minikube delete
minikube start --driver=docker --cpus=6 --memory=10g
kubectl get nodes
```

如果你的机器内存不足，可以先尝试：

```powershell
minikube start --driver=docker --cpus=4 --memory=8g
```

## 2. 克隆官方项目

建议放在 `D:\文档\PPT\软件测试与维护\large_homework\external` 下，避免和本项目源码混在一起。

```powershell
cd D:\文档\PPT\软件测试与维护\large_homework
New-Item -ItemType Directory -Force -Path external | Out-Null
cd external
git clone --depth 1 https://github.com/GoogleCloudPlatform/microservices-demo.git
cd microservices-demo
```

## 3. 部署 Online Boutique

官方快速部署清单位于 `release/kubernetes-manifests.yaml`。

```powershell
kubectl create namespace online-boutique
kubectl apply -n online-boutique -f .\release\kubernetes-manifests.yaml
kubectl get pods -n online-boutique
```

等待所有 Pod 进入 `Running` 或 `Completed` 状态：

```powershell
kubectl wait --for=condition=Ready pods --all -n online-boutique --timeout=600s
kubectl get svc -n online-boutique
```

## 4. 访问前端页面

Online Boutique 默认有 `frontend-external` 服务。Minikube 下可用：

```powershell
minikube service frontend-external -n online-boutique
```

如果只想拿 URL：

```powershell
minikube service frontend-external -n online-boutique --url
```

打开浏览器后，能看到 Online Boutique 电商页面，就说明复杂微服务系统部署成功。

## 5. 部署监控

如果你已经在 SockShop 实验中部署过 Prometheus/Grafana，可以继续复用工具；但建议在大作业中单独记录 Online Boutique 的指标采集过程。

若使用 kube-prometheus-stack 或已有 Prometheus，请重点确认：

```powershell
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

然后在 Prometheus 中检查是否能查询到 Online Boutique 相关指标，例如：

```promql
container_cpu_usage_seconds_total{namespace="online-boutique"}
container_memory_working_set_bytes{namespace="online-boutique"}
kube_pod_container_status_restarts_total{namespace="online-boutique"}
```

## 6. 注入故障

可将本项目已有 ChaosMesh YAML 中的 namespace 和 label 改为 Online Boutique 的服务。例如对 `productcatalogservice` 注入 Pod Kill：

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: online-boutique-productcatalog-pod-kill
  namespace: online-boutique
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - online-boutique
    labelSelectors:
      app: productcatalogservice
  duration: "60s"
```

执行：

```powershell
kubectl apply -f online-boutique-productcatalog-pod-kill.yaml
kubectl get pods -n online-boutique -w
```

## 7. 导出 Prometheus 数据

本项目的 `src/export_prometheus.py` 默认查询 SockShop 的 namespace。部署 Online Boutique 后，需要把查询中的 namespace 从 `sock-shop` 改为 `online-boutique`，或者复制一份脚本改成 Online Boutique 专用。

建议至少导出这些指标：

- CPU 使用率
- 内存使用量
- Pod 重启次数
- frontend 请求数
- frontend 响应时延
- 错误率或异常状态码数量

导出后运行：

```powershell
python src\run_usad.py --input data\prometheus_online_boutique_metrics.csv --out outputs_online_boutique
```

## 8. 部署自研 anomaly-detector 微服务

先构建镜像：

```powershell
cd D:\文档\PPT\软件测试与维护\large_homework\final_project
docker build -f services\anomaly-detector\Dockerfile -t anomaly-detector:latest .
```

让 Minikube 使用本地 Docker 镜像时，建议在当前 shell 中执行：

```powershell
minikube image load anomaly-detector:latest
```

部署服务：

```powershell
kubectl create namespace monitoring
kubectl apply -f k8s\anomaly-detector-deployment.yaml
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

访问健康检查：

```powershell
minikube service anomaly-detector -n monitoring --url
```

然后访问：

```text
http://<URL>/health
```

## 9. 第三档展示建议

最终报告或答辩建议补充以下截图：

- `kubectl get pods -n online-boutique`
- `kubectl get svc -n online-boutique`
- Online Boutique 前端页面
- Prometheus 查询 Online Boutique 指标
- Grafana 展示 Online Boutique 资源/请求指标
- ChaosMesh 故障注入状态
- `kubectl get pods -n monitoring` 中 anomaly-detector 正常运行
- `curl /health` 或 `/summary` 的接口结果
- USAD 在 `outputs_online_boutique` 中生成的异常分数图

本机实际部署记录见 `docs/online_boutique_deployment_evidence.md`。

## 10. TrainTicket 备选

TrainTicket 官方仓库：

- https://github.com/FudanSELab/train-ticket

官方说明它包含 41 个微服务，复杂度更高；部署要求包括 Kubernetes、Helm 和 PVC 支持。其快速部署命令为：

```powershell
git clone --depth=1 https://github.com/FudanSELab/train-ticket.git
cd train-ticket
make deploy
```

如果要带监控或 tracing，可使用：

```powershell
make deploy DeployArgs="--with-monitoring"
make deploy DeployArgs="--with-tracing --with-monitoring"
```

但 TrainTicket 对本机资源要求更高，调试成本更大。若目标是稳妥达到第三档，优先建议 Online Boutique。
