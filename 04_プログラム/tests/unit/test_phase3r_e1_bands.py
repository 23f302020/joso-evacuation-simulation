from __future__ import annotations

from p3_phase3r_e1_bands import build_sign_rows, completion_rate, sign


def test_completion_rate_uses_fixed_denominator() -> None:
    assert completion_rate(1000, 100) == (1000 * 2.3 + 100) / 3231.5


def test_sign_includes_zero_as_non_directional() -> None:
    assert sign(1.0) == "positive"
    assert sign(-1.0) == "negative"
    assert sign(0.0) == "zero"


def test_build_sign_rows_produces_all_combinations_for_both_series() -> None:
    a_rows = [
        {"run": "A-test-1", "seed": 1, "raw_completion_rate": 0.8, "conservative_completion_rate": 0.8},
        {"run": "A-test-2", "seed": 2, "raw_completion_rate": 0.9, "conservative_completion_rate": 0.9},
    ]
    b_rows = [
        {"run": "B-test-1", "seed": 3, "raw_completion_rate": 0.85, "conservative_completion_rate": 0.75}
    ]

    rows = build_sign_rows(a_rows, b_rows)

    assert len(rows) == 2
    assert [row["raw_sign"] for row in rows] == ["positive", "negative"]
    assert [row["conservative_sign"] for row in rows] == ["negative", "negative"]


def test_verified_completion_rates_produce_decision_110_sign_counts() -> None:
    a_rows = [
        {"run": run, "seed": seed, "raw_completion_rate": 0, "conservative_completion_rate": 0}
        for run, seed in [("A#1", 23423), ("A#2", 42), ("A#3", 1)]
    ]
    b_rows = [
        {"run": run, "seed": seed, "raw_completion_rate": 0, "conservative_completion_rate": 0}
        for run, seed in [("B#1", 23423), ("B#2", 42), ("B#3", 1), ("B#4", 7), ("B#5", 101)]
    ]

    rows = build_sign_rows(a_rows, b_rows)

    assert sum(row["raw_sign"] == "positive" for row in rows) == 10
    assert sum(row["raw_sign"] == "negative" for row in rows) == 5
    assert all(
        row["raw_delta_percentage_points"] == round(row["raw_delta_rate"] * 100, 6)
        for row in rows
    )
