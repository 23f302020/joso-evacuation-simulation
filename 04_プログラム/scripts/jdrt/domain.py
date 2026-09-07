"""Domain objects for the Joso City dynamic DRT study.

This module has no SUMO/TraCI dependency.  Dispatchers consume ``NetworkState``
and ``ForecastState`` so that traffic execution and research decisions remain
separate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import inf
from typing import Mapping


class TransportMode(str, Enum):
    PRIVATE_CAR = "PRIVATE_CAR"
    DRT = "DRT"
    RESCUE_CAR = "RESCUE_CAR"


class EvacueeStatus(str, Enum):
    NOT_READY = "NOT_READY"
    WAITING = "WAITING"
    ASSIGNED = "ASSIGNED"
    ONBOARD = "ONBOARD"
    EVACUATED = "EVACUATED"
    STRANDED = "STRANDED"
    CANCELLED = "CANCELLED"


class RequestStatus(str, Enum):
    WAITING = "WAITING"
    ASSIGNED = "ASSIGNED"
    ONBOARD = "ONBOARD"
    COMPLETED = "COMPLETED"
    STRANDED = "STRANDED"
    CANCELLED = "CANCELLED"


class VehicleStatus(str, Enum):
    IDLE = "IDLE"
    TO_PICKUP = "TO_PICKUP"
    BOARDING = "BOARDING"
    TO_SHELTER = "TO_SHELTER"
    ALIGHTING = "ALIGHTING"
    REPOSITIONING = "REPOSITIONING"
    STRANDED = "STRANDED"
    FINISHED = "FINISHED"


def _require_non_empty(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_non_negative(name: str, value: int | float) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


@dataclass
class Evacuee:
    person_id: str
    origin_id: str
    person_type: int
    age_group: str
    has_private_car: bool
    vulnerability_score: float
    ready_time: int
    eligible_for_drt: bool
    transport_mode: TransportMode | None = None
    status: EvacueeStatus = EvacueeStatus.NOT_READY
    request_time: int | None = None
    pickup_time: int | None = None
    arrival_time: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty("person_id", self.person_id)
        _require_non_empty("origin_id", self.origin_id)
        if self.person_type not in {1, 2, 3, 4}:
            raise ValueError("person_type must be one of 1, 2, 3, 4")
        if not 0.0 <= self.vulnerability_score <= 1.0:
            raise ValueError("vulnerability_score must be between 0 and 1")
        _require_non_negative("ready_time", self.ready_time)


@dataclass
class DRTRequest:
    request_id: str
    person_ids: tuple[str, ...]
    origin_edge: str
    request_time: int
    vulnerability: float
    latest_pickup_time: int | None = None
    isolation_time: int | None = None
    assigned_vehicle_id: str | None = None
    status: RequestStatus = RequestStatus.WAITING

    def __post_init__(self) -> None:
        _require_non_empty("request_id", self.request_id)
        _require_non_empty("origin_edge", self.origin_edge)
        if not self.person_ids:
            raise ValueError("person_ids must not be empty")
        if len(set(self.person_ids)) != len(self.person_ids):
            raise ValueError("person_ids must be unique within a request")
        _require_non_negative("request_time", self.request_time)
        if not 0.0 <= self.vulnerability <= 1.0:
            raise ValueError("vulnerability must be between 0 and 1")

    @property
    def party_size(self) -> int:
        return len(self.person_ids)


@dataclass
class DRTVehicle:
    vehicle_id: str
    capacity: int
    current_edge: str
    onboard_person_ids: tuple[str, ...] = ()
    status: VehicleStatus = VehicleStatus.IDLE

    def __post_init__(self) -> None:
        _require_non_empty("vehicle_id", self.vehicle_id)
        _require_non_empty("current_edge", self.current_edge)
        if self.capacity <= 0:
            raise ValueError("capacity must be positive")
        if len(set(self.onboard_person_ids)) != len(self.onboard_person_ids):
            raise ValueError("onboard_person_ids must be unique within a vehicle")

    @property
    def remaining_capacity(self) -> int:
        return self.capacity - len(self.onboard_person_ids)


@dataclass(frozen=True)
class NetworkState:
    current_time: int
    closed_edges: frozenset[str] = field(default_factory=frozenset)
    travel_time_by_edge: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_negative("current_time", self.current_time)
        invalid = {
            edge_id: value
            for edge_id, value in self.travel_time_by_edge.items()
            if value < 0
        }
        if invalid:
            raise ValueError(f"travel times must be non-negative: {invalid}")


@dataclass(frozen=True)
class ForecastState:
    """Dispatcher-visible predicted closure times only.

    True closure times deliberately do not exist on this type.
    """

    current_time: int
    predicted_closure_time_by_edge: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_negative("current_time", self.current_time)

    def route_closure_margin(self, route_edges: tuple[str, ...]) -> float:
        if not route_edges:
            raise ValueError("route_edges must not be empty")
        earliest = min(
            (
                self.predicted_closure_time_by_edge.get(edge_id, inf)
                for edge_id in route_edges
            ),
            default=inf,
        )
        return float(earliest - self.current_time) if earliest != inf else inf


@dataclass(frozen=True)
class AssignmentCandidate:
    request_id: str
    vehicle_id: str
    route_to_pickup: tuple[str, ...]
    route_to_shelter: tuple[str, ...]
    pickup_time_sec: float
    shelter_travel_time_sec: float
    waiting_time_sec: float
    vulnerability: float
    remaining_capacity: int
    party_size: int
    boarding_time_sec: float = 0.0
    request_status: RequestStatus = RequestStatus.WAITING
    vehicle_status: VehicleStatus = VehicleStatus.IDLE

    def __post_init__(self) -> None:
        _require_non_empty("request_id", self.request_id)
        _require_non_empty("vehicle_id", self.vehicle_id)
        if not self.route_to_pickup or not self.route_to_shelter:
            raise ValueError("candidate routes must not be empty")
        for name, value in (
            ("pickup_time_sec", self.pickup_time_sec),
            ("shelter_travel_time_sec", self.shelter_travel_time_sec),
            ("boarding_time_sec", self.boarding_time_sec),
            ("waiting_time_sec", self.waiting_time_sec),
        ):
            _require_non_negative(name, value)
        if not 0.0 <= self.vulnerability <= 1.0:
            raise ValueError("vulnerability must be between 0 and 1")
        if self.remaining_capacity < 0:
            raise ValueError("remaining_capacity must be non-negative")
        if self.party_size <= 0:
            raise ValueError("party_size must be positive")

    @property
    def route_edges(self) -> tuple[str, ...]:
        return self.route_to_pickup + self.route_to_shelter

    @property
    def total_service_time_sec(self) -> float:
        return (
            self.pickup_time_sec
            + self.boarding_time_sec
            + self.shelter_travel_time_sec
        )
