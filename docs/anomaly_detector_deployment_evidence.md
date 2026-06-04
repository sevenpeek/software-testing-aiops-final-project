# anomaly-detector 微服务部署记录

部署时间：2026-06-02

## 1. 镜像构建

构建命令：

```powershell
docker build -f services\anomaly-detector\Dockerfile -t anomaly-detector:latest .
```

结果：

```text
naming to docker.io/library/anomaly-detector:latest done
```

## 2. 加载到 Minikube

```powershell
minikube image load anomaly-detector:latest
```

## 3. Kubernetes 部署

```powershell
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s\anomaly-detector-deployment.yaml
```

部署资源：

```text
namespace/monitoring created
deployment.apps/anomaly-detector created
service/anomaly-detector created
```

## 4. Pod 与 Service 状态

```text
pod/anomaly-detector-58f5d6c476-z8c5h condition met
```

```text
NAME               TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)
anomaly-detector   NodePort   10.110.79.104   <none>        8088:30088/TCP
```

## 5. 健康检查

由于 Windows + Docker driver 下 NodePort 访问不稳定，使用 port-forward 验证服务：

```powershell
kubectl port-forward svc/anomaly-detector 8088:8088 -n monitoring
```

访问：

```powershell
Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8088/health
```

结果：

```json
{
  "status": "ok",
  "service": "anomaly-detector"
}
```

## 6. /detect 接口验证

请求：

```powershell
Invoke-WebRequest -UseBasicParsing -Method Post `
  -Uri http://127.0.0.1:8088/detect `
  -Body '{"input":"data/sample_sockshop_metrics.csv","out":"outputs_in_cluster","window":12,"epochs":30}' `
  -ContentType 'application/json'
```

返回核心结果：

```json
{
  "status": "ok",
  "summary": {
    "rows": "720",
    "metrics": "9",
    "precision": "0.7098",
    "recall": "1.0000",
    "f1": "0.8303"
  }
}
```

## 7. 第三档意义

`anomaly-detector` 已作为独立自研微服务部署到 Kubernetes `monitoring` 命名空间，并能通过 HTTP API 实际触发 USAD 异常检测流程。该服务与已部署的 Online Boutique 共同构成“复杂开源微服务系统 + 自研微服务开发”的第三档展示基础。

