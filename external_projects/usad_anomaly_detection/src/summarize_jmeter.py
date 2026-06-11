import argparse
import csv
from pathlib import Path


def read_jtl(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def summarize(path: Path, threads: int) -> dict[str, object]:
    rows = read_jtl(path)
    elapsed = [float(r.get("elapsed", 0) or 0) for r in rows]
    success = [str(r.get("success", "")).lower() == "true" for r in rows]
    total = len(rows)
    success_count = sum(1 for ok in success if ok)
    error_count = total - success_count
    avg = sum(elapsed) / total if total else 0.0
    sorted_elapsed = sorted(elapsed)
    p95_index = int(0.95 * (total - 1)) if total else 0
    labels = sorted({r.get("label", "") for r in rows if r.get("label")})
    return {
        "threads": threads,
        "samples": total,
        "success": success_count,
        "errors": error_count,
        "error_rate": error_count / total if total else 0.0,
        "avg_latency_ms": avg,
        "min_latency_ms": min(elapsed) if elapsed else 0.0,
        "p95_latency_ms": sorted_elapsed[p95_index] if elapsed else 0.0,
        "max_latency_ms": max(elapsed) if elapsed else 0.0,
        "labels": ", ".join(labels),
    }


def write_outputs(rows: list[dict[str, object]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    headers = [
        "threads",
        "samples",
        "success",
        "errors",
        "error_rate",
        "avg_latency_ms",
        "min_latency_ms",
        "p95_latency_ms",
        "max_latency_ms",
        "labels",
    ]
    csv_path = out_dir / "jmeter_matrix_summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    md_lines = [
        "# JMeter 10/30/50 Concurrency Summary",
        "",
        "| 并发线程 | 样本数 | 错误率 | 平均响应(ms) | P95(ms) | 最大响应(ms) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        md_lines.append(
            f"| {r['threads']} | {r['samples']} | {float(r['error_rate']) * 100:.2f}% | "
            f"{float(r['avg_latency_ms']):.2f} | {float(r['p95_latency_ms']):.2f} | {float(r['max_latency_ms']):.2f} |"
        )
    (out_dir / "jmeter_matrix_summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(csv_path)
    print(out_dir / "jmeter_matrix_summary.md")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="outputs_jmeter_matrix")
    parser.add_argument("items", nargs="+", help="thread_count=jtl_path")
    args = parser.parse_args()

    rows = []
    for item in args.items:
        threads_raw, path_raw = item.split("=", 1)
        rows.append(summarize(Path(path_raw), int(threads_raw)))
    write_outputs(rows, Path(args.out_dir))


if __name__ == "__main__":
    main()
