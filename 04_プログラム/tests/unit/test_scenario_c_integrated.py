from __future__ import annotations

from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

from scenario_c_integrated import (
    build_run_summary,
    build_occupancy_ledger,
    build_closure_events,
    assign_unique_vehicle_routes,
    rebalance_vehicle_counts,
)


def test_rebalance_preserves_total_and_adds_missing_origin_vehicle() -> None:
    people = {
        "origin_a": [{"person_id": "a1"}],
        "origin_b": [{"person_id": f"b{i}"} for i in range(1, 7)],
    }
    original = Counter({"origin_a": 0, "origin_b": 3})

    adjusted, changes = rebalance_vehicle_counts("test", people, original)

    assert adjusted == Counter({"origin_a": 1, "origin_b": 2})
    assert sum(adjusted.values()) == sum(original.values())
    assert {row["origin_id"] for row in changes} == {"origin_a", "origin_b"}


def test_occupancy_ledger_is_exclusive_and_origin_local() -> None:
    mode_rows = [
        {
            "person_id": f"p{i}", "origin_id": "origin_a", "KEY_CODE": "1",
            "age_group": "elderly" if i == 1 else "non_elderly", "assigned_mode": "car",
        }
        for i in range(1, 6)
    ]
    car_rows = [
        {"vehicle_id": "car_1", "origin_id": "origin_a"},
        {"vehicle_id": "car_2", "origin_id": "origin_a"},
    ]

    rows = build_occupancy_ledger("test", mode_rows, car_rows)

    assert len(rows) == 5
    assert len({row["person_id"] for row in rows}) == 5
    assert Counter(row["vehicle_id"] for row in rows) == {"car_1": 3, "car_2": 2}
    assert {row["origin_id"] for row in rows} == {"origin_a"}


def test_run_summary_uses_person_denominator_not_vehicle_count() -> None:
    vehicle_rows = [
        {"occupancy_count": 3, "arrived": True, "final_status": "arrived"},
        {"occupancy_count": 2, "arrived": False, "final_status": "simulation_end_active"},
    ]
    person_rows = [
        {"arrived": True, "final_status": "arrived"},
        {"arrived": False, "final_status": "preflight_route_unreachable"},
    ]
    condition = {
        "condition_id": "test", "cohort": "T", "scenario_id": "test",
        "policy": "strict", "elderly_speed": 0.58,
    }

    summary, accounting = build_run_summary(vehicle_rows, person_rows, condition, 1)

    assert summary["completed_people"] == 4
    assert accounting["population"] == 7
    assert accounting["unfinished_people"] == 3


def test_assign_unique_vehicle_routes_preserves_vehicle_and_edges(tmp_path: Path) -> None:
    path = tmp_path / "cars.rou.xml"
    path.write_text(
        '<routes><vType id="car"/><vehicle id="v1" type="car" depart="0.00">'
        '<route edges="a b c"/></vehicle></routes>',
        encoding="utf-8",
    )

    assign_unique_vehicle_routes(path)

    root = ET.parse(path).getroot()
    route = root.find("route")
    vehicle = root.find("vehicle")
    assert route is not None and route.attrib == {"id": "route__v1", "edges": "a b c"}
    assert vehicle is not None
    assert vehicle.attrib["id"] == "v1"
    assert vehicle.attrib["depart"] == "0.00"
    assert vehicle.attrib["route"] == "route__v1"
    assert vehicle.find("route") is None


def test_synthetic_dry_restore_event_is_wade_smoke_only() -> None:
    strict_smoke = build_closure_events("strict", compressed=True)
    wade_smoke = build_closure_events("wade", compressed=True)
    wade_full = build_closure_events("wade", compressed=False)

    assert len(strict_smoke) == 8
    assert len(wade_full) == 8
    assert len(wade_smoke) == 9
    assert wade_smoke[-1]["time_id"] == "smoke_dry_restore"
    assert wade_smoke[-1]["sim_time_sec"] == 28
    assert wade_smoke[-1]["wade_shallow_edge_ids"] == []
