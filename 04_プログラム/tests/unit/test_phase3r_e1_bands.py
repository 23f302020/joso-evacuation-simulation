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
        {"run": "A#1", "seed": 1, "raw_completion_rate": 0.8, "conservative_completion_rate": 0.8},
        {"run": "A#2", "seed": 2, "raw_completion_rate": 0.9, "conservative_completion_rate": 0.9},
    ]
    b_rows = [
        {"run": "B#1", "seed": 3, "raw_completion_rate": 0.85, "conservative_completion_rate": 0.75}
    ]

    rows = build_sign_rows(a_rows, b_rows)

    assert len(rows) == 2
    assert [row["raw_sign"] for row in rows] == ["positive", "negative"]
    assert [row["conservative_sign"] for row in rows] == ["negative", "negative"]
