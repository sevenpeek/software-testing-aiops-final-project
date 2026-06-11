"""Offline reader for USAD anomaly detection outputs."""

from __future__ import annotations

import csv
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


def _is_truthy_anomaly(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "1.0", "true", "yes", "y"}


def _read_csv_rows(path: Path, warnings: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        warnings.append(f"USAD anomaly score file not found: {path}")
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))
    except Exception as exc:  # pragma: no cover - defensive for malformed files
        warnings.append(f"Failed to read USAD anomaly score CSV {path}: {exc}")
        return []


def _parse_tp_fp_fn_tn(text: str) -> dict[str, int | None]:
    match = re.search(r"tp\s*/\s*fp\s*/\s*fn\s*/\s*tn\s*:\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", text, re.I)
    if not match:
        return {"tp": None, "fp": None, "fn": None, "tn": None}
    return {
        "tp": int(match.group(1)),
        "fp": int(match.group(2)),
        "fn": int(match.group(3)),
        "tn": int(match.group(4)),
    }


def _parse_summary(path: Path | None, warnings: list[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "precision": None,
        "recall": None,
        "f1": None,
        "tp": None,
        "fp": None,
        "fn": None,
        "tn": None,
        "top_reconstruction_error_metrics": [],
    }
    if path is None:
        warnings.append("USAD metrics_summary path is not configured.")
        return summary
    if not path.exists():
        warnings.append(f"USAD metrics summary file not found: {path}")
        return summary

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - defensive for filesystem errors
        warnings.append(f"Failed to read USAD metrics summary {path}: {exc}")
        return summary

    for key in ("precision", "recall", "f1"):
        match = re.search(rf"^{key}\s*:\s*([-+]?\d+(?:\.\d+)?)", text, re.I | re.M)
        if match:
            summary[key] = _safe_float(match.group(1))

    summary.update(_parse_tp_fp_fn_tn(text))

    lines = text.splitlines()
    in_top_section = False
    for line in lines:
        if re.search(r"top\s+reconstruction[-\s]?error\s+metrics", line, re.I):
            in_top_section = True
            continue
        if not in_top_section:
            continue
        stripped = line.strip()
        if not stripped:
            if summary["top_reconstruction_error_metrics"]:
                break
            continue
        metric_match = re.match(r"[-*]\s*(.+?)\s*:\s*([-+]?\d+(?:\.\d+)?)", stripped)
        if metric_match:
            summary["top_reconstruction_error_metrics"].append(
                {
                    "metric": metric_match.group(1).strip(),
                    "value": _safe_float(metric_match.group(2)),
                }
            )
        elif summary["top_reconstruction_error_metrics"]:
            break

    return summary


def analyze_usad(config: dict[str, Any], project_root: Path, dataset_name: str | None = None) -> dict[str, Any]:
    """Read USAD offline output files and return anomaly statistics."""

    warnings: list[str] = []
    usad_config = config.get("usad", {})
    selected_dataset = dataset_name or usad_config.get("default_dataset")
    datasets = usad_config.get("datasets", {})
    dataset_config = datasets.get(selected_dataset, {})

    if not selected_dataset:
        warnings.append("USAD default dataset is not configured.")
    if selected_dataset and not dataset_config:
        warnings.append(f"USAD dataset is not configured: {selected_dataset}")

    scores_path = _resolve_path(project_root, dataset_config.get("anomaly_scores"))
    summary_path = _resolve_path(project_root, dataset_config.get("metrics_summary"))

    rows = _read_csv_rows(scores_path, warnings) if scores_path else []
    if scores_path is None:
        warnings.append("USAD anomaly_scores path is not configured.")

    scores: list[float] = []
    thresholds: list[float] = []
    anomaly_windows = 0
    for row in rows:
        score = _safe_float(row.get("anomaly_score"))
        if score is not None:
            scores.append(score)
        threshold = _safe_float(row.get("threshold"))
        if threshold is not None:
            thresholds.append(threshold)
        if _is_truthy_anomaly(row.get("predicted_anomaly")):
            anomaly_windows += 1

    total_windows = len(rows)
    max_anomaly_score = max(scores) if scores else None
    mean_anomaly_score = sum(scores) / len(scores) if scores else None
    threshold_value = thresholds[-1] if thresholds else None

    has_anomaly = anomaly_windows > 0
    if not has_anomaly and max_anomaly_score is not None and threshold_value is not None:
        has_anomaly = max_anomaly_score > threshold_value

    summary = _parse_summary(summary_path, warnings)

    return {
        "dataset_name": selected_dataset,
        "paths": {
            "anomaly_scores": str(scores_path) if scores_path else None,
            "metrics_summary": str(summary_path) if summary_path else None,
        },
        "statistics": {
            "total_windows": total_windows,
            "anomaly_windows": anomaly_windows,
            "max_anomaly_score": max_anomaly_score,
            "mean_anomaly_score": mean_anomaly_score,
            "threshold": threshold_value,
            "has_anomaly": has_anomaly,
        },
        "summary": summary,
        "warnings": warnings,
    }
