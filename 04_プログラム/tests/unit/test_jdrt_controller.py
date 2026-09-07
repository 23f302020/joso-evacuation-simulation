from __future__ import annotations

from collections.abc import Sequence

import pytest

from jdrt import (
    DRTRequest,
    DRTRequestPlan,
    DRTVehicle,
    DynamicTravelTimeDispatcher,
    Evacuee,
    EvacueeStatus,
    FloodRiskAwareDispatcher,
    JDRTController,
    JDRTInputBundle,
    RequestStatus,
    RouteEstimate,
    ShelterInput,
    SumoTraCIPort,
    TransportMode,
    TrueClosureTimeline,
    VehicleStatus,
    build_temporal_forecast,
)


class FakeTraCIPort:
    def __init__(self) -> None:
        self.time = 0
        self.vehicle_edges = {"jdrt_bus_1": "base_edge"}
        self.pending_vehicle_ids: set[str] = set()
        self.stopped_vehicle_ids: set[str] = set()
        self.routes: dict[tuple[str, str, str], RouteEstimate | None] = {}
        self.applied_closures: list[tuple[str, ...]] = []
        self.route_commands: list[tuple[str, tuple[str, ...], str, int]] = []
        self.route_commands_succeed = True
        self.park_commands: list[tuple[str, str, int]] = []
        self.removed_vehicle_ids: list[str] = []

    def current_time(self) -> int:
        return self.time

    def apply_closures(self, edge_ids: Sequence[str]) -> None:
        self.applied_closures.append(tuple(edge_ids))

    def vehicle_exists(self, vehicle_id: str) -> bool:
        return vehicle_id in self.vehicle_edges

    def vehicle_pending(self, vehicle_id: str) -> bool:
        return vehicle_id in self.pending_vehicle_ids

    def vehicle_edge(self, vehicle_id: str) -> str:
        return self.vehicle_edges[vehicle_id]

    def is_stopped_at(self, vehicle_id: str, edge_id: str) -> bool:
        return (
            self.vehicle_edges.get(vehicle_id) == edge_id
            and vehicle_id in self.stopped_vehicle_ids
        )

    def find_route(
        self, from_edge: str, to_edge: str, vehicle_type: str
    ) -> RouteEstimate | None:
        return self.routes.get((from_edge, to_edge, vehicle_type))

    def set_route_and_stop(
        self,
        vehicle_id: str,
        route_edges: Sequence[str],
        stop_edge: str,
        duration_sec: int,
    ) -> bool:
        self.route_commands.append(
            (vehicle_id, tuple(route_edges), stop_edge, duration_sec)
        )
        return self.route_commands_succeed

    def remove_vehicle(self, vehicle_id: str) -> None:
        if vehicle_id in self.vehicle_edges:
            del self.vehicle_edges[vehicle_id]
            self.removed_vehicle_ids.append(vehicle_id)

    def park_vehicle(
        self, vehicle_id: str, edge_id: str, duration_sec: int
    ) -> None:
        self.park_commands.append((vehicle_id, edge_id, duration_sec))


def test_pending_vehicle_is_not_permanently_stranded() -> None:
    input_bundle = bundle()
    port = FakeTraCIPort()
    port.vehicle_edges.clear()
    port.pending_vehicle_ids.add("jdrt_bus_1")
    controller = JDRTController(
        input_bundle,
        port,
        DynamicTravelTimeDispatcher(),
        "JDRT-B2",
    )

    controller.step()

    assert input_bundle.vehicles[0].status is VehicleStatus.IDLE


