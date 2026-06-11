# Prometheus/Grafana Monitoring Evidence

## Environment

- Date: 2026-06-03
- Kubernetes environment: minikube, Kubernetes v1.32.0, Docker driver
- Monitored system: Online Boutique namespace `online-boutique`
- Monitoring namespace: `monitoring`

## Deployment Result

The lightweight monitoring stack was deployed with:

```powershell
kubectl apply -f final_project\monitoring\lightweight-monitoring.yaml
kubectl rollout restart deployment/prometheus -n monitoring
kubectl rollout restart deployment/grafana -n monitoring
```

Current monitoring pods:

```text
anomaly-detector      1/1 Running
grafana               1/1 Running
kube-state-metrics    1/1 Running
prometheus            1/1 Running
```

Prometheus was intentionally configured as a lightweight collector after the Docker Desktop recovery:

- scrape `prometheus` itself
- scrape `kube-state-metrics`
- scrape annotated Kubernetes service endpoints such as CoreDNS
- do not scrape node cAdvisor through the apiserver proxy

This avoids unnecessary pressure on a single-node minikube cluster while still providing Kubernetes service health, Pod readiness, restart, phase, and deployment replica metrics.

## Metric Verification

Prometheus query:

```promql
sum(kube_pod_status_ready{exported_namespace="online-boutique",condition="true"})
```

Result:

```text
12
```

Prometheus query:

```promql
sum(kube_pod_container_status_restarts_total{exported_namespace="online-boutique"})
```

Result:

```text
12
```

The restart count is expected after the Windows/Docker Desktop reboot recovery. It also proves that the dashboard can capture operational restart events.

Prometheus active scrape targets after the lightweight configuration:

```text
kubernetes-service-endpoints  up  http://10.244.0.23:9153/metrics
kubernetes-service-endpoints  up  http://10.244.0.30:8080/metrics
prometheus                    up  http://localhost:9090/metrics
```

## Grafana Dashboard

Dashboard URL:

```text
http://127.0.0.1:3000/d/online-boutique-monitoring/online-boutique-monitoring?orgId=1
```

Dashboard panels:

- Online Boutique Ready Pods
- Container Restarts
- Pod Phase Distribution
- Pod Ready State by Pod
- Ready Replicas by Deployment

Screenshot:

```text
final_project/docs/screenshots/grafana_online_boutique_dashboard.png
```
