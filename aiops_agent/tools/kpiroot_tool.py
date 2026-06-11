"""Offline reader for KPIRoot root-cause localization outputs."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


def _resolve_path(project_root: Path, raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return project_root / path


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _read_csv(path: Path | None, warnings: list[str], label: str) -> list[dict[str, str]]:
    if path is None:
        warnings.append(f"KPIRoot {label} path is not configured.")
        return []
    if not path.exists():
        warnings.append(f"KPIRoot {label} file not found: {path}")
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))
    except Exception as exc:  # pragma: no cover - defensive for malformed files
        warnings.append(f"Failed to read KPIRoot {label} CSV {path}: {exc}")
        return []


def _choose_column(fieldnames: list[str], exact_names: list[str], contains: list[str]) -> str | None:
    lowered = {name.lower(): name for name in fieldnames}
    for exact in exact_names:
        if exact.lower() in lowered:
            return lowered[exact.lower()]
    for name in fieldnames:
        lower = name.lower()
        if any(token in lower for token in contains):
            return name
    return None


def _metric_column(fieldnames: list[str]) -> str | None:
    return _choose_column(
        fieldnames,
        ["kpi", "metric", "candidate", "root_cause", "root_cause_kpi", "candidate_kpi", "name"],
        ["root_cause", "candidate", "metric", "kpi"],
    )


def _service_column(fieldnames: list[str]) -> str | None:
    return _choose_column(
        fieldnames,
        ["service", "component", "pod", "deployment", "root_cause_service"],
        ["service", "component", "deployment", "pod"],
    )


def _score_column(fieldnames: list[str]) -> str | None:
    return _choose_column(
        fieldnames,
        ["score", "final_score", "combined_score", "kpiroot_score"],
        ["final_score", "combined_score", "score", "similarity", "causality"],
    )


def _rank_column(fieldnames: list[str]) -> str | None:
    return _choose_column(fieldnames, ["rank"], ["rank"])


def _parse_service_from_metric(metric: str | None) -> str | None:
    if not metric:
        return None
    text = str(metric).strip()
    if "__" in text:
        service = text.split("__", 1)[1].strip()
        return service or None
    for separator in ("/", ".", ":"):
        if separator in text:
            service = text.rsplit(separator, 1)[-1].strip()
            if service:
                return service
    match = re.search(r"(frontend|paymentservice|checkoutservice|productcatalogservice|cartservice|currencyservice|emailservice|recommendationservice|shippingservice|redis-cart|adservice)", text)
    if match:
        return match.group(1)
    return None


def _find_summary_row(rows: list[dict[str, str]], scenario: str | None, warnings: list[str]) -> dict[str, str] | None:
    if not rows:
        return None
    if not scenario:
        warnings.append("KPIRoot default scenario is not configured.")
        return rows[0]
    for row in rows:
        for key in ("scenario_id", "scenario", "case", "name"):
            if row.get(key) == scenario:
                return row
    warnings.append(f"KPIRoot scenario not found in summary.csv: {scenario}")
    return None


def _load_summary_json(path: Path, warnings: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        warnings.append(f"KPIRoot summary.json not found: {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - defensive for malformed files
        warnings.append(f"Failed to read KPIRoot summary.json {path}: {exc}")
        return None


def analyze_kpiroot(config: dict[str, Any], project_root: Path, scenario: str | None = None) -> dict[str, Any]:
    """Read KPIRoot offline output files and return top root-cause candidates."""

    warnings: list[str] = []
    kpiroot_config = config.get("kpiroot", {})
    selected_scenario = scenario or kpiroot_config.get("default_scenario")

    summary_csv = _resolve_path(project_root, kpiroot_config.get("summary_csv"))
    ablation_summary_csv = _resolve_path(project_root, kpiroot_config.get("ablation_summary_csv"))
    scenarios_dir = _resolve_path(project_root, kpiroot_config.get("scenarios_dir"))
    ranking_csv = scenarios_dir / selected_scenario / "ranking.csv" if scenarios_dir and selected_scenario else None
    summary_json_path = scenarios_dir / selected_scenario / "summary.json" if scenarios_dir and selected_scenario else None

    summary_rows = _read_csv(summary_csv, warnings, "summary")
    _ = _read_csv(ablation_summary_csv, warnings, "ablation summary") if ablation_summary_csv else []
    ranking_rows = _read_csv(ranking_csv, warnings, "ranking")
    summary_row = _find_summary_row(summary_rows, selected_scenario, warnings)
    summary_json = _load_summary_json(summary_json_path, warnings) if summary_json_path else None

    fieldnames = list(ranking_rows[0].keys()) if ranking_rows else []
    metric_col = _metric_column(fieldnames) if fieldnames else None
    service_col = _service_column(fieldnames) if fieldnames else None
    score_col = _score_column(fieldnames) if fieldnames else None
    rank_col = _rank_column(fieldnames) if fieldnames else None

    if ranking_rows and metric_col is None:
        warnings.append("Could not identify metric column in KPIRoot ranking.csv.")
    if ranking_rows and score_col is None:
        warnings.append("Could not identify score column in KPIRoot ranking.csv.")

    top_candidates: list[dict[str, Any]] = []
    for index, row in enumerate(ranking_rows[:5], start=1):
        metric = row.get(metric_col) if metric_col else None
        service = row.get(service_col) if service_col else None
        if not service:
            service = _parse_service_from_metric(metric)
        score = _safe_float(row.get(score_col)) if score_col else None
        rank_value = row.get(rank_col) if rank_col else None
        top_candidates.append(
            {
                "rank": int(_safe_float(rank_value) or index),
                "metric": metric,
                "service": service,
                "score": score,
            }
        )

    top = top_candidates[0] if top_candidates else {}

    return {
        "scenario": selected_scenario,
        "paths": {
            "summary_csv": str(summary_csv) if summary_csv else None,
            "ablation_summary_csv": str(ablation_summary_csv) if ablation_summary_csv else None,
            "ranking_csv": str(ranking_csv) if ranking_csv else None,
            "summary_json": str(summary_json_path) if summary_json_path else None,
        },
        "top_metric": top.get("metric"),
        "top_service": top.get("service"),
        "top_score": top.get("score"),
        "top_candidates": top_candidates,
        "summary_row": summary_row,
        "summary_json": summary_json,
        "warnings": warnings,
    }
