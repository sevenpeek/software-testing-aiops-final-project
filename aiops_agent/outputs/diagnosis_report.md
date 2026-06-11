# AIOps Agent 智能运维诊断报告

## 1. 基本信息

- 系统名称：Online Boutique
- namespace：online-boutique
- 运行模式：hybrid（离线算法结果 + 在线运行证据）
- Agent 类型：规则编排型 AIOps Agent
- 数据来源：USAD 输出文件 + KPIRoot 输出文件 + Kubernetes 只读查询 + Prometheus 实时指标
- 当前阶段：第三阶段，已加入 Kubernetes 只读证据查询与 Prometheus 实时指标查询。
- 生成时间：2026-06-08T20:37:12

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

## 故障实验上下文

- fault_type: `cpu_stress`
- target_service: `paymentservice`
- fault_status: `verified`
- 检测依据: Prometheus service_cpu_rate
- 当前局限: CPU pressure is the fully verified end-to-end demo scenario.

## Kubernetes 运行证据

- 查询 namespace：`online-boutique`
- 查询服务名：`paymentservice`
- 当前健康状态：`healthy`
- kubectl 可用：是
- Pod restart count：2
- Pod ready：True
- Pod phase：`Running`
- Deployment available：True
- Selected pod names：`paymentservice-66c65775b-ljm4g`
- Event warning 数量：0
- Event 解释：当前 Event 未显示明显异常。
- 最近 warning events：`0`

Pod 查询结果：
```text
NAME                             READY   STATUS    RESTARTS      AGE   IP             NODE       NOMINATED NODE   READINESS GATES
paymentservice-66c65775b-ljm4g   1/1     Running   2 (67m ago)   38h   10.244.0.226   minikube   <none>           <none>
```

Deployment 查询结果：
```text
NAME             READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS   IMAGES                                                                                SELECTOR
paymentservice   1/1     1            1           39h   server       us-central1-docker.pkg.dev/google-samples/microservices-demo/paymentservice:v0.10.5   app=paymentservice
```

Service 查询结果：
```text
NAME             TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)     AGE   SELECTOR
paymentservice   ClusterIP   10.105.212.131   <none>        50051/TCP   39h   app=paymentservice
```

近期 Event：
```text
N/A
```

服务日志尾部：

日志内容已进行脱敏处理，仅保留排障所需的摘要信息。本次脱敏替换次数：170。
```text
UnacceptedCreditCard [Error]: Sorry, we cannot process visa_electron credit cards. Only VISA or MasterCard is accepted.
    at charge (/usr/src/app/charge.js:74:68)
    at HipsterShopServer.ChargeServiceHandler (/usr/src/app/server.js:44:24)
    at Object.onReceiveHalfClose (/usr/src/app/node_modules/@grpc/grpc-js/build/src/server.js:1464:25)
    at BaseServerInterceptingCall.maybePushNextMessage (/usr/src/app/node_modules/@grpc/grpc-js/build/src/server-interceptors.js:595:31)
    at BaseServerInterceptingCall.handleEndEvent (/usr/src/app/node_modules/@grpc/grpc-js/build/src/server-interceptors.js:635:14)
    at ServerHttp2Stream.<anonymous> (/usr/src/app/node_modules/@grpc/grpc-js/build/src/server-interceptors.js:394:18)
    at ServerHttp2Stream.emit (node:events:520:35)
    at endReadableNT (node:internal/streams/readable:1701:12)
    at process.processTicksAndRejections (node:internal/process/task_queues:89:21) {
  code: 400
}
{"severity":"info","time":1780922206609,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"TRY\",\"units\":\"5465\",\"nanos\":421147305},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780922206609,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: TRY5465.421147305"}
{"severity":"info","time":1780922215468,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"JPY\",\"units\":\"251854\",\"nanos\":96419952},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780922215468,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: JPY251854.96419952"}
{"severity":"info","time":1780922221728,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"JPY\",\"units\":\"43929\",\"nanos\":730207993},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780922221729,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: JPY43929.730207993"}
{"severity":"info","time":1780922224289,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-server","message":"PaymentService#Charge invoked with request {\"amount\":{\"currency_code\":\"JPY\",\"units\":\"11056\",\"nanos\":785493160},\"credit_card\":{\"credit_card_number\":\"****\",\"credit_card_cvv\":\"***\",\"credit_card_expiration_year\":\"****\",\"credit_card_expiration_month\":\"**\"}}"}
{"severity":"info","time":1780922224289,"pid":1,"hostname":"paymentservice-66c65775b-ljm4g","name":"paymentservice-charge","message":"Transaction processed: visa ending ****     Amount: JPY11056.785493160"}
```

