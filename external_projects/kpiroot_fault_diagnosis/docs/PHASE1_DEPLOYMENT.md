# 阶段一：Online-Boutique 部署记录

## 基本信息

本阶段完成 `JoinFyc/Online-Boutique` 微服务系统在本地 Minikube 集群中的部署，为后续监控、故障注入、黑盒测试和论文算法复现提供运行对象。

| 项目 | 内容 |
| --- | --- |
| 微服务系统 | `JoinFyc/Online-Boutique` |
| 本地部署副本 | `Online-Boutique/` |
| Kubernetes 集群 | Minikube |
| 命名空间 | `online-boutique` |
| 使用清单 | `Online-Boutique/release/kubernetes-manifests.yaml` |

`kubernetes-manifests` 目录中的镜像名依赖 Skaffold 构建流程，课程实验中直接采用 `release/kubernetes-manifests.yaml` 中的公开预构建镜像。

## 部署过程

部署时使用的核心命令如下：

```powershell
minikube start
kubectl create namespace online-boutique
kubectl apply -n online-boutique -f .\FinalProject\Online-Boutique\release\kubernetes-manifests.yaml
kubectl wait --for=condition=available deployment --all -n online-boutique --timeout=300s
```

部署完成后检查 Pod 和 Service：

```powershell
kubectl get pods -n online-boutique -o wide
kubectl get svc -n online-boutique -o wide
```

检查结果显示，Online-Boutique 的 12 个业务 Pod 均进入 `1/1 Running` 状态，`frontend-external` 被暴露为 `LoadBalancer` 类型 Service。Windows 环境中直接访问 Minikube NodePort 不够稳定，因此最终采用本地端口转发访问前端。

## 前端访问

本地前端访问通过以下命令建立：

```powershell
kubectl port-forward -n online-boutique service/frontend 8088:80
```

访问地址：

```text
http://127.0.0.1:8088
```

2026-06-04 的验证结果：

- `curl -I http://127.0.0.1:8088` 返回 `HTTP/1.1 200 OK`。
- `curl -L http://127.0.0.1:8088` 能返回 Online Boutique 首页 HTML。
- 浏览器可以正常打开商品首页。

## 恢复脚本

为避免每次重启 Windows 后手动恢复集群状态，项目中保留了恢复脚本：

```powershell
.\FinalProject\scripts\resume-online-boutique.ps1
```

该脚本负责启动 Minikube、清理上一次 Minikube 会话遗留的终止态 Pod、重启 Online-Boutique Deployment、等待 frontend 端点恢复，并建立本地前端访问。

常用参数如下：

```powershell
# 仅恢复集群，不启动前台端口转发。
.\FinalProject\scripts\resume-online-boutique.ps1 -NoPortForward

# 8088 被占用时使用其他本地端口。
.\FinalProject\scripts\resume-online-boutique.ps1 -LocalPort 8089

# 集群已确认健康时跳过 rollout restart。
.\FinalProject\scripts\resume-online-boutique.ps1 -SkipRolloutRestart
```

在 Minikube 已运行且 Pod 已健康的情况下，也可以只执行前端端口转发脚本：

```powershell
.\FinalProject\scripts\port-forward-frontend.ps1
```

## 手动恢复命令记录

脚本以外的手动恢复流程如下：

```powershell
minikube start
kubectl get namespace online-boutique
kubectl delete pod -n online-boutique --field-selector=status.phase=Failed --ignore-not-found
kubectl delete pod -n online-boutique --field-selector=status.phase=Succeeded --ignore-not-found
kubectl get deployment -n online-boutique -o name | ForEach-Object { kubectl rollout restart $_ -n online-boutique }
kubectl wait --for=condition=available deployment --all -n online-boutique --timeout=300s
kubectl get pods -n online-boutique -o wide
kubectl get endpointslices -n online-boutique -l kubernetes.io/service-name=frontend -o wide
kubectl port-forward -n online-boutique service/frontend 8088:80
```

若 `online-boutique` 命名空间不存在，则重新部署：

```powershell
.\FinalProject\scripts\deploy-online-boutique.ps1
```

## 资源整理

部署后清理了前序实验中不再使用的 `sock-shop` 命名空间，以释放本地资源。`monitoring` 和 `chaos-testing` 命名空间被保留，因为阶段二继续复用其中的 Prometheus、Grafana 和 ChaosMesh 组件。

阶段一完成后，Online-Boutique 前端、Pod 状态和 Service 暴露方式均已验证，可作为后续实验的稳定对象。
