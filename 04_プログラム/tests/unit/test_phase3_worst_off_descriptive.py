from __future__ import annotations

from pathlib import Path

import pandas as pd

from p3_evaluate_equity import build_replicate_descriptive_table


def _write_vehicle_log(path: Path, arrived: list[bool], durations: list[int]) -> None:
    pd.DataFrame(
        {
            "vehicle_id": [f"vehicle_{index}" for index in range(len(arrived))],
            "arrival": [duration + 10 if flag else "" for flag, duration in zip(arrived, durations)],
            "duration": durations,
            "arrived": arrived,
        }
    ).to_csv(path, index=False)


def test_replicate_descriptive_is_arrived_vehicle_only_without_ab_judgment(
    tmp_path: Path,
) -> None:
    rows = []
    for scenario, run_id in (("A", "run_a"), ("B", "run_b")):
        artifact_dir = tmp_path / run_id
        artifact_dir.mkdir()
        _write_vehicle_log(
            artifact_dir / f"scenario_{scenario.lower()}_vehicle_log.csv",
            [True, True, False],
            [10, 30, 999],
        )
        rows.append(
            {
                "scenario": scenario,
                "run": f"{scenario}#1",
                "seed": 1,
                "run_id": run_id,
                "artifact_dir": artifact_dir,
            }
        )

    replicate_csv = tmp_path / "replicates.csv"
    pd.DataFrame(rows).to_csv(replicate_csv, index=False)
    result = build_replicate_descriptive_table(replicate_csv)

    assert len(result) == 2
    assert set(result["unit_scope"]) == {"vehicle"}
    assert set(result["population_conditioning"]) == {"arrived_vehicles_only"}
    assert set(result["scenario_b_bus_passengers"]) == {"excluded"}
    assert set(result["analysis_role"]) == {"descriptive_diagnostic_only"}
    assert set(result["directional_claim"]) == {"prohibited"}
    assert set(result["arrival_rate"]) == {0.666667}
    assert set(result["mean_duration_sec"]) == {20.0}
    assert set(result["worst_off_count"]) == {1}
    assert set(result["worst_off_mean_duration_sec"]) == {30.0}
    forbidden = ("delta", "sign", "improvement", "difference")
    assert not any(term in column.lower() for column in result.columns for term in forbidden)
