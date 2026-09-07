from __future__ import annotations

import pytest

from jdrt import (
    DRTVehicle,
    Evacuee,
    EvacueeStatus,
    TransportMode,
    validate_final_state_conservation,
    validate_population_accounting,
    validate_unique_person_modes,
    validate_vehicle_capacity,
)


def evacuee(
    person_id: str,
    *,
    mode: TransportMode | None = TransportMode.DRT,
    status: EvacueeStatus = EvacueeStatus.WAITING,
    eligible: bool = True,
) -> Evacuee:
    return Evacuee(
        person_id=person_id,
        origin_id="origin_1",
        person_type=4,
        age_group="elderly",
        has_private_car=False,
        vulnerability_score=1.0,
        ready_time=0,
        eligible_for_drt=eligible,
        transport_mode=mode,
        status=status,
    )


def test_duplicate_person_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate person_id"):
        validate_unique_person_modes(
            [
                evacuee("person_1", mode=TransportMode.DRT),
                evacuee("person_1", mode=TransportMode.RESCUE_CAR),
            ]
        )


def test_ineligible_drt_assignment_is_rejected() -> None:
    with pytest.raises(ValueError, match="not eligible"):
        validate_unique_person_modes([evacuee("person_1", eligible=False)])


def test_population_accounting_returns_mode_counts() -> None:
    rows = [
        evacuee("person_1", mode=TransportMode.DRT),
        evacuee("person_2", mode=TransportMode.PRIVATE_CAR),
        evacuee("person_3", mode=TransportMode.PRIVATE_CAR),
    ]

    assert validate_population_accounting(rows, expected_population=3) == {
        "DRT": 1,
        "PRIVATE_CAR": 2,
    }


def test_missing_transport_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="transport mode is missing"):
        validate_population_accounting(
            [evacuee("person_1", mode=None)], expected_population=1
        )


def test_final_state_conservation_groups_active_states() -> None:
    rows = [
        evacuee("person_1", status=EvacueeStatus.EVACUATED),
        evacuee("person_2", status=EvacueeStatus.STRANDED),
        evacuee("person_3", status=EvacueeStatus.ONBOARD),
        evacuee("person_4", status=EvacueeStatus.CANCELLED),
    ]

    assert validate_final_state_conservation(rows, expected_population=4) == {
        "evacuated": 1,
        "stranded": 1,
        "cancelled": 1,
        "active": 1,
    }


def test_vehicle_capacity_and_cross_vehicle_duplicates_are_rejected() -> None:
    over_capacity = DRTVehicle(
        vehicle_id="vehicle_1",
        capacity=1,
        current_edge="edge_a",
        onboard_person_ids=("person_1", "person_2"),
    )
    with pytest.raises(ValueError, match="exceeds capacity"):
        validate_vehicle_capacity([over_capacity])

    first = DRTVehicle(
        vehicle_id="vehicle_1",
        capacity=2,
        current_edge="edge_a",
        onboard_person_ids=("person_1",),
    )
    second = DRTVehicle(
        vehicle_id="vehicle_2",
        capacity=2,
        current_edge="edge_b",
        onboard_person_ids=("person_1",),
    )
    with pytest.raises(ValueError, match="multiple vehicles"):
        validate_vehicle_capacity([first, second])
