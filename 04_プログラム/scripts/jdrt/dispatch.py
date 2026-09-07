"""Deterministic dispatch rules for the Joso City JDRT study."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Iterable

from .domain import (
    AssignmentCandidate,
    ForecastState,
    NetworkState,
    RequestStatus,
    VehicleStatus,
)


def is_assignment_feasible(
    candidate: AssignmentCandidate,
    network_state: NetworkState,
    forecast_state: ForecastState | None = None,
    *,
    safety_margin_sec: float = 0.0,
) -> bool:
    """Return whether a candidate can be considered by a dispatcher."""

    if safety_margin_sec < 0:
        raise ValueError("safety_margin_sec must be non-negative")
    if candidate.request_status is not RequestStatus.WAITING:
        return False
    if candidate.vehicle_status is not VehicleStatus.IDLE:
        return False
    if candidate.party_size > candidate.remaining_capacity:
        return False
    if network_state.closed_edges.intersection(candidate.route_edges):
        return False
    if forecast_state is None:
        return True
    if forecast_state.current_time != network_state.current_time:
        raise ValueError("network and forecast current_time must match")
    closure_margin = forecast_state.route_closure_margin(candidate.route_edges)
    required_time = candidate.total_service_time_sec + safety_margin_sec
    return required_time < closure_margin


def _feasible_candidates(
    candidates: Iterable[AssignmentCandidate],
    network_state: NetworkState,
    forecast_state: ForecastState | None,
    safety_margin_sec: float,
) -> list[AssignmentCandidate]:
    return [
        candidate
        for candidate in candidates
        if is_assignment_feasible(
            candidate,
            network_state,
            forecast_state,
            safety_margin_sec=safety_margin_sec,
        )
    ]


def _normalize(value: float, maximum: float) -> float:
    return value / maximum if maximum > 0 else 0.0


@dataclass(frozen=True)
class NearestDispatcher:
    def select(
        self,
        candidates: Iterable[AssignmentCandidate],
        network_state: NetworkState,
    ) -> AssignmentCandidate | None:
        feasible = _feasible_candidates(candidates, network_state, None, 0.0)
        return min(
            feasible,
            key=lambda item: (item.pickup_time_sec, item.request_id, item.vehicle_id),
            default=None,
        )


@dataclass(frozen=True)
class DynamicTravelTimeDispatcher:
    def select(
        self,
        candidates: Iterable[AssignmentCandidate],
        network_state: NetworkState,
    ) -> AssignmentCandidate | None:
        feasible = _feasible_candidates(candidates, network_state, None, 0.0)
        return min(
            feasible,
            key=lambda item: (
                item.total_service_time_sec,
                item.pickup_time_sec,
                item.request_id,
                item.vehicle_id,
            ),
            default=None,
        )


@dataclass(frozen=True)
class WaitingVulnerabilityDispatcher:
    waiting_weight: float = 1.0
    vulnerability_weight: float = 1.0
    pickup_weight: float = 1.0

    def __post_init__(self) -> None:
        if min(self.waiting_weight, self.vulnerability_weight, self.pickup_weight) < 0:
            raise ValueError("dispatcher weights must be non-negative")

    def select(
        self,
        candidates: Iterable[AssignmentCandidate],
        network_state: NetworkState,
    ) -> AssignmentCandidate | None:
        feasible = _feasible_candidates(candidates, network_state, None, 0.0)
        if not feasible:
            return None
        max_wait = max(item.waiting_time_sec for item in feasible)
        max_pickup = max(item.pickup_time_sec for item in feasible)

        def score(item: AssignmentCandidate) -> float:
            return (
                self.waiting_weight * _normalize(item.waiting_time_sec, max_wait)
                + self.vulnerability_weight * item.vulnerability
                - self.pickup_weight * _normalize(item.pickup_time_sec, max_pickup)
            )

        return min(
            feasible,
            key=lambda item: (-score(item), item.request_id, item.vehicle_id),
        )


@dataclass(frozen=True)
class FloodRiskAwareDispatcher:
    waiting_weight: float = 1.0
    flood_weight: float = 1.0
    vulnerability_weight: float = 1.0
    pickup_weight: float = 1.0
    safety_margin_sec: float = 0.0

    def __post_init__(self) -> None:
        if min(
            self.waiting_weight,
            self.flood_weight,
            self.vulnerability_weight,
            self.pickup_weight,
            self.safety_margin_sec,
        ) < 0:
            raise ValueError("dispatcher weights and safety margin must be non-negative")

    def select(
        self,
        candidates: Iterable[AssignmentCandidate],
        network_state: NetworkState,
        forecast_state: ForecastState,
    ) -> AssignmentCandidate | None:
        feasible = _feasible_candidates(
            candidates,
            network_state,
            forecast_state,
            self.safety_margin_sec,
        )
        if not feasible:
            return None

        max_wait = max(item.waiting_time_sec for item in feasible)
        max_pickup = max(item.pickup_time_sec for item in feasible)
        urgency = {
            item: (
                0.0
                if forecast_state.route_closure_margin(item.route_edges) == inf
                else 1.0
                / max(forecast_state.route_closure_margin(item.route_edges), 1.0)
            )
            for item in feasible
        }
        max_urgency = max(urgency.values(), default=0.0)

        def score(item: AssignmentCandidate) -> float:
            return (
                self.waiting_weight * _normalize(item.waiting_time_sec, max_wait)
                + self.flood_weight * _normalize(urgency[item], max_urgency)
                + self.vulnerability_weight * item.vulnerability
                - self.pickup_weight * _normalize(item.pickup_time_sec, max_pickup)
            )

        return min(
            feasible,
            key=lambda item: (-score(item), item.request_id, item.vehicle_id),
        )
