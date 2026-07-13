from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from p3_phase3r_e1_bands import (
    assert_summary_matches_metrics,
    build_metrics,
    build_sign_rows,
    completion_rate,
    sign,
)


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


def test_build_metrics_matches_archive_ground_truth() -> None:
    metrics, rows, summary = build_metrics("08211")

    expected_arrivals = [
        1341,
        1066,
        1349,
        1273,
        1304,
        1298,
        1330,
        1317,
    ]
    assert [row["rescue_arrived_total"] for row in metrics] == expected_arrivals
    tripinfo_arrivals = []
    for row in metrics:
        prefix = "scenario_a" if row["scenario"] == "A" else "scenario_b"
        tripinfo = Path(row["artifact_dir"]) / f"{prefix}_tripinfo.xml"
        tripinfo_arrivals.append(
            sum(
                1
                for _event, element in ET.iterparse(tripinfo, events=("end",))
                if element.tag == "tripinfo"
                and str(element.attrib.get("id", "")).startswith("rescue_")
            )
        )
    assert tripinfo_arrivals == expected_arrivals
    assert summary["raw_sign_counts"] == {"positive": 13, "negative": 2, "zero": 0}
    assert summary["conservative_sign_counts"] == {
        "positive": 13,
        "negative": 2,
        "zero": 0,
    }
    assert all(
        abs(row["raw_delta_percentage_points"] - row["raw_delta_rate"] * 100) <= 1e-6
        for row in rows
    )


def test_summary_consistency_assert_halts_on_mismatch() -> None:
    metrics, _, summary = build_metrics("08211")
    summary["a_completion_rate_values"] = [0.0]

    try:
        assert_summary_matches_metrics(metrics, summary)
    except AssertionError as exc:
        assert "summary/replicate mismatch" in str(exc)
    else:
        raise AssertionError("self-consistency tripwire did not halt")
