from __future__ import annotations

from math import isfinite
from pathlib import Path

from jdrt import load_joso_input_bundle
from jdrt.static_routing import StaticTravelTimeLowerBounds


def test_real_joso_network_has_finite_service_lower_bounds(program_dir: Path) -> None:
    bundle = load_joso_input_bundle(program_dir.parent)
    bounds = StaticTravelTimeLowerBounds(
        program_dir / "output" / "sumo" / "regions" / "08211" / "network" / "08211.net.xml",
        boarding_time_sec=300,
    )
    vehicle = bundle.vehicles[0]
    plans = bundle.request_plans[:20]
    values = [bounds(vehicle, plan) for plan in plans]

    assert all(isfinite(value) and value >= 300 for value in values)
    assert len(bounds._forward_cache) == 1
    assert len(bounds._to_shelter_cache) == len({plan.shelter_edge for plan in plans})
