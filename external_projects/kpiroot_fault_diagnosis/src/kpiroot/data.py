from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        value = yaml.safe_load(file)
    return value or {}


def load_scenario_frame(scenario_dir: Path) -> pd.DataFrame:
    matrix = scenario_dir / "processed" / "kpi_matrix.csv"
    if not matrix.exists():
        raise FileNotFoundError(f"Missing KPI matrix: {matrix}")
    frame = pd.read_csv(matrix)
    if "timestamp" not in frame.columns:
        raise ValueError(f"Missing timestamp column in {matrix}")
    return frame.sort_values("timestamp").reset_index(drop=True)


def parse_epoch(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(pd.Timestamp(value).timestamp())
    except Exception:
        return None


def extract_time_window(metadata: dict[str, Any]) -> tuple[float | None, float | None]:
    timing = metadata.get("timing") or metadata.get("timeline") or {}
    start_keys = [
        "fault_start",
        "chaos_creation_time",
        "fault_apply_time",
        "fault_apply_command_time",
        "fault_confirmed_time",
    ]
    end_keys = ["fault_end_estimated", "recovery_confirmed_time", "export_end"]
    start = next((parse_epoch(timing.get(key)) for key in start_keys if parse_epoch(timing.get(key)) is not None), None)
    end = next((parse_epoch(timing.get(key)) for key in end_keys if parse_epoch(timing.get(key)) is not None), None)
    return start, end


def extract_expected(metadata: dict[str, Any]) -> tuple[list[str], str | None]:
    fault = metadata.get("fault") or {}
    expected_kpis = fault.get("expected_root_cause_kpis") or []
    if isinstance(expected_kpis, str):
        expected_kpis = [expected_kpis]
    expected_service = (
        fault.get("expected_root_cause")
        or fault.get("target_service")
        or fault.get("target_app")
        or fault.get("target")
    )
    return list(expected_kpis), expected_service


def service_from_kpi(name: str) -> str | None:
    if "__" not in name:
        return None
    parts = name.split("__")
    if len(parts) < 2:
        return None
    service = parts[1]
    service = re.sub(r"-[0-9a-f]{6,}.*$", "", service)
    return service or None


def add_synthetic_alarms(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    cpu_columns = [column for column in frame.columns if column.startswith("cpu__")]
    memory_columns = [column for column in frame.columns if column.startswith("memory__")]
    running_columns = [column for column in frame.columns if column.startswith("running__")]
    restart_columns = [column for column in frame.columns if column.startswith("restart__")]
    if cpu_columns:
        frame["synthetic_total_cpu"] = frame[cpu_columns].sum(axis=1)
    if memory_columns:
        frame["synthetic_total_memory"] = frame[memory_columns].sum(axis=1)
    if running_columns:
        frame["synthetic_unavailable_pods"] = (1 - frame[running_columns]).clip(lower=0).sum(axis=1)
    if restart_columns:
        frame["synthetic_total_restarts"] = frame[restart_columns].sum(axis=1)
    return frame


def choose_alarm_column(frame: pd.DataFrame, scenario_id: str) -> str:
    scenario = scenario_id.lower()
    if "cpu" in scenario and "synthetic_total_cpu" in frame.columns:
        return "synthetic_total_cpu"
    if "pod-kill" in scenario:
        if "synthetic_total_memory" in frame.columns:
            return "synthetic_total_memory"
        if "alarm_frontend_probe_duration" in frame.columns:
            return "alarm_frontend_probe_duration"
    if "alarm_frontend_probe_duration" in frame.columns:
        return "alarm_frontend_probe_duration"
    if "synthetic_total_cpu" in frame.columns:
        return "synthetic_total_cpu"
    raise ValueError(f"Unable to choose an alarm column for {scenario_id}")


def candidate_columns(frame: pd.DataFrame, alarm_column: str) -> list[str]:
    excluded_prefixes = ("alarm_", "synthetic_")
    columns = []
    for column in frame.columns:
        if column == "timestamp" or column == alarm_column:
            continue
        if column.startswith(excluded_prefixes):
            continue
        columns.append(column)
    return columns


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
