from __future__ import annotations

from pathlib import Path

from jdrt import RequestStatus, RouteEstimate, load_joso_input_bundle
from jdrt.smoke import build_smoke_bundle, resolve_sumo_binary, select_smoke_plans


def test_smoke_selection_and_bundle_are_isolated(program_dir: Path) -> None:
    source = load_joso_input_bundle(program_dir.parent)
    vehicle = next(item for item in source.vehicles if item.capacity == 8)

    def route_finder(
        from_edge: str, to_edge: str, vehicle_type: str
    ) -> RouteEstimate:
        assert vehicle_type == "bus_standard"
        return RouteEstimate((from_edge, to_edge), 10.0)

    plans = select_smoke_plans(source, vehicle, route_finder, request_count=10)
    smoke = build_smoke_bundle(source, vehicle, plans)

    assert len(plans) == len(smoke.request_plans) == 10
    assert len({plan.shelter_edge for plan in plans}) == 1
    assert len(smoke.evacuees) == sum(
        plan.request.party_size for plan in smoke.request_plans
    )
    assert len(smoke.vehicles) == 1
    assert smoke.private_vehicles == ()
    assert smoke.true_closures.closure_time_by_edge == {}

    smoke.request_plans[0].request.status = RequestStatus.ASSIGNED
    assert source.request_plans[0].request.status is RequestStatus.WAITING

    closure_smoke = build_smoke_bundle(
        source, vehicle, plans, include_true_closures=True
    )
    assert closure_smoke.true_closures is source.true_closures

    first_closure_time = min(source.true_closures.closure_time_by_edge.values())
    closure_plans = select_smoke_plans(
        source,
        vehicle,
        route_finder,
        request_count=10,
        origin_closure_time_sec=first_closure_time,
    )
    assert all(
        source.true_closures.closure_time_by_edge[plan.request.origin_edge]
        == first_closure_time
        for plan in closure_plans
    )


def test_resolve_sumo_binary_accepts_an_explicit_file(tmp_path: Path) -> None:
    binary = tmp_path / "sumo.exe"
    binary.touch()

    assert resolve_sumo_binary(str(binary)) == binary.resolve()
