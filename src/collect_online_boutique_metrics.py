import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd


DEPLOYMENTS = [
    "frontend",
    "productcatalogservice",
    "cartservice",
    "checkoutservice",
    "recommendationservice",
    "paymentservice",
    "shippingservice",
]


PATHS = [
    "/",
    "/product/OLJCESPC7Z",
    "/product/66VCHSJNUP",
    "/cart",
]


def kubectl_json(args: list[str]) -> dict:
    cmd = ["kubectl", *args, "-o", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return json.loads(proc.stdout)


def kubectl(args: list[str]) -> None:
    proc = subprocess.run(["kubectl", *args], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())


def deployment_ready(namespace: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for name in DEPLOYMENTS:
        try:
            data = kubectl_json(["get", "deployment", name, "-n", namespace])
            spec = data.get("spec", {}).get("replicas", 0) or 0
            ready = data.get("status", {}).get("readyReplicas", 0) or 0
            values[f"{name}_ready_ratio"] = ready / spec if spec else 0.0
        except Exception:
            values[f"{name}_ready_ratio"] = 0.0
    return values


def pod_metrics(namespace: str) -> dict[str, float]:
    data = kubectl_json(["get", "pods", "-n", namespace])
    items = data.get("items", [])
    total_restarts = 0
    not_ready = 0
    running = 0
    for pod in items:
        phase = pod.get("status", {}).get("phase")
        if phase == "Running":
            running += 1
        statuses = pod.get("status", {}).get("containerStatuses", []) or []
        if not statuses or not all(s.get("ready", False) for s in statuses):
            not_ready += 1
        for status in statuses:
            total_restarts += status.get("restartCount", 0) or 0
    return {
        "running_pods": float(running),
        "not_ready_pods": float(not_ready),
        "total_restarts": float(total_restarts),
    }


def request_metrics(base_url: str, path: str) -> dict[str, float]:
    url = base_url.rstrip("/") + path
    start = time.perf_counter()
    status = 0
    size = 0
    ok = 0
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read()
            status = response.status
            size = len(body)
            ok = 1 if 200 <= status < 400 else 0
    except urllib.error.HTTPError as exc:
        status = exc.code
        size = len(exc.read() or b"")
    except Exception:
        status = 0
    elapsed = (time.perf_counter() - start) * 1000
    return {
        "frontend_latency_ms": elapsed,
        "frontend_status_code": float(status),
        "frontend_success": float(ok),
        "frontend_error": 0.0 if ok else 1.0,
        "frontend_response_bytes": float(size),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--namespace", default="online-boutique")
    parser.add_argument("--out", default="data/online_boutique_real_metrics.csv")
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--fault-start", type=int, default=45)
    parser.add_argument("--fault-end", type=int, default=75)
    parser.add_argument("--fault-deployment", default="productcatalogservice")
    args = parser.parse_args()

    rows = []
    fault_active = False
    for i in range(args.samples):
        if i == args.fault_start:
            kubectl(["scale", "deployment", args.fault_deployment, "--replicas=0", "-n", args.namespace])
            fault_active = True
        if i == args.fault_end:
            kubectl(["scale", "deployment", args.fault_deployment, "--replicas=1", "-n", args.namespace])
            fault_active = False

        path = PATHS[i % len(PATHS)]
        row = {
            "timestamp": pd.Timestamp.now().isoformat(),
            "sample_index": i,
            "label": 1 if args.fault_start <= i < args.fault_end else 0,
            "fault_active": 1.0 if fault_active else 0.0,
        }
        row.update(request_metrics(args.base_url, path))
        row.update(pod_metrics(args.namespace))
        row.update(deployment_ready(args.namespace))
        rows.append(row)
        print(f"{i+1}/{args.samples} label={row['label']} latency={row['frontend_latency_ms']:.1f}ms error={row['frontend_error']}")
        time.sleep(args.interval)

    if fault_active:
        kubectl(["scale", "deployment", args.fault_deployment, "--replicas=1", "-n", args.namespace])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

