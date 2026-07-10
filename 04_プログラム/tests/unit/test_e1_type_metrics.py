from __future__ import annotations

import csv
from pathlib import Path

from p3_e1_type_metrics import assign_vehicle_types, compute_e1_metrics, load_bus_arrived_people


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
        type34_denominator_people=4.6,
        type34_reference_population=5.0,
    )
    assert result["summary"]["vehicle_count"] == 3
    assert result["summary"]["typed_vehicle_count"] == 3
    assert result["summary"]["unmatched_vehicle_count"] == 0
    assert result["summary"]["type34_vehicle_count"] == 2
    assert result["summary"]["type34_arrived_count"] == 1
    assert result["summary"]["type34_completion_rate"] == 0.5
    assert result["summary"]["type34_rescue_arrived_people"] == 2.3
    assert result["summary"]["type34_bus_arrived_people"] == 0.0
    assert result["summary"]["type34_fixed_denominator_people"] == 4.6
    assert result["summary"]["type34_reference_population_people"] == 5.0
    assert result["summary"]["type34_reference_gap_people"] == 0.4
    assert result["summary"]["type34_fixed_denominator_completion_rate"] == 0.5
    assert result["summary"]["type34_reference_population_completion_rate"] == 0.46
    type34_row = next(row for row in result["metric_rows"] if row["person_type"] == "type34")
    assert type34_row["arrived_people_with_bus"] == 2.3
    assert type34_row["fixed_denominator_completion_rate"] == 0.5


def test_compute_e1_metrics_adds_arrived_bus_people_to_type34_numerator(tmp_path: Path) -> None:
    assignments = _write_csv(
        tmp_path / "assignments.csv",
        ["vehicle_id", "vehicle_kind", "origin_id", "KEY_CODE", "passenger_equivalent"],
        [
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
                "type1_car_non_elderly_pop": "0",
                "type2_car_elderly_pop": "0",
                "type3_no_car_non_elderly_pop": "1",
                "type4_no_car_elderly_pop": "1",
            }
        ],
    )
    vehicle_log = _write_csv(
        tmp_path / "vehicle_log.csv",
        ["vehicle_id", "arrived", "duration", "stranded_main", "long_stopped"],
        [
            {"vehicle_id": "r1", "arrived": "True", "duration": "20", "stranded_main": "False", "long_stopped": "False"},
            {"vehicle_id": "r2", "arrived": "False", "duration": "", "stranded_main": "True", "long_stopped": "True"},
        ],
    )
    passenger_log = _write_csv(
        tmp_path / "passenger_log.csv",
        ["passenger_id", "person_type", "arrived"],
        [
            {"passenger_id": "b1", "person_type": "type3", "arrived": "True"},
            {"passenger_id": "b2", "person_type": "type4", "arrived": "1"},
            {"passenger_id": "b3", "person_type": "type4", "arrived": "False"},
        ],
    )

    result = compute_e1_metrics(
        vehicle_log_path=vehicle_log,
        assignments_path=assignments,
        agent_types_path=agents,
        bus_passenger_log_path=passenger_log,
        type34_denominator_people=4.6,
        type34_reference_population=5.0,
    )

    assert load_bus_arrived_people(passenger_log) == 2.0
    assert result["summary"]["type34_rescue_arrived_people"] == 2.3
    assert result["summary"]["type34_bus_arrived_people"] == 2.0
    assert result["summary"]["type34_arrived_people_with_bus"] == 4.3
    assert result["summary"]["type34_fixed_denominator_completion_rate"] == 0.934783
    assert result["summary"]["type34_reference_population_completion_rate"] == 0.86
