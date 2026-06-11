"""Safe orchestration helpers for the realtime AIOps pipeline."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .realtime_dataset_adapter import build_realtime_datasets
from .realtime_prometheus_collector import collect_realtime_prometheus_metrics


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_path(project_root: Path, path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = project_root / path
    return path


def _runtime_outputs(config: dict[str, Any]) -> Path:
    project_root = _project_root()
    path = config.get("realtime_pipeline", {}).get("runtime_outputs_dir", "aiops_agent/runtime_outputs")
    output_dir = _resolve_path(project_root, path)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def inspect_external_projects(config: dict[str, Any] | None = None) -> dict[str, Any]:
    project_root = _project_root()
    usad_root = project_root / "external_projects" / "usad_anomaly_detection"
    kpiroot_root = project_root / "external_projects" / "kpiroot_fault_diagnosis"
    usad_entry = usad_root / "src" / "run_usad.py"
    kpiroot_script = kpiroot_root / "scripts" / "run-phase4-kpiroot.ps1"
    kpiroot_cli = kpiroot_root / "src" / "kpiroot" / "cli.py"
    return {
        "usad": {
            "root": str(usad_root),
            "readme": str(usad_root / "README.md"),
            "entry": str(usad_entry),
            "supports_input_path": True,
            "supports_output_path": True,
            "is_train_and_infer_together": True,
            "existing_outputs": [
                str(usad_root / "outputs_online_boutique_real" / "anomaly_scores.csv"),
                str(usad_root / "outputs_online_boutique_real" / "metrics_summary.txt"),
                str(usad_root / "outputs_online_boutique_chaosmesh" / "anomaly_scores.csv"),
                str(usad_root / "outputs_online_boutique_chaosmesh" / "metrics_summary.txt"),
            ],
            "warnings": [] if usad_entry.exists() else ["USAD run_usad.py entry was not found."],
        },
        "kpiroot": {
            "root": str(kpiroot_root),
            "readme": str(kpiroot_root / "README.md"),
            "script_entry": str(kpiroot_script),
            "cli_entry": str(kpiroot_cli),
            "supports_phase2_dir": True,
            "supports_output_dir": True,
            "depends_on_usad_output": False,
            "existing_outputs": [
                str(kpiroot_root / "data" / "phase4" / "kpiroot" / "summary.csv"),
                str(kpiroot_root / "data" / "phase4" / "kpiroot" / "ablation_summary.csv"),
            ],
            "warnings": [] if kpiroot_cli.exists() else ["KPIRoot cli.py entry was not found."],
        },
        "safety": {
            "external_outputs_may_be_overwritten_by_default_scripts": True,
            "safe_strategy": "Use explicit output directories under aiops_agent/runtime_outputs and never call fixed-output PowerShell scripts unless paths are reviewed.",
        },
    }


def collect_realtime_metrics(
    config: dict[str, Any],
    duration_minutes: int,
    step_seconds: int,
) -> dict[str, Any]:
    runtime_data = config.get("realtime_pipeline", {}).get("runtime_data_dir", "aiops_agent/runtime_data")
    return collect_realtime_prometheus_metrics(
        config,
        namespace=config.get("system", {}).get("namespace", "online-boutique"),
        duration_minutes=duration_minutes,
        step_seconds=step_seconds,
        output_dir=runtime_data,
    )


def build_realtime_dataset(
    config: dict[str, Any],
    prometheus_csv: str | Path,
    scenario_id: str = "realtime-paymentservice-cpu",
    alarm_name: str = "paymentservice",
) -> dict[str, Any]:
    runtime_data = config.get("realtime_pipeline", {}).get("runtime_data_dir", "aiops_agent/runtime_data")
    return build_realtime_datasets(
        config,
        prometheus_csv,
        output_dir=runtime_data,
        scenario_id=scenario_id,
        alarm_name=alarm_name,
    )


def _tail_text(text: str, max_lines: int = 40) -> str:
    lines = (text or "").splitlines()
    return "\n".join(lines[-max_lines:])


def run_usad_realtime(
    config: dict[str, Any],
    usad_input_csv: str | Path,
    execute: bool = False,
    dry_run: bool = True,
    usad_epochs: int = 1,
    usad_window: int = 5,
    usad_train_ratio: float = 0.7,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    project_root = _project_root()
    usad_entry = project_root / "external_projects" / "usad_anomaly_detection" / "src" / "run_usad.py"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = _runtime_outputs(config) / f"usad_realtime_{timestamp}"
    command = [
        sys.executable,
        str(usad_entry),
        "--input",
        str(_resolve_path(project_root, usad_input_csv)),
        "--out",
        str(output_dir),
        "--epochs",
        str(usad_epochs),
        "--window",
        str(usad_window),
        "--train-ratio",
        str(usad_train_ratio),
        "--title",
        "Realtime USAD anomaly score on Online Boutique metrics",
    ]
    expected_outputs = [
        str(output_dir / "anomaly_scores.csv"),
        str(output_dir / "metrics_summary.txt"),
        str(output_dir / "anomaly_score.png"),
        str(output_dir / "reconstruction_error.png"),
    ]
    result = {
        "command": command,
        "planned_command": command,
        "output_dir": str(output_dir),
        "executed": False,
        "success": False,
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "warnings": [],
        "expected_outputs": expected_outputs,
    }
    if dry_run or not execute:
        result["warnings"].append("USAD realtime execution skipped because dry_run=True or execute=False.")
        return result
    if not usad_entry.exists():
        result["warnings"].append("USAD entry script not found.")
        return result
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            command,
            cwd=str(project_root),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except Exception as exc:
        result["executed"] = True
        result["warnings"].append(f"USAD command failed to execute: {exc}")
        return result
    result.update(
        {
            "executed": True,
            "success": completed.returncode == 0 and all(Path(path).exists() for path in expected_outputs[:2]),
            "returncode": completed.returncode,
            "stdout_tail": _tail_text(completed.stdout),
            "stderr_tail": _tail_text(completed.stderr),
        }
    )
    if not result["success"]:
        result["warnings"].append("USAD execution finished but expected output files were not all found or return code was non-zero.")
    return result


def run_kpiroot_realtime(
    config: dict[str, Any],
    kpiroot_input_csv: str | Path,
    usad_result: dict[str, Any] | None = None,
    execute: bool = False,
    dry_run: bool = True,
    scenario: str = "realtime-paymentservice-cpu",
    alarm: str = "paymentservice",
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    project_root = _project_root()
    kpiroot_root = project_root / "external_projects" / "kpiroot_fault_diagnosis"
    phase2_dir = Path(kpiroot_input_csv).resolve().parents[2] if Path(kpiroot_input_csv).name == "kpi_matrix.csv" else _resolve_path(project_root, config.get("realtime_pipeline", {}).get("runtime_data_dir", "aiops_agent/runtime_data")) / "kpiroot_phase2"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = _runtime_outputs(config) / f"kpiroot_realtime_{timestamp}"
    report = output_dir / "PHASE4_KPIROOT_REALTIME.md"
    command = [
        sys.executable,
        "-m",
        "kpiroot.cli",
        "--phase2-dir",
        str(phase2_dir),
        "--output-dir",
        str(output_dir),
        "--report",
        str(report),
        "--scenario",
        scenario,
        "--alarm",
        alarm,
        "--paa-size",
        "16",
    ]
    expected_outputs = [
        str(output_dir / "summary.csv"),
        str(output_dir / "ablation_summary.csv"),
        str(output_dir / scenario / "ranking.csv"),
        str(output_dir / scenario / "summary.json"),
    ]
    result = {
        "command": command,
        "planned_command": command,
        "phase2_dir": str(phase2_dir),
        "output_dir": str(output_dir),
        "executed": False,
        "success": False,
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "warnings": [],
        "expected_outputs": expected_outputs,
    }
    if dry_run or not execute:
        result["warnings"].append("KPIRoot realtime execution skipped because dry_run=True or execute=False.")
        return result
    cli_path = kpiroot_root / "src" / "kpiroot" / "cli.py"
    if not cli_path.exists():
        result["warnings"].append("KPIRoot CLI not found.")
        return result
    if not (phase2_dir / scenario / "processed" / "kpi_matrix.csv").exists():
        result["warnings"].append(f"KPIRoot phase2 scenario matrix not found: {phase2_dir / scenario / 'processed' / 'kpi_matrix.csv'}")
        return result
    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(kpiroot_root / "src")
    try:
        completed = subprocess.run(
            command,
            cwd=str(kpiroot_root),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
            env=env,
        )
    except Exception as exc:
        result["executed"] = True
        result["warnings"].append(f"KPIRoot command failed to execute: {exc}")
        return result
    result.update(
        {
            "executed": True,
            "success": completed.returncode == 0 and all(Path(path).exists() for path in expected_outputs[:3]),
            "returncode": completed.returncode,
            "stdout_tail": _tail_text(completed.stdout),
            "stderr_tail": _tail_text(completed.stderr),
        }
    )
    if not result["success"]:
        result["warnings"].append("KPIRoot execution finished but expected output files were not all found or return code was non-zero.")
    return result


def collect_latest_external_outputs(config: dict[str, Any]) -> dict[str, Any]:
    project_root = _project_root()
    outputs_dir = _runtime_outputs(config)
    runtime_usad_dirs = sorted(outputs_dir.glob("usad_realtime_*"), key=lambda path: path.stat().st_mtime, reverse=True)
    runtime_kpiroot_dirs = sorted(outputs_dir.glob("kpiroot_realtime_*"), key=lambda path: path.stat().st_mtime, reverse=True)
    usad_dir = runtime_usad_dirs[0] if runtime_usad_dirs else None
    kpiroot_dir = runtime_kpiroot_dirs[0] if runtime_kpiroot_dirs else None
    fallback = inspect_external_projects(config)
    return {
        "runtime_usad_output_dir": str(usad_dir) if usad_dir else None,
        "runtime_kpiroot_output_dir": str(kpiroot_dir) if kpiroot_dir else None,
        "usad_anomaly_scores": str(usad_dir / "anomaly_scores.csv") if usad_dir and (usad_dir / "anomaly_scores.csv").exists() else fallback["usad"]["existing_outputs"][2],
        "usad_metrics_summary": str(usad_dir / "metrics_summary.txt") if usad_dir and (usad_dir / "metrics_summary.txt").exists() else fallback["usad"]["existing_outputs"][3],
        "kpiroot_summary_csv": str(kpiroot_dir / "summary.csv") if kpiroot_dir and (kpiroot_dir / "summary.csv").exists() else fallback["kpiroot"]["existing_outputs"][0],
        "kpiroot_ablation_summary_csv": str(kpiroot_dir / "ablation_summary.csv") if kpiroot_dir and (kpiroot_dir / "ablation_summary.csv").exists() else fallback["kpiroot"]["existing_outputs"][1],
        "warnings": [
            "If runtime output paths are None, aiops_agent continues with existing external project outputs.",
            "run_agent.py uses config.json paths unless a temporary runtime config is generated by realtime_pipeline_agent.",
        ],
    }


def copy_runtime_config_for_outputs(config: dict[str, Any], latest_outputs: dict[str, Any], output_dir: Path) -> Path:
    runtime_config = json.loads(json.dumps(config))
    runtime_config.setdefault("usad", {}).setdefault("datasets", {}).setdefault("realtime_runtime", {})
    runtime_config["usad"]["default_dataset"] = "realtime_runtime"
    runtime_config["usad"]["datasets"]["realtime_runtime"] = {
        "anomaly_scores": _to_project_relative(latest_outputs["usad_anomaly_scores"]),
        "metrics_summary": _to_project_relative(latest_outputs["usad_metrics_summary"]),
    }
    runtime_config.setdefault("kpiroot", {})
    runtime_config["kpiroot"]["summary_csv"] = _to_project_relative(latest_outputs["kpiroot_summary_csv"])
    runtime_config["kpiroot"]["ablation_summary_csv"] = _to_project_relative(latest_outputs["kpiroot_ablation_summary_csv"])
    if latest_outputs.get("runtime_kpiroot_output_dir"):
        runtime_config["kpiroot"]["scenarios_dir"] = _to_project_relative(latest_outputs["runtime_kpiroot_output_dir"])
        realtime_scenarios = [
            path.name
            for path in Path(latest_outputs["runtime_kpiroot_output_dir"]).iterdir()
            if path.is_dir() and (path / "ranking.csv").exists()
        ]
        if realtime_scenarios:
            runtime_config["kpiroot"]["default_scenario"] = realtime_scenarios[0]
    path = output_dir / "runtime_config.json"
    path.write_text(json.dumps(runtime_config, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _to_project_relative(path_value: str) -> str:
    project_root = _project_root()
    path = Path(path_value)
    try:
        return path.resolve().relative_to(project_root).as_posix()
    except Exception:
        return str(path_value).replace("\\", "/")
