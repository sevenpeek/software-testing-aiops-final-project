"""End-to-end realtime AIOps pipeline entrypoint.

Default mode is dry-run. External USAD/KPIRoot scripts only run when
``--execute-external`` is provided and ``--dry-run`` is not provided.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.external_pipeline_tool import (
    build_realtime_dataset,
    collect_latest_external_outputs,
    collect_realtime_metrics,
    copy_runtime_config_for_outputs,
    inspect_external_projects,
    run_kpiroot_realtime,
    run_usad_realtime,
)


def _load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _resolve_path(project_root: Path, path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = project_root / path
    return path


def _run_agent(project_root: Path, config_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "aiops_agent\\run_agent.py", "--config", str(config_path)],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )


def _run_llm(project_root: Path, config_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "aiops_agent\\veadk_agent.py",
            "--config",
            str(config_path),
            "--alert",
            "Realtime Online Boutique anomaly pipeline result",
            "--llm",
        ],
        cwd=str(project_root),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=360,
        check=False,
        env=env,
    )


def _parse_agent_decision(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in output.splitlines():
        if line.startswith("USAD has_anomaly:"):
            result["usad_has_anomaly"] = line.split(":", 1)[1].strip()
        elif line.startswith("USAD anomaly_windows:"):
            result["usad_anomaly_windows"] = line.split(":", 1)[1].strip()
        elif line.startswith("USAD max_anomaly_score:"):
            result["usad_max_anomaly_score"] = line.split(":", 1)[1].strip()
        elif line.startswith("KPIRoot top_service:"):
            result["kpiroot_top_service"] = line.split(":", 1)[1].strip()
        elif line.startswith("KPIRoot top_metric:"):
            result["kpiroot_top_metric"] = line.split(":", 1)[1].strip()
        elif line.startswith("Kubernetes health_status:"):
            result["kubernetes_health_status"] = line.split(":", 1)[1].strip()
        if line.startswith("Recovery decision:"):
            result["recovery_decision"] = line.split(":", 1)[1].strip()
        elif line.startswith("Recovery risk_level:"):
            result["risk_level"] = line.split(":", 1)[1].strip()
        elif line.startswith("Report generated:"):
            result["diagnosis_report"] = line.split(":", 1)[1].strip()
        elif line.startswith("Prometheus service_cpu_rate:"):
            result["prometheus_service_cpu_rate"] = line.split(":", 1)[1].strip()
    return result


def _is_weak_llm_output(text: str) -> bool:
    clean = (text or "").strip()
    if len(clean) < 220:
        return True
    weak_markers = (
        "Diagnosis report generated. Please review",
        "Please review aiops_agent/outputs/diagnosis_report.md",
        "请查看",
    )
    return any(marker.lower() in clean.lower() for marker in weak_markers) and "根因" not in clean and "建议" not in clean


def _conclusion_for(decision: str | None, service: str | None) -> str:
    target = service or "目标服务"
    if decision == "cpu_pressure_investigation":
        return f"当前 {target} 存在 CPU 压力异常，建议进入 CPU 压力排查。恢复动作保持 dry-run，未执行真实恢复命令。"
    if decision == "observe":
        return "当前 Prometheus 实时指标未显示明显资源压力，Agent 建议继续观察并保留本次诊断报告。"
    if decision == "manual_review":
        return "当前证据不足或模块输出不完整，建议人工复核 USAD、KPIRoot、Kubernetes 与 Prometheus 证据。"
    return f"当前 Agent 决策为 {decision or 'unknown'}，建议结合报告证据进行人工确认，恢复动作保持 dry-run。"


def _root_cause_text(context: dict[str, Any]) -> str:
    decision = context.get("recovery_decision")
    service = context.get("kpiroot_top_service") or context.get("kpiroot_alarm") or "paymentservice"
    metric = context.get("kpiroot_top_metric") or "N/A"
    cpu_rate = context.get("prometheus_service_cpu_rate") or "N/A"
    if decision == "cpu_pressure_investigation":
        return (
            f"Prometheus 当前 service_cpu_rate={cpu_rate}，超过 CPU 压力阈值或表现出明显升高；"
            f"USAD 检测到异常窗口，KPIRoot 将 Top1 根因定位到 `{metric}`，对应服务 `{service}`。"
            f"因此本次更符合 {service} CPU 压力故障。"
        )
    if decision == "observe":
        return "当前 Prometheus 实时 CPU/内存指标未显示明显压力，Kubernetes 运行证据未显示容器级故障，因此建议继续观察。"
    if decision == "manual_review":
        return "当前证据链不足以形成明确自动化结论，可能是实时算法输出缺失、指标窗口过短或故障类型与指标模板尚未完全对齐，需要人工复核。"
    return "Agent 已生成恢复建议，但仍需要结合 Pipeline report、USAD 输出、KPIRoot 排名和 Kubernetes 证据确认最终根因。"


def _build_llm_summary_markdown(context: dict[str, Any], raw_llm_output: str, llm_mode: str, llm_warning: str | None) -> str:
    service = context.get("kpiroot_top_service") or context.get("kpiroot_alarm") or "paymentservice"
    decision = context.get("recovery_decision")
    lines = [
        "# LLM 智能诊断总结",
        "",
        "## 1. 结论",
        "",
        _conclusion_for(str(decision) if decision else None, str(service)),
        "",
        "## 2. 关键证据",
        "",
        f"- data_source_mode: `{context.get('data_source_mode')}`",
        f"- execute_mode: `{context.get('execute_mode')}`",
        f"- Prometheus service_cpu_rate: `{context.get('prometheus_service_cpu_rate') or 'N/A'}`",
        f"- USAD has_anomaly: `{context.get('usad_has_anomaly') or 'N/A'}`",
        f"- USAD anomaly_windows: `{context.get('usad_anomaly_windows') or 'N/A'}`",
        f"- USAD max_anomaly_score: `{context.get('usad_max_anomaly_score') or 'N/A'}`",
        f"- KPIRoot top_service: `{context.get('kpiroot_top_service') or 'N/A'}`",
        f"- KPIRoot top_metric: `{context.get('kpiroot_top_metric') or 'N/A'}`",
        f"- Kubernetes health_status: `{context.get('kubernetes_health_status') or 'N/A'}`",
        f"- recovery_decision: `{context.get('recovery_decision') or 'N/A'}`",
        f"- risk_level: `{context.get('risk_level') or 'N/A'}`",
        "",
        "## 3. 根因分析",
        "",
        _root_cause_text(context),
        "",
        "## 4. 建议动作",
        "",
        "- 保留 USAD、KPIRoot、Pipeline 和 Agent 诊断报告，作为本次故障实验证据。",
        f"- 查看 `{service}` 近期变更、日志和 Kubernetes Event。",
        "- 检查流量峰值、资源 request/limit，以及是否存在资源竞争。",
        "- 必要时由人工确认后再考虑重启、扩容或调整资源配置。",
        "- 系统不会自动执行 `kubectl rollout restart`。",
        "",
        "## 5. 安全说明",
        "",
        "- external_projects 原始输出未被覆盖。",
        "- 本次优先使用 `aiops_agent/runtime_outputs` 中的实时结果；如输出缺失，Pipeline report 会标注 fallback。",
        "- 恢复动作保持 dry-run。",
        "- API Key 只通过环境变量或当前会话传入，不写入总结文件。",
        "",
        "## LLM 调用信息",
        "",
        f"- llm_mode: `{llm_mode}`",
        f"- llm_warning: `{llm_warning or 'N/A'}`",
    ]
    if raw_llm_output.strip():
        lines.extend(
            [
                "",
                "## 原始 LLM / Agent 输出摘录",
                "",
                "```text",
                raw_llm_output.strip()[-4000:],
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


def _current_runtime_outputs(
    config: dict[str, Any],
    usad_result: dict[str, Any],
    kpiroot_result: dict[str, Any],
    execute_usad: bool,
    execute_kpiroot: bool,
    dry_run_external: bool,
    warnings: list[str],
) -> tuple[dict[str, Any], str]:
    latest_outputs = collect_latest_external_outputs(config)
    warnings.extend(latest_outputs.get("warnings", []))
    if dry_run_external:
        warnings.append("dry-run mode: current realtime USAD/KPIRoot outputs were not generated; using existing outputs only for compatibility diagnosis.")
        return latest_outputs, "dry_run_plan_only"

    data_source_mode = "realtime_runtime"
    usad_dir = Path(str(usad_result.get("output_dir") or ""))
    kpiroot_dir = Path(str(kpiroot_result.get("output_dir") or ""))

    if execute_usad and usad_result.get("success") and (usad_dir / "anomaly_scores.csv").exists() and (usad_dir / "metrics_summary.txt").exists():
        latest_outputs["runtime_usad_output_dir"] = str(usad_dir)
        latest_outputs["usad_anomaly_scores"] = str(usad_dir / "anomaly_scores.csv")
        latest_outputs["usad_metrics_summary"] = str(usad_dir / "metrics_summary.txt")
    elif execute_usad:
        data_source_mode = "offline_fallback"
        warnings.append("Current realtime USAD output is missing or failed; runtime_config falls back to existing USAD output.")
    else:
        data_source_mode = "offline_fallback"
        warnings.append("USAD was not executed in this mode; runtime_config uses existing USAD output for compatibility.")

    if execute_kpiroot and kpiroot_result.get("success") and (kpiroot_dir / "summary.csv").exists():
        latest_outputs["runtime_kpiroot_output_dir"] = str(kpiroot_dir)
        latest_outputs["kpiroot_summary_csv"] = str(kpiroot_dir / "summary.csv")
        ablation_path = kpiroot_dir / "ablation_summary.csv"
        if ablation_path.exists():
            latest_outputs["kpiroot_ablation_summary_csv"] = str(ablation_path)
    elif execute_kpiroot:
        data_source_mode = "offline_fallback"
        warnings.append("Current realtime KPIRoot output is missing or failed; runtime_config falls back to existing KPIRoot output.")
    else:
        data_source_mode = "offline_fallback"
        warnings.append("KPIRoot was not executed in this mode; runtime_config uses existing KPIRoot output for compatibility.")

    return latest_outputs, data_source_mode


def _write_pipeline_report(path: Path, payload: dict[str, Any]) -> None:
    usad = payload.get("usad_result") or {}
    kpiroot = payload.get("kpiroot_result") or {}
    lines = [
        "# Realtime AIOps Pipeline Report",
        "",
        f"Generated at: {payload.get('generated_at')}",
        f"dry_run: {payload.get('dry_run')}",
        f"execute_mode: {payload.get('execute_mode')}",
        f"data_source_mode: {payload.get('data_source_mode')}",
        "",
        "## Realtime data collection",
        "",
        f"- duration_minutes: {payload.get('duration_minutes')}",
        f"- step_seconds: {payload.get('step_seconds')}",
        f"- prometheus_csv: `{payload.get('prometheus_csv')}`",
        f"- prometheus_meta: `{payload.get('prometheus_meta')}`",
        f"- usad_input_csv: `{payload.get('usad_input_csv')}`",
        f"- kpiroot_input_csv: `{payload.get('kpiroot_input_csv')}`",
        f"- kpiroot_phase2_dir: `{payload.get('kpiroot_phase2_dir')}`",
        "",
        "## USAD execution",
        "",
        f"- executed: {usad.get('executed')}",
        f"- success: {usad.get('success')}",
        f"- output_dir: `{usad.get('output_dir')}`",
        "- command:",
        "",
        "```text",
        " ".join(usad.get("command") or usad.get("planned_command") or []),
        "```",
        "",
        "- expected_outputs:",
    ]
    for item in usad.get("expected_outputs", []):
        lines.append(f"  - `{item}`")
    lines.extend(
        [
            "",
            "- stdout_tail:",
            "",
            "```text",
            usad.get("stdout_tail", ""),
            "```",
            "",
            "- stderr_tail:",
            "",
            "```text",
            usad.get("stderr_tail", ""),
            "```",
            "",
            "- warnings:",
        ]
    )
    for warning in usad.get("warnings", []):
        lines.append(f"  - {warning}")
    lines.extend(
        [
            "",
            "## KPIRoot execution",
            "",
            f"- executed: {kpiroot.get('executed')}",
            f"- success: {kpiroot.get('success')}",
            f"- output_dir: `{kpiroot.get('output_dir')}`",
            "- command:",
            "",
            "```text",
            " ".join(kpiroot.get("command") or kpiroot.get("planned_command") or []),
            "```",
            "",
            "- expected_outputs:",
        ]
    )
    for item in kpiroot.get("expected_outputs", []):
        lines.append(f"  - `{item}`")
    lines.extend(
        [
            "",
            "- stdout_tail:",
            "",
            "```text",
            kpiroot.get("stdout_tail", ""),
            "```",
            "",
            "- stderr_tail:",
            "",
            "```text",
            kpiroot.get("stderr_tail", ""),
            "```",
            "",
            "- warnings:",
        ]
    )
    for warning in kpiroot.get("warnings", []):
        lines.append(f"  - {warning}")
    lines.extend(
        [
            "",
            "## Agent diagnosis",
            "",
            f"- runtime_config: `{payload.get('runtime_config')}`",
            f"- diagnosis_report: `{payload.get('diagnosis_report')}`",
            f"- recovery_decision: {payload.get('recovery_decision')}",
            f"- risk_level: {payload.get('risk_level')}",
            f"- Prometheus service_cpu_rate: {payload.get('prometheus_service_cpu_rate')}",
            f"- data_source_mode: {payload.get('data_source_mode')}",
            "",
            "## LLM Summary",
            "",
            f"- llm_enabled: {payload.get('llm_enabled')}",
            f"- llm_executed: {payload.get('llm_executed')}",
            f"- llm_output_path: `{payload.get('llm_output_path')}`",
            f"- llm_mode: {payload.get('llm_mode')}",
            f"- llm_warning: {payload.get('llm_warning') or 'N/A'}",
            "",
            "## Safety notes",
            "",
            "- external_projects 原始输出未被覆盖。",
            "- 所有外部算法 runtime 输出均指向 aiops_agent/runtime_outputs。",
            "- 恢复动作保持 dry-run。",
            "- 没有执行 Kubernetes 修改命令。",
            "",
            "## Warnings And Limits",
            "",
        ]
    )
    for warning in payload.get("warnings", []):
        lines.append(f"- {warning}")
    lines.extend(
        [
            "",
            "## Raw command plans",
            "",
            "```json",
            json.dumps(payload.get("command_plans", {}), indent=2, ensure_ascii=False),
            "```",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8-sig")


def main() -> int:
    parser = argparse.ArgumentParser(description="Realtime end-to-end AIOps pipeline")
    parser.add_argument("--config", default="aiops_agent\\config.json")
    parser.add_argument("--duration-minutes", type=int, default=5)
    parser.add_argument("--step-seconds", type=int, default=15)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--execute-usad-only", action="store_true")
    parser.add_argument("--execute-kpiroot-only", action="store_true")
    parser.add_argument("--execute-external", action="store_true")
    parser.add_argument("--usad-epochs", type=int, default=1)
    parser.add_argument("--usad-window", type=int, default=5)
    parser.add_argument("--usad-train-ratio", type=float, default=0.7)
    parser.add_argument("--kpiroot-scenario", default="realtime-paymentservice-cpu")
    parser.add_argument("--kpiroot-alarm", default="paymentservice")
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--output-dir", default="aiops_agent\\runtime_outputs")
    args = parser.parse_args()

    agent_dir = Path(__file__).resolve().parent
    project_root = agent_dir.parent
    config_path = _resolve_path(project_root, args.config)
    output_dir = _resolve_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"realtime_pipeline_report_{timestamp}.md"

    print("Realtime AIOps Pipeline started.", flush=True)
    print(f"Config path: {config_path}", flush=True)
    print(f"Output dir: {output_dir}", flush=True)

    config = _load_config(config_path)
    execute_usad = bool((args.execute_usad_only or args.execute_external) and not args.dry_run)
    execute_kpiroot = bool((args.execute_kpiroot_only or args.execute_external) and not args.dry_run)
    external_execute = bool(execute_usad or execute_kpiroot)
    execute_mode = (
        "execute_usad_kpiroot"
        if args.execute_external
        else "execute_usad_only"
        if args.execute_usad_only
        else "execute_kpiroot_only"
        if args.execute_kpiroot_only
        else "dry_run"
    )
    warnings: list[str] = []

    inspection = inspect_external_projects(config)
    print("External projects inspected.", flush=True)

    collection = collect_realtime_metrics(config, args.duration_minutes, args.step_seconds)
    prometheus_csv = collection.get("csv_path")
    print(f"Prometheus CSV: {prometheus_csv}", flush=True)
    warnings.extend(collection.get("warnings", []))

    datasets = build_realtime_dataset(config, prometheus_csv, scenario_id=args.kpiroot_scenario, alarm_name=args.kpiroot_alarm)
    print(f"USAD input: {datasets.get('usad_input_csv')}", flush=True)
    print(f"KPIRoot input: {datasets.get('kpiroot_input_csv')}", flush=True)
    warnings.extend(datasets.get("warnings", []))

    dry_run_external = not external_execute
    if dry_run_external:
        print("External algorithm execution is dry-run. USAD/KPIRoot will not be executed.", flush=True)
    usad_result = run_usad_realtime(
        config,
        datasets.get("usad_input_csv"),
        execute=execute_usad,
        dry_run=not execute_usad,
        usad_epochs=args.usad_epochs,
        usad_window=args.usad_window,
        usad_train_ratio=args.usad_train_ratio,
    )
    kpiroot_result = run_kpiroot_realtime(
        config,
        datasets.get("kpiroot_matrix_csv"),
        usad_result=usad_result,
        execute=execute_kpiroot,
        dry_run=not execute_kpiroot,
        scenario=args.kpiroot_scenario,
        alarm=args.kpiroot_alarm,
    )
    warnings.extend(usad_result.get("warnings", []))
    warnings.extend(kpiroot_result.get("warnings", []))

    latest_outputs, data_source_mode = _current_runtime_outputs(
        config,
        usad_result,
        kpiroot_result,
        execute_usad,
        execute_kpiroot,
        dry_run_external,
        warnings,
    )
    runtime_config = copy_runtime_config_for_outputs(config, latest_outputs, output_dir)

    agent_result = _run_agent(project_root, runtime_config)
    agent_output = (agent_result.stdout or "") + ("\n" + agent_result.stderr if agent_result.stderr else "")
    print(agent_output.strip(), flush=True)
    decision = _parse_agent_decision(agent_output)

    llm_output_path = None
    llm_enabled = bool(args.llm)
    llm_executed = False
    llm_mode = "disabled"
    llm_warning = ""
    if args.llm:
        if os.environ.get("ARK_API_KEY") and os.environ.get("ARK_MODEL"):
            llm_result = _run_llm(project_root, runtime_config)
            llm_output = (llm_result.stdout or "") + ("\n" + llm_result.stderr if llm_result.stderr else "")
            llm_executed = True
            llm_mode = "volcengine_ark"
            if _is_weak_llm_output(llm_output):
                llm_mode = "volcengine_ark_with_fallback"
                llm_warning = "LLM output was too short or only pointed to diagnosis_report.md; generated local fallback summary."
            llm_context = {
                **decision,
                "data_source_mode": data_source_mode,
                "execute_mode": execute_mode,
                "kpiroot_alarm": args.kpiroot_alarm,
            }
            llm_output_path = output_dir / f"realtime_pipeline_llm_{timestamp}.md"
            llm_summary = _build_llm_summary_markdown(llm_context, llm_output, llm_mode, llm_warning)
            llm_output_path.write_text(llm_summary, encoding="utf-8-sig")
        else:
            llm_warning = "LLM requested but ARK_API_KEY or ARK_MODEL is missing; skipped LLM call."
            warnings.append(llm_warning)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run_external,
        "execute_external": external_execute,
        "execute_mode": execute_mode,
        "data_source_mode": data_source_mode,
        "duration_minutes": args.duration_minutes,
        "step_seconds": args.step_seconds,
        "prometheus_csv": prometheus_csv,
        "prometheus_meta": collection.get("meta_path"),
        "usad_input_csv": datasets.get("usad_input_csv"),
        "kpiroot_input_csv": datasets.get("kpiroot_input_csv"),
        "kpiroot_phase2_dir": datasets.get("kpiroot_phase2_dir"),
        "usad_result": usad_result,
        "kpiroot_result": kpiroot_result,
        "runtime_config": str(runtime_config),
        "diagnosis_report": decision.get("diagnosis_report"),
        "recovery_decision": decision.get("recovery_decision"),
        "risk_level": decision.get("risk_level"),
        "prometheus_service_cpu_rate": decision.get("prometheus_service_cpu_rate"),
        "llm_output_path": str(llm_output_path) if llm_output_path else None,
        "llm_enabled": llm_enabled,
        "llm_executed": llm_executed,
        "llm_mode": llm_mode,
        "llm_warning": llm_warning,
        "warnings": warnings,
        "inspection": inspection,
        "command_plans": {
            "usad": usad_result.get("command") or usad_result.get("planned_command"),
            "kpiroot": kpiroot_result.get("command") or kpiroot_result.get("planned_command"),
        },
    }
    _write_pipeline_report(report_path, payload)
    print(f"Data source mode: {data_source_mode}", flush=True)
    if llm_output_path:
        print(f"LLM output path: {llm_output_path}", flush=True)
        print(f"LLM mode: {llm_mode}", flush=True)
    print(f"Pipeline report generated: {report_path}", flush=True)
    print("Realtime AIOps Pipeline finished.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
