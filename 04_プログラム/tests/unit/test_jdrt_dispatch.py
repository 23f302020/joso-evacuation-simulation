from __future__ import annotations

from dataclasses import replace

import pytest

from jdrt import (
    AssignmentCandidate,
    DynamicTravelTimeDispatcher,
    FloodRiskAwareDispatcher,
    ForecastState,
    NearestDispatcher,
    NetworkState,
    WaitingVulnerabilityDispatcher,
    is_assignment_feasible,
)


def candidate(
    request_id: str,
    *,
    pickup: float,
    shelter: float = 20.0,
    wait: float = 0.0,
    vulnerability: float = 0.0,
    pickup_edge: str = "pickup_edge",
    shelter_edge: str = "shelter_edge",
) -> AssignmentCandidate:
    return AssignmentCandidate(
        request_id=request_id,
        vehicle_id="vehicle_1",
        route_to_pickup=(pickup_edge,),
        route_to_shelter=(shelter_edge,),
        pickup_time_sec=pickup,
        shelter_travel_time_sec=shelter,
        waiting_time_sec=wait,
        vulnerability=vulnerability,
        remaining_capacity=4,
        party_size=1,
    )


def test_feasibility_gate_is_strict_at_closure_margin() -> None:
    item = candidate("request_1", pickup=20.0, shelter=20.0)
    network = NetworkState(current_time=100)
    equal_margin = ForecastState(
        current_time=100,
        predicted_closure_time_by_edge={"shelter_edge": 150},
    )
    larger_margin = ForecastState(
        current_time=100,
        predicted_closure_time_by_edge={"shelter_edge": 151},
    )

    assert not is_assignment_feasible(
        item, network, equal_margin, safety_margin_sec=10.0
    )
    assert is_assignment_feasible(
        item, network, larger_margin, safety_margin_sec=10.0
    )


def test_feasibility_rejects_closed_edge_and_capacity_violation() -> None:
    item = candidate("request_1", pickup=10.0)

    assert not is_assignment_feasible(
        item, NetworkState(current_time=0, closed_edges=frozenset({"pickup_edge"}))
    )
    assert not is_assignment_feasible(
        replace(item, remaining_capacity=0), NetworkState(current_time=0)
    )


def test_nearest_dispatch_is_deterministic_for_ties() -> None:
    dispatcher = NearestDispatcher()
    network = NetworkState(current_time=0)
    request_b = candidate("request_b", pickup=10.0)
    request_a = candidate("request_a", pickup=10.0)

    assert dispatcher.select([request_b, request_a], network) == request_a
    assert dispatcher.select([request_a, request_b], network) == request_a


def test_dynamic_travel_time_uses_complete_service_time() -> None:
    dispatcher = DynamicTravelTimeDispatcher()
    network = NetworkState(current_time=0)
    near_but_slow = candidate("near", pickup=5.0, shelter=100.0)
    farther_but_fast = candidate("fast", pickup=20.0, shelter=20.0)

    assert dispatcher.select([near_but_slow, farther_but_fast], network) == farther_but_fast


def test_waiting_vulnerability_can_prioritize_vulnerable_request() -> None:
    dispatcher = WaitingVulnerabilityDispatcher(
        waiting_weight=0.0, vulnerability_weight=2.0, pickup_weight=1.0
    )
    network = NetworkState(current_time=0)
    near = candidate("near", pickup=5.0, vulnerability=0.0)
    vulnerable = candidate("vulnerable", pickup=20.0, vulnerability=1.0)

    assert dispatcher.select([near, vulnerable], network) == vulnerable


def test_flood_dispatcher_uses_predictions_and_filters_infeasible_request() -> None:
    dispatcher = FloodRiskAwareDispatcher(
        waiting_weight=0.0,
        flood_weight=2.0,
        vulnerability_weight=0.0,
        pickup_weight=0.0,
        safety_margin_sec=5.0,
    )
    network = NetworkState(current_time=100)
    urgent = candidate(
        "urgent", pickup=10.0, shelter=10.0, shelter_edge="urgent_edge"
    )
    later = candidate(
        "later", pickup=10.0, shelter=10.0, shelter_edge="later_edge"
    )
    forecast = ForecastState(
        current_time=100,
        predicted_closure_time_by_edge={"urgent_edge": 140, "later_edge": 300},
    )

    assert dispatcher.select([later, urgent], network, forecast) == urgent

    infeasible_forecast = ForecastState(
        current_time=100,
        predicted_closure_time_by_edge={"urgent_edge": 125, "later_edge": 300},
    )
    assert dispatcher.select([urgent, later], network, infeasible_forecast) == later


def test_flood_dispatcher_rejects_mismatched_clock() -> None:
    dispatcher = FloodRiskAwareDispatcher()
    with pytest.raises(ValueError, match="current_time"):
        dispatcher.select(
            [candidate("request_1", pickup=10.0)],
            NetworkState(current_time=100),
            ForecastState(current_time=101),
        )
