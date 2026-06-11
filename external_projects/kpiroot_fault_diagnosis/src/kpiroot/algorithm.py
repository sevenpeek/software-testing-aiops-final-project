from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import norm


EPS = 1e-9


@dataclass(frozen=True)
class KPIRootConfig:
    """Configuration for the KPIRoot reproduction.

    The paper uses w ~= sqrt(n) in large industrial datasets. Our course
    datasets contain tens of samples, so the default keeps more PAA bins to
    avoid making the Granger segment too short.
    """

    paa_size: int = 32
    alphabet_size: int = 9
    granger_lag: int = 2
    trend_lag: int = 2
    anomaly_gamma: float = 1.8
    lambda_weight: float = 0.9
    min_segment_bins: int = 8


def clean_series(values: Iterable[float]) -> np.ndarray:
    series = pd.Series(values, dtype="float64")
    series = series.replace([np.inf, -np.inf], np.nan)
    series = series.interpolate(limit_direction="both")
    series = series.ffill().bfill().fillna(0.0)
    return series.to_numpy(dtype=float)


def zscore(values: Iterable[float]) -> np.ndarray:
    arr = clean_series(values)
    std = float(np.std(arr))
    if std < EPS:
        return np.zeros_like(arr, dtype=float)
    return (arr - float(np.mean(arr))) / std


def minmax(values: Iterable[float]) -> np.ndarray:
    arr = clean_series(values)
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    if hi - lo < EPS:
        return np.zeros_like(arr, dtype=float)
    return (arr - lo) / (hi - lo)


def paa(values: Iterable[float], size: int) -> np.ndarray:
    arr = clean_series(values)
    if len(arr) == 0:
        return np.array([], dtype=float)
    size = max(1, min(int(size), len(arr)))
    return np.array([float(np.mean(chunk)) for chunk in np.array_split(arr, size)], dtype=float)


def paa_with_centers(values: Iterable[float], timestamps: Iterable[float], size: int) -> tuple[np.ndarray, np.ndarray]:
    arr = clean_series(values)
    ts = clean_series(timestamps)
    size = max(1, min(int(size), len(arr)))
    value_chunks = np.array_split(arr, size)
    ts_chunks = np.array_split(ts, size)
    paa_values = np.array([float(np.mean(chunk)) for chunk in value_chunks], dtype=float)
    centers = np.array([float(np.mean(chunk)) for chunk in ts_chunks], dtype=float)
    return paa_values, centers


def sax(values: Iterable[float], alphabet_size: int = 9) -> np.ndarray:
    arr = clean_series(values)
    alphabet_size = max(2, int(alphabet_size))
    breakpoints = norm.ppf(np.arange(1, alphabet_size) / alphabet_size)
    return np.digitize(arr, breakpoints)


def multiset_jaccard(left: Iterable[int], right: Iterable[int]) -> float:
    left_counter = Counter(left)
    right_counter = Counter(right)
    if not left_counter and not right_counter:
        return 0.0
    keys = set(left_counter) | set(right_counter)
    intersection = sum(min(left_counter[key], right_counter[key]) for key in keys)
    union = sum(max(left_counter[key], right_counter[key]) for key in keys)
    return float(intersection / union) if union else 0.0


