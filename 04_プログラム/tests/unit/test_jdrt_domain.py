from __future__ import annotations

from math import inf

import pytest

from jdrt import DRTRequest, DRTVehicle, ForecastState


def test_forecast_state_contains_predictions_not_true_closures() -> None:
    forecast = ForecastState(
        current_time=100,
        predicted_closure_time_by_edge={"edge_a": 160, "edge_b": 140},
    )

    assert forecast.route_closure_margin(("edge_a", "edge_b")) == 40.0
    assert not hasattr(forecast, "true_closure_time_by_edge")


def test_route_without_predicted_closure_has_infinite_margin() -> None:
    forecast = ForecastState(current_time=100)

    assert forecast.route_closure_margin(("edge_a",)) == inf


def test_request_party_size_and_vehicle_remaining_capacity() -> None:
    request = DRTRequest(
        request_id="request_1",
        person_ids=("person_1", "person_2"),
        origin_edge="edge_a",
        request_time=10,
        vulnerability=0.5,
    )
    vehicle = DRTVehicle(
        vehicle_id="vehicle_1",
        capacity=4,
        current_edge="edge_b",
        onboard_person_ids=("person_3",),
    )

    assert request.party_size == 2
    assert vehicle.remaining_capacity == 3


def test_invalid_vulnerability_is_rejected() -> None:
    with pytest.raises(ValueError, match="vulnerability"):
        DRTRequest(
            request_id="request_1",
            person_ids=("person_1",),
            origin_edge="edge_a",
            request_time=10,
            vulnerability=1.1,
        )
