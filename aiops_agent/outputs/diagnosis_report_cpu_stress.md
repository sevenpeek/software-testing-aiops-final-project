# AIOps Agent 智能运维诊断报告

## 1. 基本信息

- 系统名称：Online Boutique
- namespace：online-boutique
- 运行模式：hybrid（离线算法结果 + 在线运行证据）
- Agent 类型：规则编排型 AIOps Agent
- 数据来源：USAD 输出文件 + KPIRoot 输出文件 + Kubernetes 只读查询 + Prometheus 实时指标
- 当前阶段：第三阶段，已加入 Kubernetes 只读证据查询与 Prometheus 实时指标查询。
- 生成时间：2026-06-07T15:56:50

## 2. 异常检测结果（USAD）

USAD 的作用是判断当前 KPI 时间序列中是否存在异常窗口，它解决的是“是否异常”的问题。

- 使用的数据集：online_boutique_chaosmesh
- anomaly_scores.csv 路径：`D:\software-test-final-aiops\external_projects\usad_anomaly_detection\outputs_online_boutique_chaosmesh\anomaly_scores.csv`
- metrics_summary.txt 路径：`D:\software-test-final-aiops\external_projects\usad_anomaly_detection\outputs_online_boutique_chaosmesh\metrics_summary.txt`
- total_windows：115
- anomaly_windows：56
- max_anomaly_score：18207.188682
- mean_anomaly_score：949.681100
- threshold：0.222608
- precision / recall / f1：0.464300 / 0.742900 / 0.571400
- tp / fp / fn / tn：26 / 30 / 9 / 50
- 初步判断：是否检测到异常：是

Top reconstruction-error metrics：
- `frontend_latency_ms`: 18.406718
- `frontend_status_code`: 6.185363
- `frontend_response_bytes`: 0.941066
- `chaosmesh_active`: 0.661957
- `frontend_success`: 0.141677

## 3. 根因定位结果（KPIRoot）

KPIRoot 的作用是在异常发生后对候选 KPI 和服务进行排序，它解决的是“异常可能在哪里”的问题。

- 使用的 scenario：stress-paymentservice-cpu-001
- summary.csv 路径：`D:\software-test-final-aiops\external_projects\kpiroot_fault_diagnosis\data\phase4\kpiroot\summary.csv`
- ranking.csv 路径：`D:\software-test-final-aiops\external_projects\kpiroot_fault_diagnosis\data\phase4\kpiroot\stress-paymentservice-cpu-001\ranking.csv`
- Top1 根因指标：`cpu__paymentservice`
- Top1 根因服务：`paymentservice`
- Top1 得分：0.700058

Top5 候选根因：
- Rank 1: `cpu__paymentservice` (service=`paymentservice`, score=0.700058)
- Rank 2: `memory__paymentservice` (service=`paymentservice`, score=0.410486)
- Rank 3: `fs_reads__paymentservice` (service=`paymentservice`, score=0.300048)
- Rank 4: `fs_writes__redis-cart` (service=`redis-cart`, score=0.282447)
- Rank 5: `memory__shippingservice` (service=`shippingservice`, score=0.228571)

## 4. 证据链分析

- 异常检测证据：USAD 在当前数据集中检测到 56 个异常窗口，最大异常分数为 18207.188682，阈值为 0.222608。
- 根因定位证据：KPIRoot 将 `cpu__paymentservice` 排在第 1 位，对应服务为 `paymentservice`。
- 指标解释：Top1 指标包含 CPU，说明该场景更倾向于 CPU 压力或计算资源异常。
- 影响解释：USAD 的 Top reconstruction-error metrics 中包含 `frontend_latency_ms`, `frontend_status_code`, `frontend_success`，说明异常最终可能反映在用户入口层；这并不否定 KPIRoot 的后端根因指向，仍需通过日志和事件进一步验证。

## Kubernetes 运行证据

- 查询 namespace：`online-boutique`
- 查询服务名：`paymentservice`
- 当前健康状态：`healthy`
- kubectl 可用：是
- Event warning 数量：0
- Event 解释：当前 Event 未显示明显异常。

Pod 查询结果：
```text
NAME                             READY   STATUS    RESTARTS   AGE   IP             NODE       NOMINATED NODE   READINESS GATES
paymentservice-66c65775b-ljm4g   1/1     Running   0          10h   10.244.0.169   minikube   <none>           <none>
```

