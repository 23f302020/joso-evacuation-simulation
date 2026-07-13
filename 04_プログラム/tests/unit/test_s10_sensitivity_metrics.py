from __future__ import annotations

from p3_s10_sensitivity_metrics import S10_RUNS, build_s10_metrics


def test_s10_seed_set_is_fixed() -> None:
    assert [(run, seed) for run, seed, _run_id in S10_RUNS] == [
        ("S10#1", 23423),
        ("S10#2", 42),
        ("S10#3", 1),
        ("S10#4", 7),
        ("S10#5", 101),
    ]


def test_s10_metrics_have_raw_and_conservative_parity() -> None:
    metrics, signs, summary = build_s10_metrics("08211")

    assert len(metrics) == 5
    assert len(signs) == 15
    assert summary["raw_sign_counts"] == {"positive": 10, "negative": 5, "zero": 0}
    assert summary["conservative_sign_counts"] == {
        "positive": 8,
        "negative": 7,
        "zero": 0,
    }
    s10_4 = next(row for row in metrics if row["run"] == "S10#4")
    assert s10_4["raw_completion_rate"] > 1.0
    assert s10_4["conservative_completion_rate"] <= 1.0
    assert all(
        "raw_sign" in row and "conservative_sign" in row for row in signs
    )