## Prometheus 实时指标证据

- 查询模式：`kubectl_exec`
- monitoring namespace：`monitoring`
- Prometheus deployment：`prometheus-deployment`
- 查询服务名：`paymentservice`
- Prometheus 可用性：是
- CPU 指标序列数量：12.000000
- Online Boutique 总 CPU rate：0.033230
- 服务 CPU rate：0.000281
- 服务 memory working set bytes：51716096.000000
- 服务 memory working set MiB：49.320312
- service container count：1.000000
- container restart count（可选 kube-state 指标）：N/A
- 指标解释：当前 paymentservice 实时 CPU 使用率较低，暂未显示明显 CPU 压力。 当前 paymentservice memory working set 约为 49.32 MiB。 Prometheus 已采集到该服务的容器级指标。 当前 Prometheus 阶段主要使用 cAdvisor/container 指标，不依赖 kube-state-metrics。
- Memory 指标解释：Current memory working set is 49.32 MiB, below threshold 150.00 MiB.
- Network latency 指标说明：Current Prometheus queries do not include application latency/error-rate metrics; network delay faults require additional business metrics for strong diagnosis.

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
- `container_restart_count`:
```promql
sum(kube_pod_container_status_restarts_total{namespace="online-boutique",pod=~"paymentservice.*"})
```

## 5. Agent 综合诊断

Agent 首先根据 USAD 结果判断系统存在异常；随后根据 KPIRoot 排名，将 `paymentservice` 作为优先排查对象。Top1 指标为 `cpu__paymentservice`，说明异常更可能与该服务的某类资源或状态变化有关。结合异常检测和根因定位结果，Agent 建议后续优先围绕该服务收集 Pod 状态、日志、事件和 Prometheus 指标。
USAD 重构误差较高的指标包含前端入口层指标，而 KPIRoot Top1 服务指向后端服务。这不应被视为矛盾，更合理的解释是：异常可能在入口层表现明显，但根因定位结果指向后端服务，需要进一步通过日志和 Kubernetes Event 验证。
Kubernetes 证据显示当前该服务处于 Running/Available 状态，当前运行状态未显示明显容器级故障。因此 USAD 与 KPIRoot 结果更像是离线故障实验数据中的异常证据，需要结合后续 Prometheus 实时指标进一步验证。
Agent 已经完成该服务的日志尾部采集，日志已脱敏并限制展示行数，可在“Kubernetes 运行证据”章节中查看。
Kubernetes health_status=healthy，且 Prometheus service_cpu_rate 很低，说明当前实时系统运行较平稳，离线 USAD/KPIRoot 异常更可能来自历史故障注入数据。
当前阶段未依赖 kube-state-metrics，因为 kube-state-metrics 当前不可用或未恢复；报告主要使用 cAdvisor/container 指标。
Fault context: current real-time evidence does not show active CPU, memory, Pod Kill, or network-delay fault pressure; the Agent keeps the recovery recommendation at observe.
基于当前 Kubernetes 与 Prometheus 实时证据，Agent 生成了恢复计划。由于当前服务实时状态为 healthy 且 CPU 使用率较低，本次建议以观察和继续采集证据为主，不自动执行重启。

## 恢复建议与执行保护

- 恢复计划状态 enabled：是
- 是否执行真实恢复命令 execute_recovery：否
- dry_run 状态：是
- 目标服务：`paymentservice`
- 根因指标：`cpu__paymentservice`
- 故障类型 fault_type：`cpu_stress`
- 决策 decision：`observe`
- 风险等级 risk_level：`low`

当前 execute_recovery=false / dry_run=true，Agent 只生成恢复建议，不执行真实恢复命令。

推荐动作：
- Current Kubernetes health is healthy and real-time Prometheus CPU/memory metrics are below thresholds.
- No explicit Pod Kill, CPU pressure, or memory pressure evidence is present; keep observing.

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

安全说明：
- execute_recovery=false / dry_run=true: Agent only generates recovery advice and never executes real recovery commands.
- agent.enable_recovery=false protects against automatic recovery.
- Commands such as rollout restart are shown only as manually confirmed drafts.
- CPU pressure threshold: 0.05.
- Memory pressure threshold: 150.0 MiB.
- Current memory working set: 49.32 MiB.

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