def bundle(*, closure_time_by_edge: dict[str, int] | None = None) -> JDRTInputBundle:
    person = Evacuee(
        person_id="person_1",
        origin_id="origin_1",
        person_type=4,
        age_group="65歳以上",
        has_private_car=False,
        vulnerability_score=1.0,
        ready_time=0,
        eligible_for_drt=True,
        transport_mode=TransportMode.DRT,
        status=EvacueeStatus.WAITING,
        request_time=0,
    )
    request = DRTRequest(
        request_id="request_1",
        person_ids=(person.person_id,),
        origin_edge="origin_edge",
        request_time=0,
        vulnerability=1.0,
    )
    return JDRTInputBundle(
        city_code="08211",
        evacuees=(person,),
        request_plans=(
            DRTRequestPlan(
                request=request,
                shelter_id="shelter_1",
                shelter_edge="shelter_edge",
            ),
        ),
        vehicles=(
            DRTVehicle(
                vehicle_id="jdrt_bus_1", capacity=4, current_edge="base_edge"
            ),
        ),
        shelters=(
            ShelterInput(
                shelter_id="shelter_1",
                name="test shelter",
                edge_id="shelter_edge",
                capacity=None,
                active_from_sec=0,
                active_until_sec=21_600,
            ),
        ),
        private_vehicles=(),
        true_closures=TrueClosureTimeline(
            closure_time_by_edge=closure_time_by_edge or {}, time_step_count=8
        ),
        parameters={
            "fleet": {"boarding_time_sec": 300, "alighting_time_sec": 300},
            "operation": {"dispatch_interval_sec": 60},
        },
        input_sha256_by_role={},
    )


def add_normal_routes(port: FakeTraCIPort) -> None:
    vehicle_type = "bus_welfare"
    port.routes[("base_edge", "origin_edge", vehicle_type)] = RouteEstimate(
        ("base_edge", "origin_edge"), 10.0
    )
    port.routes[("origin_edge", "shelter_edge", vehicle_type)] = RouteEstimate(
        ("origin_edge", "shelter_edge"), 10.0
    )


def test_temporal_forecast_is_a_copy_and_does_not_change_true_world() -> None:
    true_world = TrueClosureTimeline(
        closure_time_by_edge={"edge_a": 100, "edge_b": 10}, time_step_count=8
    )

    forecast = build_temporal_forecast(true_world, error_sec=-20)
    forecast["edge_a"] = 999

    assert forecast["edge_b"] == 0
    assert true_world.closure_time_by_edge == {"edge_a": 100, "edge_b": 10}


def test_controller_enforces_forecast_information_boundary() -> None:
    data = bundle()
    port = FakeTraCIPort()

    with pytest.raises(ValueError, match="requires predicted closures"):
        JDRTController(
            data,
            port,
            FloodRiskAwareDispatcher(),
            "JDRT-P2-L15",
        )

    with pytest.raises(ValueError, match="must not receive predicted closures"):
        JDRTController(
            data,
            port,
            DynamicTravelTimeDispatcher(),
            "JDRT-B3",
            predicted_closure_time_by_edge={},
        )


def test_complete_service_lifecycle_counts_people_once() -> None:
    data = bundle()
    port = FakeTraCIPort()
    add_normal_routes(port)
    controller = JDRTController(
        data, port, DynamicTravelTimeDispatcher(), "JDRT-B3"
    )

    controller.step()
    plan = data.request_plans[0]
    vehicle = data.vehicles[0]
    person = data.evacuees[0]
    assert plan.request.status is RequestStatus.ASSIGNED
    assert vehicle.status is VehicleStatus.TO_PICKUP
    assert person.status is EvacueeStatus.ASSIGNED

    port.time = 1
    port.vehicle_edges[vehicle.vehicle_id] = "origin_edge"
    port.stopped_vehicle_ids.add(vehicle.vehicle_id)
    controller.step()
    assert vehicle.status is VehicleStatus.BOARDING

    port.time = 301
    port.stopped_vehicle_ids.clear()
    controller.step()
    assert plan.request.status is RequestStatus.ONBOARD
    assert person.status is EvacueeStatus.ONBOARD
    assert vehicle.status is VehicleStatus.TO_SHELTER

    port.time = 302
    port.vehicle_edges[vehicle.vehicle_id] = "shelter_edge"
    port.stopped_vehicle_ids.add(vehicle.vehicle_id)
    controller.step()
    assert vehicle.status is VehicleStatus.ALIGHTING

    port.time = 602
    port.stopped_vehicle_ids.clear()
    controller.step()
    assert plan.request.status is RequestStatus.COMPLETED
    assert person.status is EvacueeStatus.EVACUATED
    assert vehicle.status is VehicleStatus.IDLE
    assert port.park_commands == [("jdrt_bus_1", "shelter_edge", 86_400)]
    assert controller.finish() == {"evacuated": 1, "stranded": 0, "active": 0}


