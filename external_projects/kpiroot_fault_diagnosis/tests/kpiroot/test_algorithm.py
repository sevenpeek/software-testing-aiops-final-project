from pathlib import Path
import sys

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from kpiroot.algorithm import (  # noqa: E402
    KPIRootConfig,
    granger_f_stat,
    multiset_jaccard,
    paa,
    run_kpiroot,
    sax,
)


def test_paa_reduces_to_requested_size():
    values = np.arange(10)
    reduced = paa(values, 5)
    assert len(reduced) == 5
    assert reduced.tolist() == [0.5, 2.5, 4.5, 6.5, 8.5]


def test_sax_returns_symbol_indices():
    symbols = sax([-2, -1, 0, 1, 2], alphabet_size=5)
    assert len(symbols) == 5
    assert symbols.min() >= 0
    assert symbols.max() < 5


def test_multiset_jaccard_counts_repeated_symbols():
    assert multiset_jaccard([1, 1, 2], [1, 2, 2]) == 0.5


def test_granger_f_stat_detects_lagged_driver():
    rng = np.random.default_rng(7)
    driver = np.sin(np.linspace(0, 8, 80))
    alarm = np.roll(driver, 2) + rng.normal(0, 0.03, 80)
    unrelated = rng.normal(0, 1, 80)
    assert granger_f_stat(alarm, driver, lag=2) > granger_f_stat(alarm, unrelated, lag=2)


def test_run_kpiroot_ranks_obvious_root_cause():
    timestamps = np.arange(80) * 15
    root = np.zeros(80)
    root[30:50] = 1.0
    alarm = root + np.random.default_rng(1).normal(0, 0.01, 80)
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "alarm": alarm,
            "cpu__rootservice": root,
            "cpu__otherservice": np.random.default_rng(2).normal(0, 0.05, 80),
        }
    )
    ranking, details = run_kpiroot(
        frame,
        alarm_column="alarm",
        candidate_columns=["cpu__rootservice", "cpu__otherservice"],
        start_epoch=float(timestamps[30]),
        end_epoch=float(timestamps[50]),
        config=KPIRootConfig(paa_size=32),
    )
    assert ranking.iloc[0]["kpi"] == "cpu__rootservice"
    assert details["segment_source"] == "metadata_window"
