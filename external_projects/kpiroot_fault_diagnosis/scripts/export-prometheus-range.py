import argparse
import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


QUERIES = {
    "alarm_frontend_probe_duration": 'probe_duration_seconds{job="online-boutique-frontend-blackbox"}',
    "alarm_frontend_probe_success": 'probe_success{job="online-boutique-frontend-blackbox"}',
    "alarm_frontend_cpu": 'sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="online-boutique", pod=~"frontend-.*"}[1m]))',
    "cpu_by_pod": 'sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="online-boutique"}[1m]))',
    "memory_by_pod": 'sum by (pod) (container_memory_working_set_bytes{namespace="online-boutique"})',
    "restarts_by_pod_container": 'sum by (pod, container) (kube_pod_container_status_restarts_total{namespace="online-boutique"})',
    "pod_running_by_pod": 'kube_pod_status_phase{namespace="online-boutique", phase="Running"}',
    "fs_reads_by_pod": 'sum by (pod) (rate(container_fs_reads_bytes_total{namespace="online-boutique"}[1m]))',
    "fs_writes_by_pod": 'sum by (pod) (rate(container_fs_writes_bytes_total{namespace="online-boutique"}[1m]))',
}


def parse_time(value: str) -> float:
    if re.fullmatch(r"\d+(\.\d+)?", value):
        return float(value)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def stable_pod_name(pod: str) -> str:
    return re.sub(r"-[0-9a-f]{8,10}-[a-z0-9]{5}$", "", pod)


def series_name(query_name: str, metric: dict) -> str:
    pod = metric.get("pod")
    container = metric.get("container")
    instance = metric.get("instance")

    if query_name.startswith("alarm_frontend_probe"):
        return query_name
    if pod:
        service = stable_pod_name(pod)
        if query_name == "restarts_by_pod_container" and container:
            return f"restart__{service}__{container}"
        if query_name == "pod_running_by_pod":
            return f"running__{service}"
        prefix = query_name.replace("_by_pod", "")
        return f"{prefix}__{service}"
    if instance:
        safe = re.sub(r"[^A-Za-z0-9_]+", "_", instance).strip("_")
        return f"{query_name}__{safe}"
    return query_name


def prom_query_range(base_url: str, query: str, start: float, end: float, step: int) -> dict:
    params = urllib.parse.urlencode(
        {
            "query": query,
            "start": f"{start:.0f}",
            "end": f"{end:.0f}",
            "step": str(step),
        }
    )
    url = f"{base_url.rstrip('/')}/api/v1/query_range?{params}"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    return payload


def write_raw_csv(path: Path, result: list) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["series_name", "timestamp", "value", "labels_json"])
        for item in result:
            labels = item.get("metric", {})
            name = labels.get("__series_name__", "")
            labels_json = json.dumps({k: v for k, v in labels.items() if k != "__series_name__"}, sort_keys=True)
            for timestamp, value in item.get("values", []):
                writer.writerow([name, int(float(timestamp)), value, labels_json])


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Prometheus query_range data for Phase 2 and KPIRoot.")
    parser.add_argument("--prometheus-url", default="http://127.0.0.1:9090")
    parser.add_argument("--start", required=True, help="ISO timestamp or Unix timestamp.")
    parser.add_argument("--end", required=True, help="ISO timestamp or Unix timestamp.")
    parser.add_argument("--step", type=int, default=15)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    start = parse_time(args.start)
    end = parse_time(args.end)
    if end <= start:
        raise ValueError("--end must be later than --start")

    output = Path(args.output)
    raw_dir = output / "prometheus_raw"
    processed_dir = output / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    wide = {}
    series_labels = {}

    for query_name, query in QUERIES.items():
        print(f"Exporting {query_name}...", file=sys.stderr)
        payload = prom_query_range(args.prometheus_url, query, start, end, args.step)
        result = payload["data"]["result"]

        for item in result:
            name = series_name(query_name, item.get("metric", {}))
            item.setdefault("metric", {})["__series_name__"] = name
            series_labels[name] = {k: v for k, v in item["metric"].items() if k != "__series_name__"}
            for timestamp, value in item.get("values", []):
                ts = int(float(timestamp))
                wide.setdefault(ts, {})[name] = value

        write_raw_csv(raw_dir / f"{query_name}.csv", result)

    all_series = sorted(series_labels)
    matrix_path = processed_dir / "kpi_matrix.csv"
    with matrix_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", *all_series])
        for ts in sorted(wide):
            row = [ts]
            values = wide[ts]
            row.extend(values.get(name, "") for name in all_series)
            writer.writerow(row)

    labels_path = processed_dir / "series_labels.json"
    labels_path.write_text(json.dumps(series_labels, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Wrote {matrix_path}")
    print(f"Wrote {labels_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