Deployment 查询结果：
```text
NAME             READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS   IMAGES                                                                                SELECTOR
paymentservice   1/1     1            1           10h   server       us-central1-docker.pkg.dev/google-samples/microservices-demo/paymentservice:v0.10.5   app=paymentservice
```

Service 查询结果：
```text
NAME             TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)     AGE   SELECTOR
paymentservice   ClusterIP   10.105.212.131   <none>        50051/TCP   10h   app=paymentservice
```

近期 Event：
```text
N/A
```

服务日志尾部：

日志内容已进行脱敏处理，仅保留排障所需的摘要信息。本次脱敏替换次数：200。
```text
{"severity":"info","time":1780818928135,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"USD\",\"units\":\"108\",\"nanos\":940000000},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780818928135,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: USD108.940000000"}
{"severity":"info","time":1780818936973,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"JPY\",\"units\":\"68299\",\"nanos\":605485012},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780818936973,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: JPY68299.605485012"}
{"severity":"info","time":1780818944366,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"USD\",\"units\":\"888\",\"nanos\":910000000},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780818944366,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: USD888.910000000"}
{"severity":"info","time":1780818950575,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"CAD\",\"units\":\"1529\",\"nanos\":85516128},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780818950575,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: CAD1529.85516128"}
{"severity":"info","time":1780818969243,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"EUR\",\"units\":\"1058\",\"nanos\":903140221},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780818969243,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: EUR1058.903140221"}
{"severity":"info","time":1780818980685,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"CAD\",\"units\":\"359\",\"nanos\":137783283},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780818980685,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: CAD359.137783283"}
{"severity":"info","time":1780818982662,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"CAD\",\"units\":\"88\",\"nanos\":265624061},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780818982662,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: CAD88.265624061"}
{"severity":"info","time":1780818983700,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"USD\",\"units\":\"998\",\"nanos\":880000000},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780818983700,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: USD998.880000000"}
{"severity":"info","time":1780818984659,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"JPY\",\"units\":\"28155\",\"nanos\":725785566},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780818984659,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: JPY28155.725785566"}
{"severity":"info","time":1780818996657,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"EUR\",\"units\":\"1033\",\"nanos\":392304297},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780818996658,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: EUR1033.392304297"}
```

## Prometheus 实时指标证据

- 查询模式：`kubectl_exec`
- monitoring namespace：`monitoring`
- Prometheus deployment：`prometheus-deployment`
- 查询服务名：`paymentservice`
- Prometheus 可用性：是
- CPU 指标序列数量：12.000000
- Online Boutique 总 CPU rate：0.193128
- 服务 CPU rate：0.162373
- 服务 memory working set bytes：46338048.000000
- 服务 memory working set MiB：44.191406
- service container count：1.000000
- 指标解释：当前 paymentservice CPU rate 处于中间水平，需要结合历史基线判断。 当前 paymentservice memory working set 约为 44.19 MiB。 Prometheus 已采集到该服务的容器级指标。 当前 Prometheus 阶段主要使用 cAdvisor/container 指标，不依赖 kube-state-metrics。

查询 PromQL：
- `prometheus_up`:
```promql
up
```
- `online_boutique_cpu_series_count`:
```promql
count(container_cpu_usage_seconds_total{namespace="online-boutique"})
```
- `online_boutique_cpu_total_rate`:
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="online-boutique"}[1m]))
```
- `service_cpu_rate`:
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="online-boutique",pod=~"paymentservice.*"}[1m]))
```
- `service_memory_working_set`:
```promql
sum(container_memory_working_set_bytes{namespace="online-boutique",pod=~"paymentservice.*"})
```
- `service_container_count`:
```promql
count(container_cpu_usage_seconds_total{namespace="online-boutique",pod=~"paymentservice.*"})
```

## 5. Agent 综合诊断

