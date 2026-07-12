from __future__ import annotations

from p3_s10_sensitivity_metrics import S10_RUNS


def test_s10_seed_set_is_fixed() -> None:
    assert [(run, seed) for run, seed, _run_id in S10_RUNS] == [
        ("S10#1", 23423),
        ("S10#2", 42),
        ("S10#3", 1),
        ("S10#4", 7),
        ("S10#5", 101),
    ]