def test_failed_pickup_route_command_strands_only_the_vehicle() -> None:
    data = bundle()
    port = FakeTraCIPort()
    port.routes[("base_edge", "origin_edge", "bus_welfare")] = RouteEstimate(
        ("base_edge", "origin_edge"), 10.0
    )
    port.routes[("origin_edge", "shelter_edge", "bus_welfare")] = RouteEstimate(
        ("origin_edge", "shelter_edge"), 10.0
    )
    port.route_commands_succeed = False
    controller = JDRTController(
        data, port, DynamicTravelTimeDispatcher(), "JDRT-B2"
    )

    controller.step()

    assert data.vehicles[0].status is VehicleStatus.STRANDED
    assert data.request_plans[0].request.status is RequestStatus.WAITING
    assert data.evacuees[0].status is EvacueeStatus.WAITING
    assert controller.runtime["jdrt_bus_1"].plan is None


def test_risk_dispatch_uses_predicted_not_true_closure_time() -> None:
    data = bundle(closure_time_by_edge={"shelter_edge": 100})
    port = FakeTraCIPort()
    add_normal_routes(port)
    controller = JDRTController(
        data,
        port,
        FloodRiskAwareDispatcher(safety_margin_sec=300),
        "JDRT-P2-L15",
        predicted_closure_time_by_edge={"shelter_edge": 1_000},
    )

    controller.step()

    assert data.request_plans[0].request.status is RequestStatus.ASSIGNED
    assert controller.applied_closed_edges == set()


def test_completion_at_dispatch_boundary_does_not_issue_conflicting_park() -> None:
    data = bundle()
    port = FakeTraCIPort()
    add_normal_routes(port)
    controller = JDRTController(
        data, port, DynamicTravelTimeDispatcher(), "JDRT-B3"
    )
    controller.step()
    vehicle = data.vehicles[0]

    port.time = 1
    port.vehicle_edges[vehicle.vehicle_id] = "origin_edge"
    port.stopped_vehicle_ids.add(vehicle.vehicle_id)
    controller.step()
    port.time = 301
    port.stopped_vehicle_ids.clear()
    controller.step()
    port.time = 302
    port.vehicle_edges[vehicle.vehicle_id] = "shelter_edge"
    port.stopped_vehicle_ids.add(vehicle.vehicle_id)
    controller.step()

    second_person = Evacuee(
        person_id="person_2",
        origin_id="origin_2",
        person_type=4,
        age_group="65歳以上",
        has_private_car=False,
        vulnerability_score=1.0,
        ready_time=0,
        eligible_for_drt=True,
        transport_mode=TransportMode.DRT,
        status=EvacueeStatus.WAITING,
        request_time=0,
    )
    second_request = DRTRequest(
        request_id="request_2",
        person_ids=(second_person.person_id,),
        origin_edge="origin_edge_2",
        request_time=0,
        vulnerability=1.0,
    )
    second_plan = DRTRequestPlan(
        request=second_request,
        shelter_id="shelter_1",
        shelter_edge="shelter_edge",
    )
    controller.evacuees[second_person.person_id] = second_person
    controller.plans[second_request.request_id] = second_plan
    port.routes[("shelter_edge", "origin_edge_2", "bus_welfare")] = RouteEstimate(
        ("shelter_edge", "origin_edge_2"), 10.0
    )
    port.routes[("origin_edge_2", "shelter_edge", "bus_welfare")] = RouteEstimate(
        ("origin_edge_2", "shelter_edge"), 10.0
    )

    controller.runtime[vehicle.vehicle_id].dwell_until_sec = 660
    port.time = 660
    port.stopped_vehicle_ids.clear()
    controller.step()

    assert port.park_commands == []
    assert second_request.status is RequestStatus.ASSIGNED
    assert vehicle.status is VehicleStatus.TO_PICKUP


