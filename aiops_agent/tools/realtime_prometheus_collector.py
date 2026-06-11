"""Collect realtime Online Boutique metrics from Prometheus.

This module only performs readonly Prometheus queries through ``kubectl exec``.
It does not mutate Kubernetes resources.
"""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode


DEFAULT_SERVICES = [
    "frontend",
    "checkoutservice",
    "paymentservice",
    "productcatalogservice",
    "cartservice",
    "currencyservice",
    "shippingservice",
    "recommendationservice",
    "emailservice",
    "adservice",
    "redis-cart",
]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_path(project_root: Path, path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = project_root / path
    return path


def _run_kubectl_query_range(
    config: dict[str, Any],
    promql: str,
    start_epoch: int,
    end_epoch: int,
    step_seconds: int,
) -> tuple[dict[str, Any] | None, str | None]:
    prometheus_config = config.get("prometheus", {})
    kubectl = config.get("kubernetes", {}).get("kubectl", "kubectl")
    monitoring_namespace = prometheus_config.get("monitoring_namespace", "monitoring")
    deployment = prometheus_config.get("prometheus_deployment", "prometheus-deployment")
    timeout = int(prometheus_config.get("command_timeout_seconds", 15))
    params = urlencode(
        {
            "query": promql,
            "start": start_epoch,
            "end": end_epoch,
            "step": step_seconds,
        },
        quote_via=quote,
    )
    url = f"http://localhost:9090/api/v1/query_range?{params}"
    command = [
        kubectl,
        "exec",
        "-n",
        monitoring_namespace,
        f"deployment/{deployment}",
        "--",
        "wget",
        "-qO-",
        url,
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    except Exception as exc:
        return None, f"Prometheus query failed to execute: {exc}"
    if result.returncode != 0:
        return None, f"Prometheus query failed: {result.stderr.strip() or result.stdout.strip()}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, f"Prometheus returned invalid JSON: {exc}"
    return payload, None


def _extract_series(payload: dict[str, Any]) -> dict[int, float]:
    if payload.get("status") != "success":
        return {}
    results = (payload.get("data") or {}).get("result") or []
    if not results:
        return {}
    values = results[0].get("values") or []
    series: dict[int, float] = {}
    for timestamp, value in values:
        try:
            series[int(float(timestamp))] = float(value)
        except (TypeError, ValueError):
            continue
    return series


def collect_realtime_prometheus_metrics(
    config: dict[str, Any],
    namespace: str | None = None,
    duration_minutes: int = 5,
    step_seconds: int = 15,
    output_dir: str | Path | None = None,
    services: list[str] | None = None,
) -> dict[str, Any]:
    project_root = _project_root()
    namespace = namespace or config.get("prometheus", {}).get("service_namespace") or config.get("system", {}).get("namespace") or "online-boutique"
    services = services or list(DEFAULT_SERVICES)
    runtime_dir = output_dir or config.get("realtime_pipeline", {}).get("runtime_data_dir", "aiops_agent/runtime_data")
    output_path = _resolve_path(project_root, runtime_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    end_epoch = int(datetime.now(timezone.utc).timestamp())
    start_epoch = end_epoch - int(duration_minutes * 60)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_path / f"prometheus_realtime_{timestamp}.csv"
    meta_path = output_path / f"prometheus_realtime_{timestamp}.meta.json"

    warnings: list[str] = []
    raw_queries: dict[str, str] = {}
    collected: dict[str, dict[int, float]] = {}
    all_timestamps: set[int] = set()

    for service in services:
        queries = {
            f"{service}__cpu": f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod=~"{service}.*"}}[1m]))',
            f"{service}__memory": f'sum(container_memory_working_set_bytes{{namespace="{namespace}",pod=~"{service}.*"}})',
        }
        for column, query in queries.items():
            raw_queries[column] = query
            payload, warning = _run_kubectl_query_range(config, query, start_epoch, end_epoch, step_seconds)
            if warning:
                warnings.append(f"{column}: {warning}")
                collected[column] = {}
                continue
            series = _extract_series(payload or {})
            if not series:
                warnings.append(f"{column}: Prometheus returned no samples.")
            collected[column] = series
            all_timestamps.update(series.keys())

    if not all_timestamps:
        all_timestamps = set(range(start_epoch, end_epoch + 1, max(step_seconds, 1)))
        warnings.append("No Prometheus samples were collected; generated empty timestamp grid.")

    columns = [metric for service in services for metric in (f"{service}__cpu", f"{service}__memory")]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["timestamp", *columns])
        writer.writeheader()
        for epoch in sorted(all_timestamps):
            row = {"timestamp": datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()}
            for column in columns:
                value = collected.get(column, {}).get(epoch)
                row[column] = "" if value is None else value
            writer.writerow(row)

    metadata = {
        "namespace": namespace,
        "duration_minutes": duration_minutes,
        "step_seconds": step_seconds,
        "start_epoch": start_epoch,
        "end_epoch": end_epoch,
        "services": services,
        "csv_path": str(csv_path),
        "meta_path": str(meta_path),
        "raw_queries": raw_queries,
        "warnings": warnings,
    }
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8-sig")
    return metadata
