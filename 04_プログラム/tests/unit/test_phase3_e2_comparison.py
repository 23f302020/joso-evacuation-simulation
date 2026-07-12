from __future__ import annotations

from p3_evaluate_equity import build_phase3_band_comparison_rows


def test_phase3_e2_uses_percent_and_percentage_point_units() -> None:
    band = {
        "raw_sign_counts": {"positive": 10, "negative": 5, "zero": 0},
        "conservative_sign_counts": {"positive": 8, "negative": 7, "zero": 0},
        "a_completion_rate_median": 0.95,
        "a_completion_rate_min": 0.75,
        "a_completion_rate_max": 0.97,
        "b_raw_completion_rate_median": 0.96,
        "b_raw_completion_rate_min": 0.92,
        "b_raw_completion_rate_max": 0.98,
        "b_conservative_completion_rate_median": 0.955,
        "b_conservative_completion_rate_min": 0.92,
        "b_conservative_completion_rate_max": 0.965,
        "raw_point_delta_percentage_points": 1.0,
        "raw_delta_min_percentage_points": -5.0,
        "raw_delta_max_percentage_points": 23.0,
        "conservative_point_delta_percentage_points": 0.5,
        "conservative_delta_min_percentage_points": -5.0,
        "conservative_delta_max_percentage_points": 21.5,
    }

    rows = build_phase3_band_comparison_rows(band)
    raw = next(row for row in rows if row["metric"] == "type34_completion_rate_raw")

    assert raw["unit"] == "percent"
    assert raw["scenario_a_point"] == 95.0
    assert raw["difference_b_minus_a_point"] == 1.0
    assert (raw["positive_combinations"], raw["negative_combinations"]) == (10, 5)