def test_true_closure_strands_vehicle_that_entered_closed_edge() -> None:
    data = bundle(closure_time_by_edge={"closed_edge": 60})
    port = FakeTraCIPort()
    port.routes[("base_edge", "origin_edge", "bus_welfare")] = RouteEstimate(
        ("base_edge", "closed_edge", "origin_edge"), 10.0
    )
    port.routes[("origin_edge", "shelter_edge", "bus_welfare")] = RouteEstimate(
        ("origin_edge", "shelter_edge"), 10.0
    )
    controller = JDRTController(
        data, port, DynamicTravelTimeDispatcher(), "JDRT-B3"
    )
    controller.step()

    port.time = 60
    port.vehicle_edges["jdrt_bus_1"] = "closed_edge"
    controller.step()

    assert port.applied_closures == [("closed_edge",)]
    assert port.removed_vehicle_ids == ["jdrt_bus_1"]
    assert data.vehicles[0].status is VehicleStatus.STRANDED
    assert data.request_plans[0].request.status is RequestStatus.STRANDED
    assert data.evacuees[0].status is EvacueeStatus.STRANDED
    assert controller.runtime["jdrt_bus_1"].plan is None

    port.time = 61
    controller.step()

    assert port.removed_vehicle_ids == ["jdrt_bus_1"]


def test_waiting_request_is_closed_once_without_route_queries() -> None:
    data = bundle(closure_time_by_edge={"origin_edge": 0})
    port = FakeTraCIPort()
    controller = JDRTController(
        data, port, DynamicTravelTimeDispatcher(), "JDRT-B3"
    )

    controller.step()

    assert data.request_plans[0].request.status is RequestStatus.STRANDED
    assert data.evacuees[0].status is EvacueeStatus.STRANDED
    assert port.route_commands == []


def test_dispatch_reuses_route_queries_for_same_origin_and_shelter() -> None:
    data = bundle()
    first_plan = data.request_plans[0]
    second_person = Evacuee(
        person_id="person_2",
        origin_id="origin_1",
        person_type=3,
        age_group="65歳未満",
        has_private_car=False,
        vulnerability_score=0.0,
        ready_time=0,
        eligible_for_drt=True,
        transport_mode=TransportMode.DRT,
        status=EvacueeStatus.WAITING,
        request_time=0,
    )
    second_plan = DRTRequestPlan(
        request=DRTRequest(
            request_id="request_2",
            person_ids=(second_person.person_id,),
            origin_edge=first_plan.request.origin_edge,
            request_time=0,
            vulnerability=0.0,
        ),
        shelter_id=first_plan.shelter_id,
        shelter_edge=first_plan.shelter_edge,
    )
    controller_bundle = JDRTInputBundle(
        city_code=data.city_code,
        evacuees=data.evacuees + (second_person,),
        request_plans=data.request_plans + (second_plan,),
        vehicles=data.vehicles,
        shelters=data.shelters,
        private_vehicles=(),
        true_closures=data.true_closures,
        parameters=data.parameters,
        input_sha256_by_role={},
    )
    port = FakeTraCIPort()
    add_normal_routes(port)
    calls: list[tuple[str, str, str]] = []
    original_find_route = port.find_route

    def counted_find_route(
        from_edge: str, to_edge: str, vehicle_type: str
    ) -> RouteEstimate | None:
        calls.append((from_edge, to_edge, vehicle_type))
        return original_find_route(from_edge, to_edge, vehicle_type)

    port.find_route = counted_find_route  # type: ignore[method-assign]
    controller = JDRTController(
        controller_bundle, port, DynamicTravelTimeDispatcher(), "JDRT-B3"
    )

    controller.step()

    assert calls == [
        ("base_edge", "origin_edge", "bus_welfare"),
        ("origin_edge", "shelter_edge", "bus_welfare"),
    ]


