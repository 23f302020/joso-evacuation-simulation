from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from scenario_c_routes import (
    allocate_households,
    build_car_assignments,
    build_person_ledger,
    write_person_routes,
)


def test_household_allocation_closes_citywide_targets() -> None:
    rows, counts = allocate_households(
        [
            {
                "origin_id": "origin_0001",
                "KEY_CODE": "5339777442",
                "total_pop": "21539",
            }
        ],
        0.15,
    )

    assert counts == {
        "population": 21539,
        "households": 9365,
        "non_owner_households": 1405,
        "car_households": 7960,
    }
    assert rows[0]["car_households"] == 7960


def test_car_assignment_uses_one_private_car_per_owner_household() -> None:
    rows = build_car_assignments(
        [
            {
                "origin_id": "origin_0001",
                "KEY_CODE": "5339777442",
                "car_households": 2,
            }
        ],
        {
            "origin_0001": {
                "from_sumo_edge_id": "from_edge",
                "shelter_id": "shelter_1",
                "shelter_name": "safe",
                "to_sumo_edge_id": "to_edge",
            }
        },
    )

    assert [row["vehicle_id"] for row in rows] == [
        "scen_c_origin_0001_0001",
        "scen_c_origin_0001_0002",
    ]
    assert {row["depart"] for row in rows} == {"0"}


def test_person_ledger_keeps_unreachable_people_and_emits_only_reachable(
    tmp_path: Path,
) -> None:
    mode_rows = [
        {
            "person_id": "p_general",
            "origin_id": "origin_0001",
            "KEY_CODE": "5339777442",
            "person_type": "type3",
            "age_group": "non_elderly",
            "assigned_mode": "walk",
        },
        {
            "person_id": "p_elderly",
            "origin_id": "origin_0001",
            "KEY_CODE": "5339777442",
            "person_type": "type4",
            "age_group": "elderly",
            "assigned_mode": "walk",
        },
        {
            "person_id": "p_unreachable",
            "origin_id": "origin_0002",
            "KEY_CODE": "5339777443",
            "person_type": "type3",
            "age_group": "non_elderly",
            "assigned_mode": "walk",
        },
    ]
    routes = [
        {
            "origin_id": "origin_0001",
            "origin_edge_id": "edge_a",
            "shelter_id": "shelter_1",
            "shelter_edge_id": "edge_c",
            "total_walk_distance_m": "580.000",
            "route_status": "reachable",
            "route_edges": "edge_a edge_b edge_c",
        },
        {
            "origin_id": "origin_0002",
            "origin_edge_id": "edge_x",
            "shelter_id": "",
            "shelter_edge_id": "",
            "total_walk_distance_m": "",
            "route_status": "route_unreachable",
            "route_edges": "",
        },
    ]

    ledger = build_person_ledger(mode_rows, routes)
    assert len(ledger) == 3
    assert sum(row["person_xml_emitted"] == "true" for row in ledger) == 2
    assert ledger[1]["walk_speed_mps"] == "0.58"
    assert ledger[2]["not_emitted_reason"] == "route_unreachable"

    output = tmp_path / "persons.rou.xml"
    write_person_routes(output, ledger)
    root = ET.parse(output).getroot()
    types = {row.attrib["id"]: row.attrib for row in root.findall("vType")}
    assert types["walk_general"]["desiredMaxSpeed"] == "1.00"
    assert types["walk_elderly"]["desiredMaxSpeed"] == "0.58"
    people = root.findall("person")
    assert len(people) == 2
    assert people[0].find("walk").attrib["edges"] == "edge_a edge_b edge_c"
