"""5-A スキーマ回帰テスト（P0）。

実出力CSVの列名・行数・不変条件を固定し、リファクタで出力構造が
黙って変わる事故を検知する。既存の「手動再実行＋Markdown記録」を自動化する
最速ROIのテスト（scripts側のコード変更は不要）。

実出力が無い環境では conftest.require_output により自動skip。
"""
from __future__ import annotations

import pandas as pd
import pytest

from conftest import require_output

# 実測済みスキーマ（tests/テスト設計書.md §5-A）
EXPECTED = {
    "sumo/evaluation/evacuation_summary.csv": {
        "columns": [
            "scenario_name", "scale_label", "vehicle_count", "departed_count",
            "arrived_count", "not_arrived_count", "arrival_rate",
            "reroute_failed_count", "long_stopped_count",
            "departure_blocked_by_closure_count", "stranded_main_count",
            "stranded_rate", "closure_event_count",
            "final_cumulative_closed_sumo_edge_count", "first_arrival_time_sec",
            "last_arrival_time_sec", "mean_travel_time_sec", "max_travel_time_sec",
            "evacuation_completion_time_sec", "evacuation_completion_status",
        ],
        "rows": 3,
    },
    "sumo/evaluation/evacuation_summary_by_municipality.csv": {"n_columns": 26, "rows": 41},
    "sumo/evaluation/phase1_phase2_comparison.csv": {"n_columns": 13},
    "sumo/evaluation/phase1_phase2_region_comparison.csv": {"n_columns": 14, "rows": 164},
    "sumo/derived/agent_types.csv": {"n_columns": 21, "rows": 40},
    "sumo/derived/time_mapping_sumo.csv": {
        "columns": [
            "time_id", "source_timestamp", "elapsed_sec_real",
            "sim_time_sec", "compression_ratio", "notes",
        ],
        "rows": 8,
    },
    "closure/closure_diagnostics.csv": {
        "columns": [
            "timestamp", "instant_edges", "new_edges", "lost_edges", "cumulative_edges",
        ],
        "rows": 8,
    },
}


@pytest.mark.regression
@pytest.mark.parametrize("rel_path", list(EXPECTED.keys()))
def test_output_schema(rel_path):
    spec = EXPECTED[rel_path]
    df = pd.read_csv(require_output(rel_path))

    if "columns" in spec:
        assert list(df.columns) == spec["columns"], f"{rel_path} の列名が変化"
    if "n_columns" in spec:
        assert df.shape[1] == spec["n_columns"], f"{rel_path} の列数が変化"
    if "rows" in spec:
        assert len(df) == spec["rows"], f"{rel_path} の行数が変化"


@pytest.mark.regression
def test_time_mapping_is_monotonic():
    """時間マッピングは単調増加で、シミュレーション総時間は6時間=21600秒。"""
    df = pd.read_csv(require_output("sumo/derived/time_mapping_sumo.csv"))
    sim = df["sim_time_sec"].astype(int)
    assert sim.is_monotonic_increasing, "sim_time_sec が単調増加でない"
    assert sim.max() == 21600, "総シミュレーション時間が6時間(21600秒)でない"


@pytest.mark.regression
def test_closure_is_cumulatively_monotonic():
    """道路閉鎖は累積で単調非減少（一度閉じた道路が復活しない）。"""
    df = pd.read_csv(require_output("closure/closure_diagnostics.csv"))
    cum = df["cumulative_edges"].astype(int)
    assert cum.is_monotonic_increasing, "cumulative_edges が単調非減少でない"