def test_b2_branch_and_bound_keeps_exact_best_and_skips_worse_bound() -> None:
    data = bundle()
    first_plan = data.request_plans[0]
    extra_people = []
    extra_plans = []
    for number, edge in ((2, "near_edge"), (3, "far_edge")):
        person = Evacuee(
            person_id=f"person_{number}",
            origin_id=f"origin_{number}",
            person_type=4,
            age_group="65歳以上",
            has_private_car=False,
            vulnerability_score=1.0,
            ready_time=0,
            eligible_for_drt=True,
            transport_mode=TransportMode.DRT,
            status=EvacueeStatus.WAITING,
            request_time=0,
        )
        extra_people.append(person)
        extra_plans.append(
            DRTRequestPlan(
                request=DRTRequest(
                    request_id=f"request_{number}",
                    person_ids=(person.person_id,),
                    origin_edge=edge,
                    request_time=0,
                    vulnerability=1.0,
                ),
                shelter_id=first_plan.shelter_id,
                shelter_edge=first_plan.shelter_edge,
            )
        )
    controller_bundle = JDRTInputBundle(
        city_code=data.city_code,
        evacuees=data.evacuees + tuple(extra_people),
        request_plans=data.request_plans + tuple(extra_plans),
        vehicles=data.vehicles,
        shelters=data.shelters,
        private_vehicles=(),
        true_closures=data.true_closures,
        parameters=data.parameters,
        input_sha256_by_role={},
    )
    port = FakeTraCIPort()
    port.routes[("base_edge", "near_edge", "bus_welfare")] = RouteEstimate(
        ("base_edge", "near_edge"), 5.0
    )
    port.routes[("near_edge", "shelter_edge", "bus_welfare")] = RouteEstimate(
        ("near_edge", "shelter_edge"), 5.0
    )
    port.routes[("base_edge", "origin_edge", "bus_welfare")] = RouteEstimate(
        ("base_edge", "origin_edge"), 20.0
    )
    port.routes[("origin_edge", "shelter_edge", "bus_welfare")] = RouteEstimate(
        ("origin_edge", "shelter_edge"), 20.0
    )
    lower_bounds = {
        "near_edge": 310.0,
        "origin_edge": 340.0,
        "far_edge": 1_000.0,
    }
    controller = JDRTController(
        controller_bundle,
        port,
        DynamicTravelTimeDispatcher(),
        "JDRT-B2",
        service_time_lower_bound=lambda vehicle, plan: lower_bounds[
            plan.request.origin_edge
        ],
    )

    controller.step()

    assert extra_plans[0].request.status is RequestStatus.ASSIGNED
    assert ("base_edge", "far_edge", "bus_welfare") not in port.routes
    assert all(command[2] != "far_edge" for command in port.route_commands)


