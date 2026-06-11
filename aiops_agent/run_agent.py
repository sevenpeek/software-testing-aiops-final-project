"""Run the offline AIOps Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.kpiroot_tool import analyze_kpiroot
from tools.kubernetes_tool import collect_kubernetes_evidence
from tools.prometheus_tool import collect_prometheus_metrics
from tools.recovery_tool import generate_recovery_plan
from tools.report_tool import generate_report
from tools.usad_tool import analyze_usad


def _load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline AIOps Agent for Online Boutique")
    parser.add_argument("--config", default="aiops_agent/config.json", help="Path to config.json")
    args = parser.parse_args()

    agent_dir = Path(__file__).resolve().parent
    project_root = agent_dir.parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = project_root / config_path

    print("AIOps Agent started.", flush=True)
    print(f"Config path: {config_path}", flush=True)
    print(f"Project root: {project_root}", flush=True)

    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr, flush=True)
        print("AIOps Agent finished.", flush=True)
        return 1

    try:
        config = _load_config(config_path)
    except Exception as exc:
        print(f"ERROR: failed to load config file {config_path}: {exc}", file=sys.stderr, flush=True)
        print(
            "If the file was generated on Windows, ensure it is saved as UTF-8 without BOM, or read it with utf-8-sig.",
            file=sys.stderr,
            flush=True,
        )
        print("AIOps Agent finished.", flush=True)
        return 1

    print(f"Mode: {config.get('mode')}", flush=True)
    print(f"USAD dataset: {config.get('usad', {}).get('default_dataset')}", flush=True)

    warnings: list[str] = []

    try:
        usad_result = analyze_usad(config, project_root)
    except Exception as exc:  # pragma: no cover - final safety net
        usad_result = {
            "dataset_name": None,
            "paths": {},
            "statistics": {
                "has_anomaly": False,
                "anomaly_windows": None,
                "max_anomaly_score": None,
                "threshold": None,
            },
            "summary": {},
            "warnings": [f"USAD analysis failed unexpectedly: {exc}"],
        }
    warnings.extend(usad_result.get("warnings", []))

    stats = usad_result.get("statistics", {})
    print(f"USAD has_anomaly: {stats.get('has_anomaly')}", flush=True)
    print(f"USAD anomaly_windows: {stats.get('anomaly_windows')}", flush=True)
    print(f"USAD max_anomaly_score: {stats.get('max_anomaly_score')}", flush=True)
    print(f"USAD threshold: {stats.get('threshold')}", flush=True)

    print(f"KPIRoot scenario: {config.get('kpiroot', {}).get('default_scenario')}", flush=True)
    try:
        kpiroot_result = analyze_kpiroot(config, project_root)
    except Exception as exc:  # pragma: no cover - final safety net
        kpiroot_result = {
            "scenario": None,
            "paths": {},
            "top_metric": None,
            "top_service": None,
            "top_score": None,
            "top_candidates": [],
            "summary_row": None,
            "summary_json": None,
            "warnings": [f"KPIRoot analysis failed unexpectedly: {exc}"],
        }
    warnings.extend(kpiroot_result.get("warnings", []))

    print(f"KPIRoot top_service: {kpiroot_result.get('top_service')}", flush=True)
    print(f"KPIRoot top_metric: {kpiroot_result.get('top_metric')}", flush=True)

    kubernetes_enabled = bool(config.get("kubernetes", {}).get("enabled", False))
    kubernetes_evidence = {
        "enabled": kubernetes_enabled,
        "namespace": config.get("system", {}).get("namespace") or "online-boutique",
        "service_name": kpiroot_result.get("top_service"),
        "kubectl_available": False,
        "pod_summary": "",
        "deployment_summary": "",
        "service_summary": "",
        "recent_events": "",
        "logs_tail": "",
        "health_status": "disabled" if not kubernetes_enabled else "unknown",
        "warnings": [],
    }
    if kubernetes_enabled and kpiroot_result.get("top_service"):
        kubernetes_evidence = collect_kubernetes_evidence(config, kpiroot_result.get("top_service"))
    elif kubernetes_enabled:
        kubernetes_evidence["warnings"].append("Kubernetes evidence enabled, but KPIRoot top_service is empty.")

    warnings.extend(kubernetes_evidence.get("warnings", []))
    print(f"Kubernetes evidence enabled: {kubernetes_enabled}", flush=True)
    print(f"Kubernetes health_status: {kubernetes_evidence.get('health_status')}", flush=True)
    if kubernetes_evidence.get("warnings"):
        print(f"Kubernetes warnings: {len(kubernetes_evidence.get('warnings', []))}", flush=True)

    prometheus_enabled = bool(config.get("prometheus", {}).get("enabled", False))
    prometheus_metrics = {
        "enabled": prometheus_enabled,
        "query_mode": config.get("prometheus", {}).get("query_mode", "kubectl_exec"),
        "monitoring_namespace": config.get("prometheus", {}).get("monitoring_namespace", "monitoring"),
        "prometheus_deployment": config.get("prometheus", {}).get("prometheus_deployment", "prometheus-deployment"),
        "service_name": kpiroot_result.get("top_service"),
        "prometheus_available": False,
        "metrics": {},
        "raw_queries": {},
        "summary": {
            "service_cpu_rate": None,
            "service_memory_working_set_mib": None,
            "interpretation": "Prometheus metrics collection did not run.",
        },
        "warnings": [],
    }
    if prometheus_enabled and kpiroot_result.get("top_service"):
        prometheus_metrics = collect_prometheus_metrics(config, kpiroot_result.get("top_service"))
    elif prometheus_enabled:
        prometheus_metrics["warnings"].append("Prometheus metrics enabled, but KPIRoot top_service is empty.")

    warnings.extend(prometheus_metrics.get("warnings", []))
    prometheus_summary = prometheus_metrics.get("summary", {})
    print(f"Prometheus metrics enabled: {prometheus_enabled}", flush=True)
    print(f"Prometheus available: {prometheus_metrics.get('prometheus_available')}", flush=True)
    print(f"Prometheus service_cpu_rate: {prometheus_summary.get('service_cpu_rate')}", flush=True)
    print(f"Prometheus service_memory_working_set_mib: {prometheus_summary.get('service_memory_working_set_mib')}", flush=True)
    if prometheus_metrics.get("warnings"):
        print(f"Prometheus warnings: {len(prometheus_metrics.get('warnings', []))}", flush=True)

    recovery_plan = generate_recovery_plan(
        config,
        usad_result,
        kpiroot_result,
        kubernetes_evidence,
        prometheus_metrics,
    )
    print(f"Recovery plan enabled: {recovery_plan.get('enabled')}", flush=True)
    print(f"Recovery decision: {recovery_plan.get('decision')}", flush=True)
    print(f"Recovery risk_level: {recovery_plan.get('risk_level')}", flush=True)
    print(f"Recovery dry_run: {recovery_plan.get('dry_run')}", flush=True)

    try:
        report_path = generate_report(
            config,
            project_root,
            usad_result,
            kpiroot_result,
            kubernetes_evidence,
            prometheus_metrics,
            recovery_plan,
        )
    except Exception as exc:
        print(f"ERROR: failed to generate report: {exc}", file=sys.stderr, flush=True)
        for warning in warnings:
            print(f"WARNING: {warning}", file=sys.stderr, flush=True)
        print("AIOps Agent finished.", flush=True)
        return 1

    print(f"Report generated: {report_path}", flush=True)

    if warnings:
        print("Warnings:", flush=True)
        for warning in warnings:
            print(f"- {warning}", flush=True)

    print("AIOps Agent finished.", flush=True)
    return 0


if __name__ == "__main__":
    main()
