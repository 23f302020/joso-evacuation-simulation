"""Accounting and invariant checks for the JDRT foundation."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from .domain import DRTVehicle, Evacuee, EvacueeStatus, TransportMode


ACTIVE_STATUSES = {
    EvacueeStatus.NOT_READY,
    EvacueeStatus.WAITING,
    EvacueeStatus.ASSIGNED,
    EvacueeStatus.ONBOARD,
}


def validate_unique_person_modes(evacuees: Iterable[Evacuee]) -> None:
    seen: dict[str, TransportMode | None] = {}
    for evacuee in evacuees:
        if evacuee.person_id in seen:
            previous = seen[evacuee.person_id]
            raise ValueError(
                f"duplicate person_id {evacuee.person_id}: {previous} and "
                f"{evacuee.transport_mode}"
            )
        if evacuee.transport_mode is TransportMode.DRT and not evacuee.eligible_for_drt:
            raise ValueError(f"person {evacuee.person_id} is not eligible for DRT")
        seen[evacuee.person_id] = evacuee.transport_mode


def validate_population_accounting(
    evacuees: Iterable[Evacuee], expected_population: int
) -> dict[str, int]:
    if expected_population < 0:
        raise ValueError("expected_population must be non-negative")
    rows = list(evacuees)
    validate_unique_person_modes(rows)
    if len(rows) != expected_population:
        raise ValueError(
            f"population mismatch: expected {expected_population}, got {len(rows)}"
        )
    missing = [row.person_id for row in rows if row.transport_mode is None]
    if missing:
        raise ValueError(f"transport mode is missing for: {missing}")
    counts = Counter(row.transport_mode.value for row in rows if row.transport_mode)
    return dict(sorted(counts.items()))


def validate_final_state_conservation(
    evacuees: Iterable[Evacuee], expected_population: int
) -> dict[str, int]:
    rows = list(evacuees)
    validate_unique_person_modes(rows)
    if len(rows) != expected_population:
        raise ValueError(
            f"final-state population mismatch: expected {expected_population}, got {len(rows)}"
        )
    counts = Counter(row.status for row in rows)
    summary = {
        "evacuated": counts[EvacueeStatus.EVACUATED],
        "stranded": counts[EvacueeStatus.STRANDED],
        "cancelled": counts[EvacueeStatus.CANCELLED],
        "active": sum(counts[status] for status in ACTIVE_STATUSES),
    }
    if sum(summary.values()) != expected_population:
        raise ValueError(f"final-state conservation failed: {summary}")
    return summary


def validate_vehicle_capacity(vehicles: Iterable[DRTVehicle]) -> None:
    seen_vehicle_ids: set[str] = set()
    person_to_vehicle: dict[str, str] = {}
    for vehicle in vehicles:
        if vehicle.vehicle_id in seen_vehicle_ids:
            raise ValueError(f"duplicate vehicle_id {vehicle.vehicle_id}")
        seen_vehicle_ids.add(vehicle.vehicle_id)
        if len(vehicle.onboard_person_ids) > vehicle.capacity:
            raise ValueError(
                f"vehicle {vehicle.vehicle_id} exceeds capacity "
                f"{vehicle.capacity}: {len(vehicle.onboard_person_ids)}"
            )
        for person_id in vehicle.onboard_person_ids:
            if person_id in person_to_vehicle:
                raise ValueError(
                    f"person {person_id} is onboard multiple vehicles: "
                    f"{person_to_vehicle[person_id]} and {vehicle.vehicle_id}"
                )
            person_to_vehicle[person_id] = vehicle.vehicle_id