def test_sumo_port_translates_controller_commands_to_traci_calls() -> None:
    class FakeSimulation:
        def getTime(self) -> float:
            return 60.0

        def getPendingVehicles(self) -> tuple[str, ...]:
            return ()

        def findRoute(
            self, from_edge: str, to_edge: str, *, vType: str, routingMode: int
        ):
            assert (from_edge, to_edge, vType, routingMode) == (
                "base_edge",
                "shelter_edge",
                "bus_welfare",
                1,
            )
            return type(
                "Stage", (), {"edges": ("base_edge", "shelter_edge"), "travelTime": 12.5}
            )()

    class FakeEdge:
        def __init__(self) -> None:
            self.calls: list[tuple[str, list[str]]] = []

        def setDisallowed(self, edge_id: str, vehicle_classes: list[str]) -> None:
            self.calls.append((edge_id, vehicle_classes))

        def getLaneNumber(self, edge_id: str) -> int:
            assert edge_id in {"base_edge", "middle_edge", "shelter_edge"}
            return 1

    class FakeLane:
        def __init__(self) -> None:
            self.connected = True
            self.target_by_lane = {
                "base_edge_0": "shelter_edge_0",
                "middle_edge_0": "other_edge_0",
            }

        def getLinks(self, lane_id: str):
            target = self.target_by_lane[lane_id]
            if lane_id == "base_edge_0" and not self.connected:
                target = "other_edge_0"
            return ((target, True, True, False, "", "G", "s", 1.0),)

        def getEdgeID(self, lane_id: str) -> str:
            return lane_id.removesuffix("_0")

        def getAllowed(self, lane_id: str) -> tuple[str, ...]:
            assert lane_id == "shelter_edge_0"
            return ("bus", "passenger")

        def getLength(self, lane_id: str) -> float:
            assert lane_id == "shelter_edge_0"
            return 50.0

    class FakeVehicle:
        def __init__(self) -> None:
            self.routes: list[tuple[str, list[str]]] = []
            self.stops: list[tuple[str, str, float]] = []
            self.removed: list[str] = []
            self.resumed: list[str] = []
            self.speeds: list[tuple[str, float]] = []

        def getIDList(self) -> tuple[str, ...]:
            return ("jdrt_bus_1",)

        def getRoadID(self, vehicle_id: str) -> str:
            assert vehicle_id == "jdrt_bus_1"
            return "base_edge"

        def getLaneID(self, vehicle_id: str) -> str:
            assert vehicle_id == "jdrt_bus_1"
            return "base_edge_0"

        def isStopped(self, vehicle_id: str) -> bool:
            return False

        def getSpeed(self, vehicle_id: str) -> float:
            return 0.05

        def setRoute(self, vehicle_id: str, edges: list[str]) -> None:
            self.routes.append((vehicle_id, edges))

        def setStop(
            self,
            vehicle_id: str,
            edge_id: str,
            *,
            pos: float,
            laneIndex: int,
            duration: float,
        ) -> None:
            self.stops.append((vehicle_id, edge_id, pos, laneIndex, duration))

        def resume(self, vehicle_id: str) -> None:
            self.resumed.append(vehicle_id)

        def setSpeed(self, vehicle_id: str, speed: float) -> None:
            self.speeds.append((vehicle_id, speed))

        def remove(self, vehicle_id: str) -> None:
            self.removed.append(vehicle_id)

    fake_traci = type(
        "FakeTraCI",
        (),
        {
            "simulation": FakeSimulation(),
            "edge": FakeEdge(),
            "lane": FakeLane(),
            "vehicle": FakeVehicle(),
            "TraCIException": RuntimeError,
        },
    )()
    port = SumoTraCIPort(fake_traci, {"jdrt_bus_1": "bus_welfare"})

    port.apply_closures(("closed_edge",))
    route = port.find_route("base_edge", "shelter_edge", "bus_welfare")
    port.set_route_and_stop(
        "jdrt_bus_1", route.edges, "shelter_edge", duration_sec=300
    )
    fake_traci.lane.connected = False
    assert not port.set_route_and_stop(
        "jdrt_bus_1", route.edges, "shelter_edge", duration_sec=300
    )
    fake_traci.lane.connected = True
    fake_traci.lane.target_by_lane["base_edge_0"] = "middle_edge_0"
    assert not port.set_route_and_stop(
        "jdrt_bus_1",
        ("base_edge", "middle_edge", "shelter_edge"),
        "shelter_edge",
        duration_sec=300,
    )
    port.park_vehicle("jdrt_bus_1", "base_edge", duration_sec=86_400)
    port.remove_vehicle("jdrt_bus_1")

    assert port.current_time() == 60
    assert port.vehicle_exists("jdrt_bus_1")
    assert port.vehicle_edge("jdrt_bus_1") == "base_edge"
    assert port.is_stopped_at("jdrt_bus_1", "base_edge")
    assert route == RouteEstimate(("base_edge", "shelter_edge"), 12.5)
    assert fake_traci.edge.calls == [("closed_edge", ["passenger", "bus"])]
    assert fake_traci.vehicle.routes == [
        ("jdrt_bus_1", ["base_edge", "shelter_edge"])
    ]
    assert fake_traci.vehicle.stops == [
        ("jdrt_bus_1", "shelter_edge", 49.0, 0, 301.0)
    ]
    assert fake_traci.vehicle.speeds == [
        ("jdrt_bus_1", -1),
        ("jdrt_bus_1", 0),
    ]
    assert fake_traci.vehicle.removed == ["jdrt_bus_1"]