Agent 首先根据 USAD 结果判断系统存在异常；随后根据 KPIRoot 排名，将 `paymentservice` 作为优先排查对象。Top1 指标为 `cpu__paymentservice`，说明异常更可能与该服务的某类资源或状态变化有关。结合异常检测和根因定位结果，Agent 建议后续优先围绕该服务收集 Pod 状态、日志、事件和 Prometheus 指标。
USAD 重构误差较高的指标包含前端入口层指标，而 KPIRoot Top1 服务指向后端服务。这不应被视为矛盾，更合理的解释是：异常可能在入口层表现明显，但根因定位结果指向后端服务，需要进一步通过日志和 Kubernetes Event 验证。
Kubernetes 证据显示当前该服务处于 Running/Available 状态，当前运行状态未显示明显容器级故障。因此 USAD 与 KPIRoot 结果更像是离线故障实验数据中的异常证据，需要结合后续 Prometheus 实时指标进一步验证。
Agent 已经完成该服务的日志尾部采集，日志已脱敏并限制展示行数，可在“Kubernetes 运行证据”章节中查看。
Prometheus 已返回服务级 CPU 指标，但当前数值未达到明显 CPU 压力阈值，建议结合历史基线继续判断。
当前阶段未依赖 kube-state-metrics，因为 kube-state-metrics 当前不可用或未恢复；报告主要使用 cAdvisor/container 指标。
基于当前 Kubernetes 与 Prometheus 实时证据，Agent 生成了恢复计划，决策为 `cpu_pressure_investigation`，风险等级为 `medium`。当前计划仅用于人工复核，不会自动执行恢复命令。

## 恢复建议与执行保护

- 恢复计划状态 enabled：是
- 是否执行真实恢复命令 execute_recovery：否
- dry_run 状态：是
- 目标服务：`paymentservice`
- 根因指标：`cpu__paymentservice`
- 决策 decision：`cpu_pressure_investigation`
- 风险等级 risk_level：`medium`

当前 execute_recovery=false / dry_run=true，Agent 只生成恢复建议，不执行真实恢复命令。

推荐动作：
- 当前 Prometheus 实时 CPU 指标超过阈值，支持 paymentservice CPU 压力判断，建议继续检查 CPU、日志和事件。
- 可考虑扩容或重启服务，但必须人工确认后执行。
- 执行任何恢复动作前应先保存当前日志、事件和 Prometheus 指标截图或报告。

建议命令：
```powershell
kubectl get pods -n online-boutique | findstr paymentservice
```
```powershell
kubectl logs deployment/paymentservice -n online-boutique --tail=100
```
```powershell
kubectl get events -n online-boutique --sort-by=.lastTimestamp
```
```powershell
kubectl top pod -n online-boutique
```
```powershell
# 需人工确认后执行：kubectl rollout restart deployment/paymentservice -n online-boutique
```

安全说明：
- 当前 execute_recovery=false / dry_run=true，Agent 只生成恢复建议，不执行真实恢复命令。
- agent.enable_recovery=false，任何恢复命令都不会由 Agent 自动执行。
- 包含 rollout restart 等命令时仅作为草案展示，必须人工确认后另行执行。
- CPU 压力判断阈值 cpu_pressure_threshold=0.05。
- 当前 Prometheus memory working set 约为 44.19 MiB，仅作为恢复判断参考。

## 6. 建议的下一步运维动作

- 查看根因服务 Pod 状态：
  ```powershell
  kubectl get pods -n online-boutique | findstr paymentservice
  ```
- 查看根因服务日志：
  ```powershell
  kubectl logs deployment/paymentservice -n online-boutique --tail=100
  ```
- 查看近期事件：
  ```powershell
  kubectl get events -n online-boutique --sort-by=.lastTimestamp
  ```
- 查询 Prometheus 指标：
  例如查询 `paymentservice` 的 CPU、内存、请求延迟或错误率相关指标。
- 如确认服务异常，再考虑：
  ```powershell
  kubectl rollout restart deployment/paymentservice -n online-boutique
  ```

当前配置 enable_recovery=false，Agent 不会执行真实恢复命令。

## 7. 当前版本局限

- 当前 Agent 仍以离线 USAD 和 KPIRoot 输出为核心输入。
- 当前 Agent 只执行 Kubernetes 只读查询，不会修改集群状态。
- 当前 Agent 通过 kubectl exec 只读查询 Prometheus API，不会修改 Prometheus 或业务服务状态。
- 当前 Agent 不会执行真实恢复命令。
- 当前 Agent 暂不依赖 kube-state-metrics，主要使用 cAdvisor/container 指标。
- USAD 与 KPIRoot 的离线故障场景仍需要在最终演示中进一步对齐。
