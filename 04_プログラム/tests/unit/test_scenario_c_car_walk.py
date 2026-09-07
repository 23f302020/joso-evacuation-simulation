from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scenario_c_car_walk import (
    allocate_bounded_proportional,
    build_elderly_population_map,
    build_foundation,
    build_mode_ledger,
    build_ownership_sensitivity_suite,
    build_scenario_c_agent_types,
    build_scenario_c_agent_types_for_rate,
    read_ownership_scenarios,
    select_private_vehicle_assignments,
)


def _write(path: Path, fields: list[str], rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _agent_types(tmp_path: Path, *, type1: int = 2) -> Path:
    return _write(
        tmp_path / "agent_types.csv",
        [
            "origin_id",
            "KEY_CODE",
            "total_pop",
            "elderly_pop",
            "type1_car_non_elderly_pop",
            "type2_car_elderly_pop",
            "type3_no_car_non_elderly_pop",
            "type4_no_car_elderly_pop",
        ],
        [
            {
                "origin_id": "origin_0001",
                "KEY_CODE": "k1",
                "total_pop": 5,
                "elderly_pop": 2,
                "type1_car_non_elderly_pop": type1,
                "type2_car_elderly_pop": 1,
                "type3_no_car_non_elderly_pop": 1,
                "type4_no_car_elderly_pop": 1,
            }
        ],
    )


def _assignments(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "scenario_a_vehicle_assignments.csv",
        ["vehicle_id", "vehicle_kind", "origin_id", "KEY_CODE", "depart"],
        [
            {
                "vehicle_id": "private_1",
                "vehicle_kind": "private_car",
                "origin_id": "origin_0001",
                "KEY_CODE": "k1",
                "depart": 0,
            },
            {
                "vehicle_id": "private_2",
                "vehicle_kind": "private_car",
                "origin_id": "origin_0001",
                "KEY_CODE": "k1",
                "depart": 0,
            },
            {
                "vehicle_id": "rescue_1",
                "vehicle_kind": "rescue_car",
                "origin_id": "origin_0001",
                "KEY_CODE": "k1",
                "depart": 0,
            },
        ],
    )


def _population_mesh(tmp_path: Path) -> Path:
    path = tmp_path / "tblT001178Q08.txt"
    fields = [
        "KEY_CODE",
        "HTKSYORI",
        "HTKSAKI",
        "GASSAN",
        "T001178001",
        "T001178043",
        "T001178046",
        "T001178049",
        "T001178052",
        "T001178055",
    ]
    rows = [
        {field: "" for field in fields},
        {
            "KEY_CODE": "a",
            "HTKSYORI": 1,
            "GASSAN": "b;c",
            "T001178001": 13,
            "T001178043": 9,
            "T001178046": 5,
            "T001178049": 9,
            "T001178052": 13,
            "T001178055": 61,
        },
        {
            "KEY_CODE": "b",
            "HTKSYORI": 2,
            "HTKSAKI": "a",
            "T001178001": 6,
            "T001178043": "*",
        },
        {
            "KEY_CODE": "c",
            "HTKSYORI": 2,
            "HTKSAKI": "a",
            "T001178001": 90,
            "T001178043": "*",
        },
        {
            "KEY_CODE": "d",
            "T001178001": 5,
            "T001178043": 1,
            "T001178046": 1,
        },
    ]
    with path.open("w", encoding="cp932", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_mode_ledger_assigns_owners_to_car_and_nonowners_to_walk(tmp_path: Path) -> None:
    rows, diagnostics = build_mode_ledger(_agent_types(tmp_path))

    assert len(rows) == 5
    assert diagnostics["person_count"] == diagnostics["declared_population"] == 5
    assert diagnostics["elderly_people"] == diagnostics["declared_elderly"] == 2
    assert diagnostics["car_people"] == 3
    assert diagnostics["walk_people"] == 2
    assert all(
        row["assigned_mode"] == ("car" if row["car_ownership"] == "owner" else "walk")
        for row in rows
    )


def test_private_vehicle_selection_excludes_rescue_cars(tmp_path: Path) -> None:
    rows = select_private_vehicle_assignments(_assignments(tmp_path))

    assert [row["vehicle_id"] for row in rows] == ["private_1", "private_2"]
    assert {row["vehicle_kind"] for row in rows} == {"private_car"}


def test_non_closing_type_population_fails_before_output(tmp_path: Path) -> None:
    agents = _agent_types(tmp_path, type1=3)
    assignments = _assignments(tmp_path)
    output_dir = tmp_path / "scenario_c" / "foundation"

    with pytest.raises(ValueError, match="does not match total_pop"):
        build_foundation(
            agent_types_path=agents,
            scenario_a_assignments_path=assignments,
            output_dir=output_dir,
        )

    assert not output_dir.exists()


def test_foundation_is_isolated_and_marks_itself_not_runnable(tmp_path: Path) -> None:
    agents = _agent_types(tmp_path)
    assignments = _assignments(tmp_path)
    source_before = assignments.read_bytes()
    output_dir = tmp_path / "scenario_c" / "foundation"

    manifest = build_foundation(
        agent_types_path=agents,
        scenario_a_assignments_path=assignments,
        output_dir=output_dir,
    )

    assert manifest["scenario"] == "C"
    assert manifest["status"] == "foundation_only_not_runnable"
    assert manifest["pedestrian_routes_implemented"] is False
    assert manifest["sumo_run_authorized"] is False
    assert manifest["diagnostics"]["private_vehicle_count"] == 2
    assert manifest["diagnostics"]["rescue_vehicle_count"] == 0
    assert manifest["diagnostics"]["bus_vehicle_count"] == 0
    assert (output_dir / "scenario_c_mode_ledger.csv").exists()
    assert (output_dir / "scenario_c_private_vehicle_assignments.csv").exists()
    assert (output_dir / "manifest.json").exists()
    assert assignments.read_bytes() == source_before


def test_output_boundary_rejects_non_scenario_c_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="scenario_c"):
        build_foundation(
            agent_types_path=_agent_types(tmp_path),
            scenario_a_assignments_path=_assignments(tmp_path),
            output_dir=tmp_path / "derived",
        )


def test_bounded_proportional_allocation_preserves_group_total() -> None:
    assert allocate_bounded_proportional([13, 6, 90], 97, [13, 6, 90]) == [12, 5, 80]


def test_confidentiality_group_is_distributed_before_selection(tmp_path: Path) -> None:
    elderly, diagnostics = build_elderly_population_map(_population_mesh(tmp_path))

    assert {elderly[key] for key in ("000000000a", "000000000b", "000000000c")} == {
        5,
        12,
        80,
    }
    assert sum(elderly[key] for key in ("000000000a", "000000000b", "000000000c")) == 97
    assert elderly["000000000d"] == 2
    assert diagnostics["group_count"] == 1


def test_scenario_c_agent_types_close_population_after_age_distribution(
    tmp_path: Path,
) -> None:
    population = _population_mesh(tmp_path)
    origins = _write(
        tmp_path / "origins.csv",
        ["origin_id", "KEY_CODE", "lon", "lat", "total_pop"],
        [
            {"origin_id": "o1", "KEY_CODE": "000000000a", "lon": 1, "lat": 2, "total_pop": 13},
            {"origin_id": "o2", "KEY_CODE": "000000000b", "lon": 1, "lat": 2, "total_pop": 6},
            {"origin_id": "o3", "KEY_CODE": "000000000c", "lon": 1, "lat": 2, "total_pop": 90},
        ],
    )
    ownership = _write(
        tmp_path / "ownership.csv",
        ["KEY_CODE", "non_car_rate"],
        [
            {"KEY_CODE": "000000000a", "non_car_rate": 0.15},
            {"KEY_CODE": "000000000b", "non_car_rate": 0.15},
            {"KEY_CODE": "000000000c", "non_car_rate": 0.15},
        ],
    )

    rows, diagnostics = build_scenario_c_agent_types(
        population_mesh_path=population,
        agent_origins_path=origins,
        ownership_source_path=ownership,
    )

    assert diagnostics["declared_population"] == diagnostics["type_population"] == 109
    assert diagnostics["declared_elderly"] == 97
    assert diagnostics["age_allocation"]["source_group_count"] == 1
    assert diagnostics["age_allocation"]["selected_group_count"] == 1
    assert [row["elderly_pop"] for row in rows] == [12, 5, 80]
    assert all(
        row["type1_car_non_elderly_pop"]
        + row["type2_car_elderly_pop"]
        + row["type3_no_car_non_elderly_pop"]
        + row["type4_no_car_elderly_pop"]
        == row["total_pop"]
        for row in rows
    )


def test_formal_rate_allocation_preserves_city_target_and_elderly_inner_total(
    tmp_path: Path,
) -> None:
    population = _population_mesh(tmp_path)
    origins = _write(
        tmp_path / "origins.csv",
        ["origin_id", "KEY_CODE", "lon", "lat", "total_pop"],
        [
            {"origin_id": "o1", "KEY_CODE": "000000000a", "total_pop": 13},
            {"origin_id": "o2", "KEY_CODE": "000000000b", "total_pop": 6},
            {"origin_id": "o3", "KEY_CODE": "000000000c", "total_pop": 90},
        ],
    )
    scenario = {
        "scenario_id": "non_car_15pct",
        "non_car_rate": 0.15,
        "role": "reference_assumption",
        "source_status": "formal_sensitivity_not_observed",
        "source_note": "test",
    }

    rows, diagnostics = build_scenario_c_agent_types_for_rate(
        population_mesh_path=population,
        agent_origins_path=origins,
        scenario=scenario,
    )

    assert diagnostics["declared_population"] == 109
    assert diagnostics["walk_people"] == diagnostics["target_walk_people"] == 16
    assert diagnostics["walk_elderly_people"] == diagnostics["target_walk_elderly"] == 15
    assert diagnostics["walk_non_elderly_people"] == 1
    assert sum(
        row["type1_car_non_elderly_pop"]
        + row["type2_car_elderly_pop"]
        + row["type3_no_car_non_elderly_pop"]
        + row["type4_no_car_elderly_pop"]
        for row in rows
    ) == 109


def test_ownership_sensitivity_suite_writes_separate_non_runnable_ledgers(
    tmp_path: Path,
) -> None:
    population = _population_mesh(tmp_path)
    origins = _write(
        tmp_path / "origins.csv",
        ["origin_id", "KEY_CODE", "lon", "lat", "total_pop"],
        [
            {"origin_id": "o1", "KEY_CODE": "000000000a", "total_pop": 13},
            {"origin_id": "o2", "KEY_CODE": "000000000b", "total_pop": 6},
            {"origin_id": "o3", "KEY_CODE": "000000000c", "total_pop": 90},
        ],
    )
    scenarios = _write(
        tmp_path / "ownership_scenarios.csv",
        ["scenario_id", "non_car_rate", "role", "source_status", "source_note"],
        [
            {
                "scenario_id": "non_car_10pct",
                "non_car_rate": 0.10,
                "role": "sensitivity_low",
                "source_status": "formal_sensitivity_not_observed",
                "source_note": "low",
            },
            {
                "scenario_id": "non_car_15pct",
                "non_car_rate": 0.15,
                "role": "reference_assumption",
                "source_status": "formal_sensitivity_not_observed",
                "source_note": "reference",
            },
            {
                "scenario_id": "non_car_20pct",
                "non_car_rate": 0.20,
                "role": "sensitivity_high",
                "source_status": "formal_sensitivity_not_observed",
                "source_note": "high",
            },
        ],
    )
    output_dir = tmp_path / "scenario_c" / "ownership_sensitivity"

    manifest = build_ownership_sensitivity_suite(
        population_mesh_path=population,
        agent_origins_path=origins,
        ownership_scenarios_path=scenarios,
        output_dir=output_dir,
    )

    assert manifest["scenario_count"] == 3
    assert manifest["sumo_run_authorized"] is False
    assert [row["walk_people"] for row in manifest["ownership_scenarios"]] == [11, 16, 22]
    for scenario_id in ("non_car_10pct", "non_car_15pct", "non_car_20pct"):
        scenario_dir = output_dir / scenario_id
        assert (scenario_dir / "scenario_c_agent_types.csv").exists()
        assert (scenario_dir / "scenario_c_mode_ledger.csv").exists()
        assert (scenario_dir / "manifest.json").exists()
        assert not (scenario_dir / "scenario_c_private_vehicle_assignments.csv").exists()


def test_ownership_scenarios_require_one_reference(tmp_path: Path) -> None:
    scenarios = _write(
        tmp_path / "ownership_scenarios.csv",
        ["scenario_id", "non_car_rate", "role", "source_status", "source_note"],
        [
            {
                "scenario_id": "non_car_10pct",
                "non_car_rate": 0.10,
                "role": "sensitivity_low",
                "source_status": "formal_sensitivity_not_observed",
                "source_note": "low",
            }
        ],
    )

    with pytest.raises(ValueError, match="exactly one reference_assumption"):
        read_ownership_scenarios(scenarios)
