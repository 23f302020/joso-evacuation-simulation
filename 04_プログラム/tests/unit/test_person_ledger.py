from __future__ import annotations

import csv
from pathlib import Path

import pytest

from p3_person_ledger import build_person_ledger, proportional_counts, validate_ledger


def _write(path: Path, fields: list[str], rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _fixtures(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    agents = _write(
        tmp_path / "agent_types.csv",
        [
            "origin_id",
            "KEY_CODE",
            "type3_no_car_non_elderly_pop",
            "type4_no_car_elderly_pop",
            "type3_mobility_limited_candidate_pop",
        ],
        [
            {
                "origin_id": "o1",
                "KEY_CODE": "k1",
                "type3_no_car_non_elderly_pop": 5,
                "type4_no_car_elderly_pop": 4,
                "type3_mobility_limited_candidate_pop": 1,
            }
        ],
    )
    assignments = _write(
        tmp_path / "assignments.csv",
        ["vehicle_id", "vehicle_kind", "origin_id"],
        [
            {"vehicle_id": "r1", "vehicle_kind": "rescue_car", "origin_id": "o1"},
            {"vehicle_id": "r2", "vehicle_kind": "rescue_car", "origin_id": "o1"},
            {"vehicle_id": "p1", "vehicle_kind": "private_car", "origin_id": "o1"},
        ],
    )
    vehicle_log = _write(
        tmp_path / "vehicle_log.csv",
        ["vehicle_id", "arrival", "arrived"],
        [
            {"vehicle_id": "r1", "arrival": 100, "arrived": True},
            {"vehicle_id": "r2", "arrival": "", "arrived": False},
            {"vehicle_id": "p1", "arrival": 80, "arrived": True},
        ],
    )
    passengers = _write(
        tmp_path / "passengers.csv",
        [
            "passenger_id",
            "origin_id",
            "person_type",
            "category",
            "bus_id",
            "trip_seq",
            "board_time_s",
            "arrival_time_s",
            "arrived",
        ],
        [
            {
                "passenger_id": "old1",
                "origin_id": "o1",
                "person_type": 4,
                "category": "type4",
                "bus_id": "b1",
                "trip_seq": 0,
                "board_time_s": 10,
                "arrival_time_s": 90,
                "arrived": True,
            }
        ],
    )
    return agents, assignments, vehicle_log, passengers


def test_largest_remainder_is_bounded_and_exact() -> None:
    assert proportional_counts([5, 4], 5) == [3, 2]
    assert proportional_counts([1, 1], 9) == [1, 1]


def test_person_ledger_preserves_population_and_excludes_bus_rescue_overlap(tmp_path: Path) -> None:
    agents, assignments, vehicle_log, passengers = _fixtures(tmp_path)
    rows, metrics, diagnostics = build_person_ledger(
        agent_types_path=agents,
        assignments_path=assignments,
        vehicle_log_path=vehicle_log,
        passenger_log_path=passengers,
        scenario="B",
        run="B#test",
        seed="42",
    )
    assert diagnostics == {
        "person_count": 9,
        "unique_person_count": 9,
        "type3_count": 5,
        "type4_count": 4,
        "bus_rescue_overlap_count": 0,
    }
    assert len({row["person_id"] for row in rows}) == 9
    assert sum(row["assigned_mode"] == "bus" for row in rows) == 1
    assert sum(row["assigned_mode"] == "rescue" for row in rows) == 5
    assert sum(row["assigned_mode"] == "unassigned" for row in rows) == 3
    assert all(not (row["assigned_bus_id"] and row["assigned_vehicle_id"]) for row in rows)
    combined = next(row for row in metrics if row["person_type"] == "type34")
    assert combined["denominator_people"] == 9
    assert combined["bus_assigned_people"] == 1
    assert combined["rescue_assigned_people"] == 5
    assert combined["unassigned_people"] == 3


def test_same_inputs_produce_same_person_assignments(tmp_path: Path) -> None:
    agents, assignments, vehicle_log, passengers = _fixtures(tmp_path)
    kwargs = dict(
        agent_types_path=agents,
        assignments_path=assignments,
        vehicle_log_path=vehicle_log,
        passenger_log_path=passengers,
        scenario="B",
        run="B#test",
        seed="42",
    )
    first, _, _ = build_person_ledger(**kwargs)
    second, _, _ = build_person_ledger(**kwargs)
    assert first == second


def test_bus_population_overflow_is_rejected(tmp_path: Path) -> None:
    agents, assignments, vehicle_log, passengers = _fixtures(tmp_path)
    with passengers.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for index in range(4):
            writer.writerow([f"overflow{index}", "o1", 4, "type4", "b1", 1, 20, "", False])
    with pytest.raises(ValueError, match="exceeds ledger population"):
        build_person_ledger(
            agent_types_path=agents,
            assignments_path=assignments,
            vehicle_log_path=vehicle_log,
            passenger_log_path=passengers,
            scenario="B",
            run="B#test",
            seed="42",
        )


def test_validator_rejects_duplicate_ids() -> None:
    row = {
        "person_id": "duplicate",
        "person_type": "type3",
        "assigned_mode": "unassigned",
        "assigned_vehicle_id": "",
        "assigned_bus_id": "",
        "arrived": False,
    }
    with pytest.raises(AssertionError, match="duplicate"):
        validate_ledger([row, dict(row)])

