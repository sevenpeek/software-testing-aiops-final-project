# Online Boutique 实际部署记录

部署时间：2026-06-02

## 1. Minikube 启动

由于 Kubernetes v1.35.1 在当前 Docker Desktop 环境中出现 `K8S_APISERVER_MISSING`，且国内镜像源对 v1.33.5/v1.34.0 的 kubelet/kubeadm 校验文件返回 404，最终采用如下稳定启动方式：

```powershell
minikube start --driver=docker --cpus=4 --memory=6g --kubernetes-version=v1.32.0 --container-runtime=docker
```

启动结果：

```text
NAME       STATUS   ROLES           AGE   VERSION
minikube   Ready    control-plane   28s   v1.32.0
```

系统组件状态：

```text
coredns, etcd, kube-apiserver, kube-controller-manager, kube-proxy,
kube-scheduler, storage-provisioner 均为 Running。
```

## 2. Online Boutique 部署

官方仓库：

```powershell
git clone --depth 1 https://github.com/GoogleCloudPlatform/microservices-demo.git external\microservices-demo
```

部署命令：

```powershell
kubectl create namespace online-boutique
kubectl apply -n online-boutique -f .\external\microservices-demo\release\kubernetes-manifests.yaml
kubectl wait --for=condition=Ready pods --all -n online-boutique --timeout=600s
```

## 3. Pod 运行状态

```text
NAME                                     READY   STATUS    RESTARTS
adservice-848c5d6f88-kwd9m               1/1     Running   0
cartservice-59d44fb67-wxchx              1/1     Running   0
checkoutservice-54475449f4-fxbxz         1/1     Running   0
currencyservice-6bbd8c95f4-998ss         1/1     Running   0
emailservice-68dd7ccf64-pqspw            1/1     Running   0
frontend-6b8fcb997-gp8nt                 1/1     Running   0
loadgenerator-8599589654-bsll6           1/1     Running   0
paymentservice-cc458477b-z2w2k           1/1     Running   0
productcatalogservice-7d7957447b-mhd9d   1/1     Running   0
recommendationservice-84d6f4488d-jqh5h   1/1     Running   0
redis-cart-c4fc658fb-s7bqj               1/1     Running   0
shippingservice-69f6756b4d-w5pc4         1/1     Running   0
```

## 4. Service 状态

```text
frontend-external  LoadBalancer  10.103.41.251  <pending>  80:30555/TCP
frontend           ClusterIP     10.99.104.171  <none>     80/TCP
```

在 Windows + Docker driver 下，`minikube ip:NodePort` 可能无法直接从宿主机访问，因此使用 port-forward：

```powershell
kubectl port-forward svc/frontend-external 8080:80 -n online-boutique
```

访问地址：

```text
http://127.0.0.1:8080
```

验证结果：

```text
HTTP 200
页面内容包含 Online Boutique、Products 等关键字。
```

## 5. 第三档达成意义

Online Boutique 已作为比 SockShop 更复杂的开源微服务系统成功部署，包含 frontend、cart、checkout、currency、email、payment、product catalog、recommendation、shipping、ad、redis cart、load generator 等服务。结合本项目新增的 `anomaly-detector` 自研微服务，可以支撑第三档评分中“复杂微服务系统 + 微服务开发”的展示要求。

