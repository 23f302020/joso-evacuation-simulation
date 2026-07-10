from __future__ import annotations

from p3_a_side_interpretation_diagnostics import (
    allocation_shadow_by_origin,
    not_arrived_by_origin_kind_closure,
    vehicle_kind_route_shelter,
)


def test_not_arrived_by_origin_kind_closure_groups_origin_kind_and_closure() -> None:
    rows = [
        {
            "origin_id": "o1",
            "KEY_CODE": "k1",
            "vehicle_kind": "rescue_car",
            "from_sumo_edge_id": "e1",
            "current_edge": "e2",
            "current_edge_closed": "True",
            "person_type": "type3",
            "arrived": "False",
        },
        {
            "origin_id": "o1",
            "KEY_CODE": "k1",
            "vehicle_kind": "rescue_car",
            "from_sumo_edge_id": "e1",
            "current_edge": "e3",
            "current_edge_closed": "False",
            "person_type": "type4",
            "arrived": "False",
        },
        {
            "origin_id": "o1",
            "KEY_CODE": "k1",
            "vehicle_kind": "rescue_car",
            "from_sumo_edge_id": "e1",
            "current_edge": "e2",
            "current_edge_closed": "False",
            "person_type": "type3",
            "arrived": "True",
        },
    ]

    result = not_arrived_by_origin_kind_closure(rows, {"e1": 100, "e2": 200, "e3": 300})

    assert result == [
        {
            "origin_id": "o1",
            "KEY_CODE": "k1",
            "vehicle_kind": "rescue_car",
            "origin_edge": "e1",
            "origin_edge_first_closure_sec": "100",
            "not_arrived_count": 2,
            "type3_count": 1,
            "type4_count": 1,
            "current_edge_closed_count": 1,
            "current_edge_min_first_closure_sec": 200,
        }
    ]


def test_vehicle_kind_route_shelter_summarizes_lengths_and_completion() -> None:
    rows = [
        {"vehicle_kind": "rescue_car", "shelter_id": "s1", "shelter_name": "A", "arrived": "True", "route_length_m": 100.0},
        {"vehicle_kind": "rescue_car", "shelter_id": "s1", "shelter_name": "A", "arrived": "False", "route_length_m": ""},
        {"vehicle_kind": "private_car", "shelter_id": "s2", "shelter_name": "B", "arrived": "True", "route_length_m": 50.0},
    ]

    result = vehicle_kind_route_shelter(rows)
    rescue = next(row for row in result if row["vehicle_kind"] == "rescue_car")

    assert rescue["vehicle_count"] == 2
    assert rescue["arrived_count"] == 1
    assert rescue["completion_rate"] == 0.5
    assert rescue["route_length_available_count"] == 1
    assert rescue["route_length_mean_m"] == 100.0


def test_allocation_shadow_by_origin_reports_type4_share_and_gap() -> None:
    rows = [
        {"origin_id": "o1", "KEY_CODE": "k1", "person_type": "type3", "arrived": "True"},
        {"origin_id": "o1", "KEY_CODE": "k1", "person_type": "type3", "arrived": "False"},
        {"origin_id": "o1", "KEY_CODE": "k1", "person_type": "type4", "arrived": "False"},
        {"origin_id": "o2", "KEY_CODE": "k2", "person_type": "type3", "arrived": "True"},
        {"origin_id": "o2", "KEY_CODE": "k2", "person_type": "type4", "arrived": "True"},
    ]
    agents = {
        "o1": {"type3_no_car_non_elderly_pop": "2", "type4_no_car_elderly_pop": "1"},
        "o2": {"type3_no_car_non_elderly_pop": "1", "type4_no_car_elderly_pop": "1"},
    }

    result, summary = allocation_shadow_by_origin(rows, agents)
    o1 = next(row for row in result if row["origin_id"] == "o1")

    assert o1["assigned_type4_share"] == 0.333333
    assert o1["population_type4_share"] == 0.333333
    assert o1["type4_minus_type3_completion_rate"] == -0.5
    assert summary["origin_count"] == 2
    assert summary["pearson_assigned_type4_share_vs_type34_completion_rate"] != ""
