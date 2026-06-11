import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate_sample(rows: int = 720, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(rows)
    daily = np.sin(2 * np.pi * t / 180)
    slow = np.sin(2 * np.pi * t / 420)

    data = {
        "timestamp": pd.date_range("2026-06-01 10:00:00", periods=rows, freq="30s"),
        "frontend_request_rate": 85 + 10 * daily + rng.normal(0, 2.5, rows),
        "frontend_p95_latency_ms": 120 + 18 * daily + rng.normal(0, 5.0, rows),
        "frontend_error_rate": np.clip(0.012 + rng.normal(0, 0.004, rows), 0, None),
        "catalogue_cpu_usage": 0.38 + 0.06 * daily + rng.normal(0, 0.018, rows),
        "catalogue_memory_usage": 0.55 + 0.03 * slow + rng.normal(0, 0.012, rows),
        "orders_cpu_usage": 0.32 + 0.05 * daily + rng.normal(0, 0.018, rows),
        "orders_memory_usage": 0.48 + 0.02 * slow + rng.normal(0, 0.012, rows),
        "payment_cpu_usage": 0.27 + 0.04 * daily + rng.normal(0, 0.014, rows),
        "pod_restart_count": np.zeros(rows),
        "label": np.zeros(rows, dtype=int),
    }
    df = pd.DataFrame(data)

    # 模拟两类 ChaosMesh 故障：网络延迟和 Pod Kill/重启。
    fault_windows = [(260, 335), (500, 560)]
    for start, end in fault_windows:
        idx = slice(start, end)
        df.loc[idx, "label"] = 1

    idx = slice(fault_windows[0][0], fault_windows[0][1])
    df.loc[idx, "frontend_p95_latency_ms"] += rng.normal(130, 20, fault_windows[0][1] - fault_windows[0][0] + 1)
    df.loc[idx, "frontend_error_rate"] += rng.normal(0.06, 0.01, fault_windows[0][1] - fault_windows[0][0] + 1)
    df.loc[idx, "frontend_request_rate"] -= rng.normal(18, 4, fault_windows[0][1] - fault_windows[0][0] + 1)

    idx = slice(fault_windows[1][0], fault_windows[1][1])
    df.loc[idx, "catalogue_cpu_usage"] += rng.normal(0.24, 0.04, fault_windows[1][1] - fault_windows[1][0] + 1)
    df.loc[idx, "catalogue_memory_usage"] += rng.normal(0.12, 0.02, fault_windows[1][1] - fault_windows[1][0] + 1)
    df.loc[fault_windows[1][0] : fault_windows[1][0] + 8, "pod_restart_count"] = 1
    df.loc[idx, "frontend_p95_latency_ms"] += rng.normal(65, 15, fault_windows[1][1] - fault_windows[1][0] + 1)

    metric_cols = [c for c in df.columns if c not in {"timestamp", "label"}]
    for col in metric_cols:
        df[col] = df[col].clip(lower=0)
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/sample_kpi_metrics.csv")
    parser.add_argument("--rows", type=int, default=720)
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = generate_sample(args.rows)
    df.to_csv(out, index=False)
    print(f"wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
