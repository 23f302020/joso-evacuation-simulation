from __future__ import annotations

import csv
from pathlib import Path

from p3_e1_type_metrics import assign_vehicle_types, compute_e1_metrics


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_assign_vehicle_types_maps_private_and_rescue_by_origin(tmp_path: Path) -> None:
    assignments = _write_csv(
        tmp_path / "assignments.csv",
        [
            "vehicle_id",
            "vehicle_kind",
            "origin_id",
            "KEY_CODE",
            "passenger_equivalent",
        ],
        [
            {"vehicle_id": "p1", "vehicle_kind": "private_car", "origin_id": "o1", "KEY_CODE": "k1", "passenger_equivalent": "2.3"},
            {"vehicle_id": "p2", "vehicle_kind": "private_car", "origin_id": "o1", "KEY_CODE": "k1", "passenger_equivalent": "2.3"},
            {"vehicle_id": "p3", "vehicle_kind": "private_car", "origin_id": "o1", "KEY_CODE": "k1", "passenger_equivalent": "2.3"},
            {"vehicle_id": "r1", "vehicle_kind": "rescue_car", "origin_id": "o1", "KEY_CODE": "k1", "passenger_equivalent": "2.3"},
            {"vehicle_id": "r2", "vehicle_kind": "rescue_car", "origin_id": "o1", "KEY_CODE": "k1", "passenger_equivalent": "2.3"},
        ],
    )
    agents = _write_csv(
        tmp_path / "agent_types.csv",
        [
            "origin_id",
            "type1_car_non_elderly_pop",
            "type2_car_elderly_pop",
            "type3_no_car_non_elderly_pop",
            "type4_no_car_elderly_pop",
        ],
        [
            {
                "origin_id": "o1",
                "type1_car_non_elderly_pop": "2",
                "type2_car_elderly_pop": "1",
                "type3_no_car_non_elderly_pop": "1",
                "type4_no_car_elderly_pop": "1",
            }
        ],
    )

    mapped, diagnostics = assign_vehicle_types(assignments, agents)
    assert diagnostics["typed_vehicle_count"] == 5
    assert diagnostics["unmatched_origin_count"] == 0
    assert sorted(row["person_type"] for row in mapped.values()) == [
        "type1",
        "type1",
        "type2",
        "type3",
        "type4",
    ]


def test_compute_e1_metrics_reports_type34_completion_rate(tmp_path: Path) -> None:
    assignments = _write_csv(
        tmp_path / "assignments.csv",
        ["vehicle_id", "vehicle_kind", "origin_id", "KEY_CODE", "passenger_equivalent"],
        [
            {"vehicle_id": "p1", "vehicle_kind": "private_car", "origin_id": "o1", "KEY_CODE": "k1", "passenger_equivalent": "2.3"},
            {"vehicle_id": "r1", "vehicle_kind": "rescue_car", "origin_id": "o1", "KEY_CODE": "k1", "passenger_equivalent": "2.3"},
            {"vehicle_id": "r2", "vehicle_kind": "rescue_car", "origin_id": "o1", "KEY_CODE": "k1", "passenger_equivalent": "2.3"},
        ],
    )
    agents = _write_csv(
        tmp_path / "agent_types.csv",
        [
            "origin_id",
            "type1_car_non_elderly_pop",
            "type2_car_elderly_pop",
            "type3_no_car_non_elderly_pop",
            "type4_no_car_elderly_pop",
        ],
        [
            {
                "origin_id": "o1",
                "type1_car_non_elderly_pop": "1",
                "type2_car_elderly_pop": "0",
                "type3_no_car_non_elderly_pop": "1",
                "type4_no_car_elderly_pop": "1",
            }
        ],
    )
    vehicle_log = _write_csv(
        tmp_path / "vehicle_log.csv",
        [
            "vehicle_id",
            "arrived",
            "duration",
            "stranded_main",
            "long_stopped",
        ],
        [
            {"vehicle_id": "p1", "arrived": "True", "duration": "10", "stranded_main": "False", "long_stopped": "False"},
            {"vehicle_id": "r1", "arrived": "True", "duration": "20", "stranded_main": "False", "long_stopped": "False"},
            {"vehicle_id": "r2", "arrived": "False", "duration": "", "stranded_main": "True", "long_stopped": "True"},
        ],
    )

    result = compute_e1_metrics(
        vehicle_log_path=vehicle_log,
        assignments_path=assignments,
        agent_types_path=agents,
    )
    assert result["summary"]["vehicle_count"] == 3
    assert result["summary"]["typed_vehicle_count"] == 3
    assert result["summary"]["unmatched_vehicle_count"] == 0
    assert result["summary"]["type34_vehicle_count"] == 2
    assert result["summary"]["type34_arrived_count"] == 1
    assert result["summary"]["type34_completion_rate"] == 0.5
