import argparse
import subprocess
import time
from pathlib import Path

import pandas as pd

from collect_online_boutique_metrics import deployment_ready, pod_metrics, request_metrics


PATHS = [
    "/",
    "/product/OLJCESPC7Z",
    "/product/66VCHSJNUP",
    "/cart",
]


def kubectl(args: list[str], timeout: int = 60) -> str:
    proc = subprocess.run(["kubectl", *args], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return proc.stdout.strip()


def apply_chaos(path: Path) -> None:
    kubectl(["apply", "-f", str(path)])


def delete_chaos(name: str, namespace: str) -> None:
    subprocess.run(
        ["kubectl", "delete", "podchaos", name, "-n", namespace, "--ignore-not-found=true"],
        capture_output=True,
        text=True,
        timeout=60,
    )


def collect_podchaos_status(name: str, namespace: str) -> str:
    proc = subprocess.run(
        ["kubectl", "describe", "podchaos", name, "-n", namespace],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.stdout if proc.returncode == 0 else proc.stderr


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--namespace", default="online-boutique")
    parser.add_argument("--chaos-namespace", default="online-boutique")
    parser.add_argument("--chaos-name", default="online-boutique-productcatalog-pod-kill")
    parser.add_argument("--chaos-yaml", default="scripts/chaos-online-boutique-productcatalog-podkill.yaml")
    parser.add_argument("--out", default="data/online_boutique_chaosmesh_metrics.csv")
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--fault-start", type=int, default=45)
    parser.add_argument("--fault-end", type=int, default=75)
    parser.add_argument("--evidence-out", default="docs/chaosmesh_kpi_collection_evidence.md")
    parser.add_argument("--keep-chaos", action="store_true")
    args = parser.parse_args()

    chaos_yaml = Path(args.chaos_yaml)
    rows = []
    events: list[str] = []
    chaos_applied = False
    started_at = pd.Timestamp.now().isoformat()

    try:
        for i in range(args.samples):
            if i == args.fault_start:
                apply_chaos(chaos_yaml)
                chaos_applied = True
                events.append(f"sample {i}: applied {chaos_yaml}")
                time.sleep(2.0)
                events.append(collect_podchaos_status(args.chaos_name, args.chaos_namespace))

            path = PATHS[i % len(PATHS)]
            row = {
                "timestamp": pd.Timestamp.now().isoformat(),
                "sample_index": i,
                "label": 1 if args.fault_start <= i < args.fault_end else 0,
                "fault_active": 1.0 if args.fault_start <= i < args.fault_end else 0.0,
                "chaosmesh_active": 1.0 if chaos_applied and i >= args.fault_start else 0.0,
            }
            row.update(request_metrics(args.base_url, path))
            row.update(pod_metrics(args.namespace))
            row.update(deployment_ready(args.namespace))
            rows.append(row)
            print(
                f"{i + 1}/{args.samples} label={row['label']} "
                f"latency={row['frontend_latency_ms']:.1f}ms error={row['frontend_error']}"
            )
            time.sleep(args.interval)
    finally:
        if chaos_applied and not args.keep_chaos:
            delete_chaos(args.chaos_name, args.chaos_namespace)
            events.append(f"cleanup: deleted PodChaos {args.chaos_name}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)

    evidence = Path(args.evidence_out)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    finished_at = pd.Timestamp.now().isoformat()
    evidence.write_text(
        "\n".join(
            [
                "# ChaosMesh KPI Collection Evidence",
                "",
                f"started_at: {started_at}",
                f"finished_at: {finished_at}",
                f"samples: {args.samples}",
                f"interval_seconds: {args.interval}",
                f"fault_window_samples: {args.fault_start}-{args.fault_end - 1}",
                f"chaos_yaml: {args.chaos_yaml}",
                f"output_csv: {args.out}",
                "",
                "## Events",
                "",
                *["```text\n" + event.strip() + "\n```" for event in events],
            ]
        ),
        encoding="utf-8",
    )
    print(f"wrote {out}")
    print(f"wrote {evidence}")


if __name__ == "__main__":
    main()
