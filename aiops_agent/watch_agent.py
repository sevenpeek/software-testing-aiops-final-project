"""Automatic readonly watcher for AIOps Agent.

The watcher only polls Prometheus and generates diagnosis reports. It never
executes recovery commands or mutates Kubernetes resources.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.kpiroot_tool import analyze_kpiroot
from tools.prometheus_tool import collect_prometheus_metrics


HISTORY_FIELDS = [
    "timestamp",
    "service",
    "service_cpu_rate",
    "threshold",
    "prometheus_available",
    "triggered",
    "recovery_decision",
    "risk_level",
    "report_path",
    "mode",
    "llm_output_path",
    "llm_enabled",
    "llm_executed",
]


def _load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _resolve_project_path(project_root: Path, path_arg: str) -> Path:
    path = Path(path_arg)
    if not path.is_absolute():
        path = project_root / path
    return path


def _get_top_service(config: dict[str, Any], project_root: Path) -> str:
    try:
        kpiroot_result = analyze_kpiroot(config, project_root)
        return kpiroot_result.get("top_service") or "paymentservice"
    except Exception as exc:
        print(f"WARNING: failed to read KPIRoot top_service: {exc}", flush=True)
        return "paymentservice"


def _run_command(
    command: list[str],
    project_root: Path,
    env: dict[str, str] | None = None,
    timeout: int = 240,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(project_root),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=env,
    )


def _run_full_diagnosis(project_root: Path, config_arg: str) -> subprocess.CompletedProcess[str]:
    return _run_command([sys.executable, "aiops_agent\\run_agent.py", "--config", config_arg], project_root)


def _run_llm_diagnosis(
    project_root: Path,
    config_arg: str,
    alert: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return _run_command(
        [
            sys.executable,
            "aiops_agent\\veadk_agent.py",
            "--config",
            config_arg,
            "--alert",
            alert,
            "--llm",
        ],
        project_root,
        env=env,
        timeout=360,
    )


def _archive_report(project_root: Path, timestamp: str) -> Path | None:
    source = project_root / "aiops_agent" / "outputs" / "diagnosis_report.md"
    if not source.exists():
        print(f"WARNING: diagnosis report not found: {source}", flush=True)
        return None

    target = project_root / "aiops_agent" / "outputs" / f"auto_diagnosis_{timestamp}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def _save_text(project_root: Path, timestamp: str, text: str) -> Path:
    target = project_root / "aiops_agent" / "outputs" / f"llm_diagnosis_{timestamp}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8-sig")
    return target


def _print_process_output(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout.rstrip(), flush=True)
    if result.stderr:
        print(result.stderr.rstrip(), flush=True)


def _service_cpu_rate(prometheus_metrics: dict[str, Any]) -> float | None:
    value = (prometheus_metrics.get("summary") or {}).get("service_cpu_rate")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_agent_output(output: str) -> tuple[str, str]:
    decision_match = re.search(r"Recovery decision:\s*(.+)", output)
    risk_match = re.search(r"Recovery risk_level:\s*(.+)", output)
    decision = decision_match.group(1).strip() if decision_match else ""
    risk_level = risk_match.group(1).strip() if risk_match else ""
    return decision, risk_level


def _append_history(history_file: Path, row: dict[str, Any]) -> None:
    history_file.parent.mkdir(parents=True, exist_ok=True)
    exists = history_file.exists()
    with history_file.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=HISTORY_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in HISTORY_FIELDS})


def _make_history_row(
    timestamp_text: str,
    service: str,
    service_cpu_rate: float | None,
    threshold: float,
    prometheus_available: bool,
    triggered: bool,
    mode: str,
    llm_enabled: bool,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp_text,
        "service": service,
        "service_cpu_rate": service_cpu_rate,
        "threshold": threshold,
        "prometheus_available": prometheus_available,
        "triggered": triggered,
        "recovery_decision": "",
        "risk_level": "",
        "report_path": "",
        "mode": mode,
        "llm_output_path": "",
        "llm_enabled": llm_enabled,
        "llm_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Readonly AIOps Agent watcher")
    parser.add_argument("--config", default="aiops_agent\\config.json", help="Path to config.json")
    parser.add_argument("--interval", type=int, default=30, help="Watch interval in seconds")
    parser.add_argument("--max-rounds", type=int, default=0, help="Maximum rounds, 0 means forever")
    parser.add_argument("--cooldown", type=int, default=60, help="Seconds to suppress repeated triggers")
    parser.add_argument("--trigger-once", action="store_true", help="Exit after the first completed anomaly trigger")
    parser.add_argument("--history-file", default="aiops_agent\\outputs\\watch_history.csv", help="CSV history path")
    parser.add_argument("--llm", action="store_true", help="Run veadk_agent.py --llm after a local trigger")
    parser.add_argument("--alert", default="", help="Alert text for LLM diagnosis")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Keep recovery dry-run only")
    args = parser.parse_args()

    agent_dir = Path(__file__).resolve().parent
    project_root = agent_dir.parent
    config_path = _resolve_project_path(project_root, args.config)
    history_file = _resolve_project_path(project_root, args.history_file)

    print("AIOps Watch Agent started.", flush=True)
    print(f"Config path: {config_path}", flush=True)
    print(f"Project root: {project_root}", flush=True)
    print(f"Dry run: {args.dry_run}", flush=True)
    print(f"Cooldown: {args.cooldown}", flush=True)
    print(f"Trigger once: {args.trigger_once}", flush=True)
    print(f"History file: {history_file}", flush=True)

    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}", flush=True)
        return 1

    config = _load_config(config_path)
    threshold = float(config.get("recovery", {}).get("cpu_pressure_threshold", 0.05))
    top_service = _get_top_service(config, project_root)
    last_trigger_time = 0.0
    rounds = 0

    print(f"Watch service: {top_service}", flush=True)
    print(f"CPU threshold: {threshold}", flush=True)

    while True:
        rounds += 1
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        timestamp_text = now.strftime("%Y-%m-%d %H:%M:%S")

        prometheus_metrics = collect_prometheus_metrics(config, top_service)
        service_cpu_rate = _service_cpu_rate(prometheus_metrics)
        prometheus_available = bool(prometheus_metrics.get("prometheus_available"))
        print(f"[{timestamp_text}] service_cpu_rate={service_cpu_rate}, threshold={threshold}", flush=True)

        over_threshold = service_cpu_rate is not None and service_cpu_rate >= threshold
        in_cooldown = (time.time() - last_trigger_time) < max(args.cooldown, 0)
        triggered = bool(over_threshold and not in_cooldown)
        mode = "llm_agent" if args.llm else "local_rule"
        row = _make_history_row(
            timestamp_text,
            top_service,
            service_cpu_rate,
            threshold,
            prometheus_available,
            triggered,
            mode,
            args.llm,
        )

        if triggered:
            print("Anomaly trigger detected.", flush=True)
            last_trigger_time = time.time()
            result = _run_full_diagnosis(project_root, args.config)
            output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
            _print_process_output(result)
            decision, risk_level = _parse_agent_output(output)
            row["recovery_decision"] = decision
            row["risk_level"] = risk_level

            archived_report = _archive_report(project_root, timestamp)
            if archived_report:
                row["report_path"] = str(archived_report)
                print(f"Archived diagnosis report: {archived_report}", flush=True)

            if args.llm:
                if os.environ.get("ARK_API_KEY") and os.environ.get("ARK_MODEL"):
                    llm_result = _run_llm_diagnosis(
                        project_root,
                        args.config,
                        args.alert or f"Online Boutique {top_service} CPU anomaly",
                        env=os.environ.copy(),
                    )
                    llm_text = (llm_result.stdout or "") + ("\n" + llm_result.stderr if llm_result.stderr else "")
                    saved_path = _save_text(project_root, timestamp, llm_text)
                    row["llm_output_path"] = str(saved_path)
                    row["llm_executed"] = True
                    print(f"Saved LLM diagnosis summary: {saved_path}", flush=True)
                else:
                    print("LLM requested, but ARK_API_KEY or ARK_MODEL is not configured. Skipping LLM diagnosis.", flush=True)
                    row["llm_executed"] = False
        else:
            if over_threshold and in_cooldown:
                print("CPU anomaly is still present, but watcher is in cooldown. Skipping trigger.", flush=True)
            else:
                print("No realtime CPU anomaly detected.", flush=True)

        _append_history(history_file, row)

        if triggered and args.trigger_once:
            print("Trigger-once completed. Exiting watcher.", flush=True)
            break

        if args.max_rounds > 0 and rounds >= args.max_rounds:
            break

        time.sleep(max(args.interval, 1))

    print("AIOps Watch Agent finished.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
