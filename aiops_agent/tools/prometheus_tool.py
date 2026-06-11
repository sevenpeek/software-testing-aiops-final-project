"""Read-only Prometheus metric collection through kubectl exec."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any
from urllib.parse import quote


def _run_command(command: list[str], timeout_seconds: int, warnings: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        warnings.append(f"Command timed out after {timeout_seconds}s: {' '.join(command)}")
        return ""
    except FileNotFoundError:
        warnings.append(f"kubectl executable not found: {command[0]}")
        return ""
    except Exception as exc:  # pragma: no cover - defensive for local runtime issues
        warnings.append(f"Command failed unexpectedly: {' '.join(command)}; error={exc}")
        return ""

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        warnings.append(f"Command failed: {' '.join(command)}; {stderr or stdout or completed.returncode}")
        return ""
    return stdout


def _parse_first_value(query_name: str, response_text: str, warnings: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "status": None,
        "raw_value": None,
        "numeric_value": None,
        "result_count": 0,
    }
    if not response_text:
        warnings.append(f"Prometheus query returned empty response: {query_name}")
        return parsed

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        warnings.append(f"Prometheus query returned invalid JSON for {query_name}: {exc}")
        return parsed

    parsed["status"] = payload.get("status")
    if payload.get("status") != "success":
        warnings.append(f"Prometheus query status is not success for {query_name}: {payload.get('status')}")
        return parsed

    results = payload.get("data", {}).get("result", [])
    parsed["result_count"] = len(results)
    if not results:
        warnings.append(f"Prometheus query result is empty: {query_name}")
        return parsed

    value = results[0].get("value")
    if not isinstance(value, list) or len(value) < 2:
        warnings.append(f"Prometheus query first result has no vector value: {query_name}")
        return parsed

    raw_value = str(value[1])
    parsed["raw_value"] = raw_value
    try:
        parsed["numeric_value"] = float(raw_value)
    except ValueError:
        warnings.append(f"Prometheus query value is not numeric for {query_name}: {raw_value}")
    return parsed


def _query_prometheus(
    kubectl: str,
    monitoring_namespace: str,
    prometheus_deployment: str,
    promql: str,
    timeout_seconds: int,
    warnings: list[str],
) -> str:
    encoded_query = quote(promql, safe="")
    url = f"http://localhost:9090/api/v1/query?query={encoded_query}"
    command = [
        kubectl,
        "exec",
        "-n",
        monitoring_namespace,
        f"deployment/{prometheus_deployment}",
        "--",
        "wget",
        "-qO-",
        url,
    ]
    return _run_command(command, timeout_seconds, warnings)


def _mib(value_bytes: float | None) -> float | None:
    if value_bytes is None:
        return None
    return value_bytes / 1024.0 / 1024.0


def _build_interpretation(prometheus_available: bool, summary: dict[str, Any], service_name: str | None) -> str:
    if not prometheus_available:
        return "Prometheus 查询不可用，需要检查 monitoring namespace、Prometheus Pod 状态或 kubectl exec 权限。"

    parts: list[str] = []
    service_cpu_rate = summary.get("service_cpu_rate")
    service_container_count = summary.get("service_container_count")
    memory_mib = summary.get("service_memory_working_set_mib")

    if service_cpu_rate is None:
        parts.append("未能查询到服务 CPU rate，需要检查 Prometheus scrape 配置或容器指标标签。")
    elif service_cpu_rate < 0.01:
        parts.append(f"当前 {service_name} 实时 CPU 使用率较低，暂未显示明显 CPU 压力。")
    elif service_cpu_rate >= 0.5:
        parts.append(f"当前 {service_name} CPU rate 较高，实时指标支持 CPU 压力判断。")
    else:
        parts.append(f"当前 {service_name} CPU rate 处于中间水平，需要结合历史基线判断。")

    if memory_mib is not None:
        parts.append(f"当前 {service_name} memory working set 约为 {memory_mib:.2f} MiB。")
    if service_container_count is not None and service_container_count > 0:
        parts.append("Prometheus 已采集到该服务的容器级指标。")
    else:
        parts.append("Prometheus 未查询到该服务容器级指标，需要检查 pod 名称匹配或 scrape 配置。")

    parts.append("当前 Prometheus 阶段主要使用 cAdvisor/container 指标，不依赖 kube-state-metrics。")
    return " ".join(parts)


def _fault_context(config: dict[str, Any]) -> str:
    return str(config.get("faults", {}).get("default_fault_type") or "cpu_stress")


def collect_prometheus_metrics(config: dict[str, Any], service_name: str | None) -> dict[str, Any]:
    """Collect read-only Prometheus metrics for the KPIRoot Top1 service."""

    prometheus_config = config.get("prometheus", {})
    enabled = bool(prometheus_config.get("enabled", False))
    query_mode = prometheus_config.get("query_mode", "kubectl_exec")
    monitoring_namespace = prometheus_config.get("monitoring_namespace", "monitoring")
    prometheus_deployment = prometheus_config.get("prometheus_deployment", "prometheus-deployment")
    service_namespace = prometheus_config.get("service_namespace") or config.get("system", {}).get("namespace") or "online-boutique"
    timeout_seconds = int(prometheus_config.get("command_timeout_seconds", 15))
    kubectl = config.get("kubernetes", {}).get("kubectl", "kubectl")
    warnings: list[str] = []

    result: dict[str, Any] = {
        "enabled": enabled,
        "query_mode": query_mode,
        "monitoring_namespace": monitoring_namespace,
        "prometheus_deployment": prometheus_deployment,
        "service_name": service_name,
        "prometheus_available": False,
        "metrics": {},
        "raw_queries": {},
        "optional_notes": [],
        "summary": {
            "cpu_series_count": None,
            "online_boutique_cpu_total_rate": None,
            "service_cpu_rate": None,
            "service_memory_working_set_bytes": None,
            "service_memory_working_set_mib": None,
            "service_container_count": None,
            "container_restart_count": None,
            "interpretation": "",
            "memory_interpretation": "",
            "network_latency_interpretation": "",
        },
        "warnings": warnings,
    }

    if not enabled:
        result["summary"]["interpretation"] = "Prometheus metrics collection is disabled."
        return result
    if query_mode != "kubectl_exec":
        warnings.append(f"Unsupported Prometheus query_mode: {query_mode}")
        result["summary"]["interpretation"] = "Prometheus 查询模式不受支持。"
        return result
    if not service_name:
        warnings.append("Prometheus collection skipped because service_name is empty.")
        result["summary"]["interpretation"] = "Prometheus 查询缺少服务名。"
        return result
    if shutil.which(kubectl) is None:
        warnings.append(f"kubectl is not available in PATH: {kubectl}")
        result["summary"]["interpretation"] = "Prometheus 查询不可用：kubectl 不在 PATH 中。"
        return result

    queries = {
        "prometheus_up": "up",
        "online_boutique_cpu_series_count": f'count(container_cpu_usage_seconds_total{{namespace="{service_namespace}"}})',
        "online_boutique_cpu_total_rate": f'sum(rate(container_cpu_usage_seconds_total{{namespace="{service_namespace}"}}[1m]))',
        "service_cpu_rate": f'sum(rate(container_cpu_usage_seconds_total{{namespace="{service_namespace}",pod=~"{service_name}.*"}}[1m]))',
        "service_memory_working_set": f'sum(container_memory_working_set_bytes{{namespace="{service_namespace}",pod=~"{service_name}.*"}})',
        "service_container_count": f'count(container_cpu_usage_seconds_total{{namespace="{service_namespace}",pod=~"{service_name}.*"}})',
        "container_restart_count": f'sum(kube_pod_container_status_restarts_total{{namespace="{service_namespace}",pod=~"{service_name}.*"}})',
    }
    result["raw_queries"] = queries

    optional_queries = {"container_restart_count"}
    for query_name, promql in queries.items():
        query_warnings = [] if query_name in optional_queries else warnings
        response = _query_prometheus(
            kubectl=kubectl,
            monitoring_namespace=monitoring_namespace,
            prometheus_deployment=prometheus_deployment,
            promql=promql,
            timeout_seconds=timeout_seconds,
            warnings=query_warnings,
        )
        result["metrics"][query_name] = {
            "promql": promql,
            **_parse_first_value(query_name, response, query_warnings),
        }
        if query_name in optional_queries and query_warnings:
            result["metrics"][query_name]["notes"] = query_warnings
            result["optional_notes"].extend(query_warnings)

    result["prometheus_available"] = result["metrics"].get("prometheus_up", {}).get("status") == "success"

    summary = result["summary"]
    summary["cpu_series_count"] = result["metrics"].get("online_boutique_cpu_series_count", {}).get("numeric_value")
    summary["online_boutique_cpu_total_rate"] = result["metrics"].get("online_boutique_cpu_total_rate", {}).get("numeric_value")
    summary["service_cpu_rate"] = result["metrics"].get("service_cpu_rate", {}).get("numeric_value")
    summary["service_memory_working_set_bytes"] = result["metrics"].get("service_memory_working_set", {}).get("numeric_value")
    summary["service_memory_working_set_mib"] = _mib(summary["service_memory_working_set_bytes"])
    summary["service_container_count"] = result["metrics"].get("service_container_count", {}).get("numeric_value")
    summary["container_restart_count"] = result["metrics"].get("container_restart_count", {}).get("numeric_value")
    summary["interpretation"] = _build_interpretation(result["prometheus_available"], summary, service_name)
    memory_mib = summary.get("service_memory_working_set_mib")
    memory_threshold = float(
        config.get("faults", {}).get(
            "memory_pressure_threshold_mib",
            config.get("recovery", {}).get("memory_pressure_threshold_mib", 150),
        )
    )
    if memory_mib is None:
        summary["memory_interpretation"] = "No memory working-set metric was returned for the target service."
    elif memory_mib >= memory_threshold:
        summary["memory_interpretation"] = (
            f"Current memory working set is {memory_mib:.2f} MiB, above threshold {memory_threshold:.2f} MiB."
        )
    else:
        summary["memory_interpretation"] = (
            f"Current memory working set is {memory_mib:.2f} MiB, below threshold {memory_threshold:.2f} MiB."
        )
    summary["network_latency_interpretation"] = (
        "Current Prometheus queries do not include application latency/error-rate metrics; "
        "network delay faults require additional business metrics for strong diagnosis."
    )
    if _fault_context(config) == "network_delay":
        warnings.append(summary["network_latency_interpretation"])

    return result