def detect_anomaly_segment(
    alarm_paa: Iterable[float],
    trend_lag: int = 2,
    gamma: float = 1.8,
    min_segment_bins: int = 8,
) -> tuple[int, int]:
    """Detect an anomaly segment using the KPIRoot trend-ratio idea.

    The ratio is computed on a positive min-max scaled curve to make it robust
    for z-scored series with negative values.
    """

    signal = minmax(alarm_paa) + EPS
    n = len(signal)
    if n == 0:
        return 0, 0
    if n <= max(2 * trend_lag + 1, min_segment_bins):
        return 0, n

    best_index = int(np.argmax(np.diff(signal))) + 1
    for idx in range(trend_lag, n - trend_lag):
        previous_sum = float(np.sum(signal[idx - trend_lag : idx]))
        next_sum = float(np.sum(signal[idx : idx + trend_lag]))
        ratio = next_sum / max(previous_sum, EPS)
        if ratio > gamma:
            best_index = idx
            break

    start = max(0, best_index)
    threshold = signal[start]
    end = n
    for idx in range(start + 1, n):
        if signal[idx] < threshold and signal[idx - 1] >= threshold:
            end = idx + 1
            break

    if end - start < min_segment_bins:
        extra = min_segment_bins - (end - start)
        start = max(0, start - extra // 2)
        end = min(n, max(end + extra - extra // 2, start + min_segment_bins))
    return start, end


def segment_from_time_window(
    centers: np.ndarray,
    start_epoch: float | None,
    end_epoch: float | None,
    min_segment_bins: int,
) -> tuple[int, int] | None:
    if start_epoch is None or end_epoch is None or len(centers) == 0:
        return None
    mask = (centers >= start_epoch) & (centers <= end_epoch)
    indices = np.flatnonzero(mask)
    if len(indices) == 0:
        return None
    start = int(indices[0])
    end = int(indices[-1]) + 1
    if end - start < min_segment_bins:
        extra = min_segment_bins - (end - start)
        start = max(0, start - extra // 2)
        end = min(len(centers), max(end + extra - extra // 2, start + min_segment_bins))
    return start, end


def granger_f_stat(alarm_values: Iterable[float], candidate_values: Iterable[float], lag: int = 2) -> float:
    alarm = clean_series(alarm_values)
    candidate = clean_series(candidate_values)
    length = min(len(alarm), len(candidate))
    if length <= 2 * lag + 2:
        return 0.0
    alarm = alarm[:length]
    candidate = candidate[:length]

    y = alarm[lag:]
    restricted_cols = []
    full_cols = []
    for offset in range(1, lag + 1):
        restricted_cols.append(alarm[lag - offset : length - offset])
        full_cols.append(alarm[lag - offset : length - offset])
    for offset in range(1, lag + 1):
        full_cols.append(candidate[lag - offset : length - offset])

    restricted_x = np.column_stack([np.ones_like(y), *restricted_cols])
    full_x = np.column_stack([np.ones_like(y), *full_cols])

    restricted_coef, *_ = np.linalg.lstsq(restricted_x, y, rcond=None)
    full_coef, *_ = np.linalg.lstsq(full_x, y, rcond=None)
    restricted_residual = y - restricted_x @ restricted_coef
    full_residual = y - full_x @ full_coef
    rss_restricted = float(np.sum(restricted_residual**2))
    rss_full = float(np.sum(full_residual**2))
    denominator_df = len(y) - 2 * lag - 1
    if denominator_df <= 0 or rss_full <= EPS:
        return 0.0
    numerator = max(rss_restricted - rss_full, 0.0) / lag
    denominator = rss_full / denominator_df
    return float(max(numerator / max(denominator, EPS), 0.0))


def normalize_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    arr = np.asarray(scores, dtype=float)
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    if hi - lo < EPS:
        return [0.0 for _ in scores]
    return ((arr - lo) / (hi - lo)).tolist()


def run_kpiroot(
    frame: pd.DataFrame,
    alarm_column: str,
    candidate_columns: list[str],
    timestamps_column: str = "timestamp",
    start_epoch: float | None = None,
    end_epoch: float | None = None,
    config: KPIRootConfig | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    config = config or KPIRootConfig()
    if alarm_column not in frame.columns:
        raise KeyError(f"Alarm column not found: {alarm_column}")
    if timestamps_column not in frame.columns:
        raise KeyError(f"Timestamp column not found: {timestamps_column}")

    timestamps = clean_series(frame[timestamps_column])
    paa_size = min(config.paa_size, len(frame))
    alarm_z = zscore(frame[alarm_column])
    alarm_paa, centers = paa_with_centers(alarm_z, timestamps, paa_size)

    segment = segment_from_time_window(centers, start_epoch, end_epoch, config.min_segment_bins)
    segment_source = "metadata_window"
    if segment is None:
        segment = detect_anomaly_segment(
            alarm_paa,
            trend_lag=config.trend_lag,
            gamma=config.anomaly_gamma,
            min_segment_bins=config.min_segment_bins,
        )
        segment_source = "automatic_trend_detection"
    start_idx, end_idx = segment

    alarm_sax = sax(alarm_paa, config.alphabet_size)
    raw_rows = []
    for column in candidate_columns:
        if column not in frame.columns or column == alarm_column:
            continue
        values = clean_series(frame[column])
        if float(np.std(values)) < EPS:
            continue
        candidate_z = zscore(values)
        candidate_paa, _ = paa_with_centers(candidate_z, timestamps, paa_size)
        candidate_sax = sax(candidate_paa, config.alphabet_size)
        similarity = multiset_jaccard(alarm_sax[start_idx:end_idx], candidate_sax[start_idx:end_idx])
        causality_raw = granger_f_stat(
            alarm_paa[start_idx:end_idx],
            candidate_paa[start_idx:end_idx],
            lag=config.granger_lag,
        )
        raw_rows.append(
            {
                "kpi": column,
                "similarity": similarity,
                "causality_raw": causality_raw,
            }
        )

    causality_norm = normalize_scores([row["causality_raw"] for row in raw_rows])
    for row, normalized in zip(raw_rows, causality_norm):
        row["causality"] = normalized
        row["score"] = config.lambda_weight * row["similarity"] + (1.0 - config.lambda_weight) * normalized

    ranking = pd.DataFrame(raw_rows)
    if not ranking.empty:
        ranking = ranking.sort_values(["score", "similarity", "causality"], ascending=False).reset_index(drop=True)
        ranking.insert(0, "rank", np.arange(1, len(ranking) + 1))

    details = {
        "alarm_column": alarm_column,
        "paa_size": int(paa_size),
        "segment_start_index": int(start_idx),
        "segment_end_index": int(end_idx),
        "segment_source": segment_source,
        "segment_start_epoch": float(centers[start_idx]) if len(centers) and start_idx < len(centers) else None,
        "segment_end_epoch": float(centers[end_idx - 1]) if len(centers) and end_idx > 0 else None,
        "candidate_count": int(len(candidate_columns)),
        "ranked_count": int(len(ranking)),
        "config": config.__dict__,
    }
    return ranking, details
