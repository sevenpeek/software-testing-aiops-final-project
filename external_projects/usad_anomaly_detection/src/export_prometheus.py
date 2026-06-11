import argparse
import datetime as dt
import json
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


DEFAULT_QUERIES = {
    "container_cpu_usage_seconds_total_rate": 'sum(rate(container_cpu_usage_seconds_total{namespace="online-boutique"}[1m])) by (pod)',
    "container_memory_working_set_bytes": 'sum(container_memory_working_set_bytes{namespace="online-boutique"}) by (pod)',
    "kube_pod_container_status_restarts_total": 'sum(kube_pod_container_status_restarts_total{namespace="online-boutique"}) by (pod)',
    "frontend_requests": 'sum(rate(request_duration_seconds_count{namespace="online-boutique"}[1m]))',
    "frontend_latency_sum": 'sum(rate(request_duration_seconds_sum{namespace="online-boutique"}[1m]))',
}


def parse_time(value: str) -> float:
    return dt.datetime.fromisoformat(value).timestamp()


def query_range(base_url: str, query: str, start: str, end: str, step: int) -> dict:
    params = urllib.parse.urlencode(
        {
            "query": query,
            "start": parse_time(start),
            "end": parse_time(end),
            "step": step,
        }
    )
    url = f"{base_url.rstrip('/')}/api/v1/query_range?{params}"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    return payload["data"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prometheus", required=True, help="Prometheus base URL, e.g. http://127.0.0.1:9090")
    parser.add_argument("--start", required=True, help="ISO time, e.g. 2026-06-01T10:00:00")
    parser.add_argument("--end", required=True, help="ISO time, e.g. 2026-06-01T11:00:00")
    parser.add_argument("--step", type=int, default=30)
    parser.add_argument("--out", default="data/prometheus_online_boutique_metrics.csv")
    args = parser.parse_args()

    frames = []
    for metric_name, query in DEFAULT_QUERIES.items():
        data = query_range(args.prometheus, query, args.start, args.end, args.step)
        for series in data.get("result", []):
            pod = series.get("metric", {}).get("pod", "system")
            col = f"{metric_name}_{pod}".replace("-", "_")
            part = pd.DataFrame(series["values"], columns=["timestamp", col])
            part["timestamp"] = pd.to_datetime(part["timestamp"], unit="s")
            part[col] = pd.to_numeric(part[col], errors="coerce")
            frames.append(part)

    if not frames:
        raise RuntimeError("no Prometheus data returned; check metric names and service address")

    df = frames[0]
    for frame in frames[1:]:
        df = df.merge(frame, on="timestamp", how="outer")
    df = df.sort_values("timestamp").ffill().bfill()
    df["label"] = 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"wrote {out} ({len(df)} rows, {len(df.columns) - 2} metrics)")


if __name__ == "__main__":
    main()
