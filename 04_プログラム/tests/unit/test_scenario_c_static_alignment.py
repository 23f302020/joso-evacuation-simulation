from __future__ import annotations

from scenario_c_static_alignment import route_walk_intermodal


def test_walk_router_distinguishes_strict_and_wade_policies() -> None:
    lengths = {
        "start_fwd-1.00": 1.0,
        "dry_fwd-1.00": 2.0,
        "shallow_fwd-1.00": 1.0,
        "shelter_fwd-1.00": 1.0,
        "shelter_arrival_connector": 0.0,
    }
    reverse = {
        "start_fwd-1.00": [],
        "dry_fwd-1.00": ["start_fwd-1.00"],
        "shallow_fwd-1.00": ["start_fwd-1.00"],
        "shelter_fwd-1.00": ["dry_fwd-1.00", "shallow_fwd-1.00"],
        "shelter_arrival_connector": ["shelter_fwd-1.00"],
    }
    base_edges = {
        "start_fwd-1.00": "start",
        "dry_fwd-1.00": "dry",
        "shallow_fwd-1.00": "shallow",
        "shelter_fwd-1.00": "shelter",
    }
    walk_od = {
        "origin_0001": {
            "origin_edge_id": "start",
            "shelter_edge_id": "shelter",
        }
    }
    times = [
        {
            "time_id": "t0",
            "strict_closed_edge_ids": ["shallow"],
            "wade_closed_edge_ids": [],
            "wade_shallow_edge_ids": ["shallow"],
        }
    ]

    strict = route_walk_intermodal(
        lengths, reverse, base_edges, walk_od, times, "strict"
    )
    wade = route_walk_intermodal(
        lengths, reverse, base_edges, walk_od, times, "wade"
    )

    assert strict[("t0", "origin_0001")] == ["start", "dry", "shelter"]
    assert wade[("t0", "origin_0001")] == ["start", "shallow", "shelter"]
