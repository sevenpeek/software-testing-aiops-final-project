# 第三档目标优化方案

大作业评分第三档要求在更复杂的开源微服务系统基础上完成部署、监控和维护，并完成 1-2 个微服务开发。为满足该目标，本项目建议采用如下升级路径。

## 1. 微服务系统选择

建议选择 `Online Boutique` 作为第三档基础系统。

原因：

- 系统复杂度高于 SockShop，包含前端、购物车、结算、支付、推荐、商品目录、货币换算等多个服务。
- 官方 Kubernetes 清单完整，部署复杂度低于 TrainTicket。
- 业务链路清晰，适合使用 JMeter/Selenium 构造访问负载。
- Prometheus 指标可覆盖服务请求、资源占用、延迟和错误率。

备选：TrainTicket。它更复杂，但部署和调试成本更高，适合时间充足的小组。

## 2. 自研微服务开发

本项目新增 `anomaly-detector` 微服务，用于封装 USAD 异常检测能力。

功能：

- 通过 `/health` 提供健康检查。
- 通过 `/detect` 接收 CSV 数据路径并运行 USAD。
- 通过 `/summary` 返回最近一次检测摘要。
- 可容器化并部署到 Kubernetes `monitoring` 命名空间。

文件：

- `services/anomaly-detector/app.py`
- `services/anomaly-detector/Dockerfile`
- `k8s/anomaly-detector-deployment.yaml`

## 3. 与 Online Boutique 的集成方式

推荐架构：

1. Online Boutique 运行于 `online-boutique` 命名空间。
2. Prometheus 运行于 `monitoring` 命名空间，采集 Online Boutique 服务指标。
3. ChaosMesh 注入 Pod Kill、Network Delay、CPU Stress 等故障。
4. `export_prometheus.py` 定时导出多变量 KPI。
5. `anomaly-detector` 调用 USAD 检测异常并输出分数。
6. Grafana 或报告中展示异常分数与关键 KPI 重构误差。

## 4. 推荐提交展示点

- 展示复杂微服务系统 Online Boutique 的服务列表和前端页面。
- 展示自研 anomaly-detector 的 Dockerfile、K8s Deployment 和 API 调用。
- 展示 Prometheus/Grafana 中 Online Boutique 指标。
- 展示 ChaosMesh 故障注入前后的 KPI 变化。
- 展示 USAD 输出的异常分数和 KPI 重构误差。

## 5. 第三档达成说明

若完成 Online Boutique 部署，并将 `anomaly-detector` 作为独立服务部署到 Kubernetes 集群中，本项目可以覆盖第三档的两个关键要求：

- 基于更复杂开源微服务系统完成部署、监控和维护。
- 完成一个自研微服务开发，并与监控/异常检测流程集成。

具体部署步骤见 `docs/deploy_online_boutique.md`。
