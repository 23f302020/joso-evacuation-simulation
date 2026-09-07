"""JDRT-only controller with an injectable SUMO/TraCI boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol, Sequence

from .dispatch import DynamicTravelTimeDispatcher, FloodRiskAwareDispatcher
from .domain import (
    AssignmentCandidate,
    DRTVehicle,
    Evacuee,
    EvacueeStatus,
    ForecastState,
    NetworkState,
    RequestStatus,
    VehicleStatus,
)
from .input_adapter import DRTRequestPlan, JDRTInputBundle, TrueClosureTimeline
from .run_records import JDRTEvent, RunRecorder


@dataclass(frozen=True)
class RouteEstimate:
    edges: tuple[str, ...]
    travel_time_sec: float

    def __post_init__(self) -> None:
        if not self.edges:
            raise ValueError("route edges must not be empty")
        if self.travel_time_sec < 0:
            raise ValueError("route travel time must be non-negative")


class TraCIPort(Protocol):
    def current_time(self) -> int: ...

    def apply_closures(self, edge_ids: Sequence[str]) -> None: ...

    def vehicle_exists(self, vehicle_id: str) -> bool: ...

    def vehicle_pending(self, vehicle_id: str) -> bool: ...

    def vehicle_edge(self, vehicle_id: str) -> str: ...

    def is_stopped_at(self, vehicle_id: str, edge_id: str) -> bool: ...

    def find_route(
        self, from_edge: str, to_edge: str, vehicle_type: str
    ) -> RouteEstimate | None: ...

    def set_route_and_stop(
        self,
        vehicle_id: str,
        route_edges: Sequence[str],
        stop_edge: str,
        duration_sec: int,
    ) -> bool: ...

    def park_vehicle(
        self, vehicle_id: str, edge_id: str, duration_sec: int
    ) -> None: ...

    def remove_vehicle(self, vehicle_id: str) -> None: ...


class SumoTraCIPort:
    """Small adapter over the SUMO 1.26.0 TraCI API."""

    def __init__(
        self,
        traci_module: object,
        vehicle_type_by_id: Mapping[str, str],
        *,
        stop_speed_threshold: float = 0.1,
    ) -> None:
        self._traci = traci_module
        self._vehicle_type_by_id = dict(vehicle_type_by_id)
        self._stop_speed_threshold = stop_speed_threshold

    def current_time(self) -> int:
        return int(self._traci.simulation.getTime())

    def apply_closures(self, edge_ids: Sequence[str]) -> None:
        for edge_id in edge_ids:
            self._traci.edge.setDisallowed(edge_id, ["passenger", "bus"])

    def vehicle_exists(self, vehicle_id: str) -> bool:
        return vehicle_id in set(self._traci.vehicle.getIDList())

    def vehicle_pending(self, vehicle_id: str) -> bool:
        return vehicle_id in set(self._traci.simulation.getPendingVehicles())

    def vehicle_edge(self, vehicle_id: str) -> str:
        return str(self._traci.vehicle.getRoadID(vehicle_id))

    def is_stopped_at(self, vehicle_id: str, edge_id: str) -> bool:
        return self.vehicle_edge(vehicle_id) == edge_id and (
            bool(self._traci.vehicle.isStopped(vehicle_id))
            or float(self._traci.vehicle.getSpeed(vehicle_id))
            < self._stop_speed_threshold
        )

    def find_route(
        self, from_edge: str, to_edge: str, vehicle_type: str
    ) -> RouteEstimate | None:
        try:
            stage = self._traci.simulation.findRoute(
                from_edge,
                to_edge,
                vType=vehicle_type,
                routingMode=getattr(
                    getattr(self._traci, "constants", None),
                    "ROUTING_MODE_AGGREGATED",
                    1,
                ),
            )
        except self._traci.TraCIException:
            return None
        edges = tuple(str(edge_id) for edge_id in stage.edges)
        if not edges:
            return None
        return RouteEstimate(edges, float(stage.travelTime))

    def _route_is_connected(
        self, vehicle_id: str, route_edges: Sequence[str]
    ) -> bool:
        current_edge = self.vehicle_edge(vehicle_id)
        if not route_edges or route_edges[0] != current_edge:
            return False
        if len(route_edges) == 1:
            return True
        current_lane = str(self._traci.vehicle.getLaneID(vehicle_id))
        if not any(
            self._traci.lane.getEdgeID(link[0]) == route_edges[1]
            for link in self._traci.lane.getLinks(current_lane)
        ):
            return False
        for from_edge, to_edge in zip(route_edges[1:-1], route_edges[2:]):
            connected = False
            for index in range(int(self._traci.edge.getLaneNumber(from_edge))):
                lane_id = f"{from_edge}_{index}"
                if any(
                    self._traci.lane.getEdgeID(link[0]) == to_edge
                    for link in self._traci.lane.getLinks(lane_id)
                ):
                    connected = True
                    break
            if not connected:
                return False
        return True

    def set_route_and_stop(
        self,
        vehicle_id: str,
        route_edges: Sequence[str],
        stop_edge: str,
        duration_sec: int,
    ) -> bool:
        if not self._route_is_connected(vehicle_id, route_edges):
            return False
        try:
            self._traci.vehicle.setSpeed(vehicle_id, -1)
            if self._traci.vehicle.isStopped(vehicle_id):
                self._traci.vehicle.resume(vehicle_id)
            self._traci.vehicle.setRoute(vehicle_id, list(route_edges))
            lane_index = 0
            stop_pos = 1.0
            for index in range(int(self._traci.edge.getLaneNumber(stop_edge))):
                lane_id = f"{stop_edge}_{index}"
                allowed = set(self._traci.lane.getAllowed(lane_id))
                if not allowed or "bus" in allowed:
                    lane_index = index
                    stop_pos = max(
                        1.0, float(self._traci.lane.getLength(lane_id)) - 1.0
                    )
                    break
            self._traci.vehicle.setStop(
                vehicle_id,
                stop_edge,
                pos=stop_pos,
                laneIndex=lane_index,
                # Keep one SUMO step of control grace.  The controller resumes the
                # vehicle after exactly duration_sec, before route-end removal.
                duration=float(duration_sec + 1),
            )
        except self._traci.TraCIException:
            return False
        return True

    def park_vehicle(
        self, vehicle_id: str, edge_id: str, duration_sec: int
    ) -> None:
        del edge_id, duration_sec
        self._traci.vehicle.setSpeed(vehicle_id, 0)

    def remove_vehicle(self, vehicle_id: str) -> None:
        if self.vehicle_exists(vehicle_id):
            self._traci.vehicle.remove(vehicle_id)


def build_temporal_forecast(
    true_closures: TrueClosureTimeline,
    error_sec: int,
) -> dict[str, int]:
    """Create Perceived World times without changing the True World object."""

    return {
        edge_id: max(0, closure_time + error_sec)
        for edge_id, closure_time in true_closures.closure_time_by_edge.items()
    }


@dataclass
class _VehicleRuntime:
    plan: DRTRequestPlan | None = None
    pickup_route: tuple[str, ...] = ()
    shelter_route: tuple[str, ...] = ()
    dwell_until_sec: int | None = None


class JDRTController:
    """Advance JDRT assignment and service state using only a TraCI port."""

    def __init__(
        self,
        bundle: JDRTInputBundle,
        port: TraCIPort,
        dispatcher: object,
        scenario_id: str,
        *,
        predicted_closure_time_by_edge: Mapping[str, int] | None = None,
        recorder: RunRecorder | None = None,
        service_time_lower_bound: Callable[[DRTVehicle, DRTRequestPlan], float]
        | None = None,
    ) -> None:
        if not scenario_id.startswith("JDRT-"):
            raise ValueError("scenario_id must use the JDRT- namespace")
        if isinstance(dispatcher, FloodRiskAwareDispatcher):
            if predicted_closure_time_by_edge is None:
                raise ValueError("risk-aware dispatcher requires predicted closures")
        elif predicted_closure_time_by_edge is not None:
            raise ValueError("non-risk dispatcher must not receive predicted closures")

        self.bundle = bundle
        self.port = port
        self.dispatcher = dispatcher
        self.scenario_id = scenario_id
        self.predicted_closures = (
            dict(predicted_closure_time_by_edge)
            if predicted_closure_time_by_edge is not None
            else None
        )
        self.recorder = recorder
        self.service_time_lower_bound = service_time_lower_bound
        self.parameters = bundle.parameters
        self.evacuees = {person.person_id: person for person in bundle.evacuees}
        self.plans = {
            plan.request.request_id: plan for plan in bundle.request_plans
        }
        self.vehicles = {vehicle.vehicle_id: vehicle for vehicle in bundle.vehicles}
        self.runtime = {vehicle_id: _VehicleRuntime() for vehicle_id in self.vehicles}
        self.applied_closed_edges: set[str] = set()
        self._finished = False

    def _record(
        self,
        sim_time: int,
        event_type: str,
        entity_id: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        if self.recorder is not None:
            self.recorder.append(
                JDRTEvent(sim_time, event_type, entity_id, details or {})
            )

    def _vehicle_type(self, vehicle: DRTVehicle) -> str:
        return "bus_welfare" if vehicle.capacity == 4 else "bus_standard"

    def _apply_due_closures(self, sim_time: int) -> None:
        due = sorted(
            edge_id
            for edge_id, closure_time in self.bundle.true_closures.closure_time_by_edge.items()
            if closure_time <= sim_time and edge_id not in self.applied_closed_edges
        )
        if not due:
            return
        self.port.apply_closures(due)
        self.applied_closed_edges.update(due)
        self._record(sim_time, "TRUE_CLOSURE_APPLIED", "network", {"edges": due})
        self._handle_active_routes_after_closure(sim_time)
        for plan in self.plans.values():
            if (
                plan.request.status is RequestStatus.WAITING
                and plan.request.origin_edge in self.applied_closed_edges
            ):
                self._mark_plan_stranded(
                    plan, sim_time, "ORIGIN_EDGE_CLOSED_BEFORE_ASSIGNMENT"
                )

    def _mark_plan_stranded(
        self,
        plan: DRTRequestPlan,
        sim_time: int,
        reason: str,
    ) -> None:
        plan.request.status = RequestStatus.STRANDED
        for person_id in plan.request.person_ids:
            person = self.evacuees[person_id]
            person.status = EvacueeStatus.STRANDED
        self._record(
            sim_time,
            "REQUEST_STRANDED",
            plan.request.request_id,
            {"reason": reason},
        )

    def _strand_vehicle(
        self,
        vehicle: DRTVehicle,
        sim_time: int,
        reason: str,
    ) -> None:
        runtime = self.runtime[vehicle.vehicle_id]
        if runtime.plan is not None:
            self._mark_plan_stranded(runtime.plan, sim_time, reason)
        runtime.plan = None
        runtime.pickup_route = ()
        runtime.shelter_route = ()
        runtime.dwell_until_sec = None
        vehicle.onboard_person_ids = ()
        vehicle.status = VehicleStatus.STRANDED
        self.port.remove_vehicle(vehicle.vehicle_id)
        self._record(sim_time, "VEHICLE_STRANDED", vehicle.vehicle_id, {"reason": reason})

    def _handle_active_routes_after_closure(self, sim_time: int) -> None:
        for vehicle in self.vehicles.values():
            runtime = self.runtime[vehicle.vehicle_id]
            if runtime.plan is None or vehicle.status not in {
                VehicleStatus.TO_PICKUP,
                VehicleStatus.TO_SHELTER,
            }:
                continue
            if not self.port.vehicle_exists(vehicle.vehicle_id):
                self._strand_vehicle(vehicle, sim_time, "VEHICLE_MISSING")
                continue
            current_edge = self.port.vehicle_edge(vehicle.vehicle_id)
            vehicle.current_edge = current_edge
            if current_edge in self.applied_closed_edges:
                self._strand_vehicle(vehicle, sim_time, "CLOSED_EDGE_ENTRY")
                continue
            target_edge = (
                runtime.plan.request.origin_edge
                if vehicle.status is VehicleStatus.TO_PICKUP
                else runtime.plan.shelter_edge
            )
            if target_edge in self.applied_closed_edges:
                if vehicle.status is VehicleStatus.TO_PICKUP:
                    self._mark_plan_stranded(
                        runtime.plan, sim_time, "ORIGIN_EDGE_CLOSED_BEFORE_PICKUP"
                    )
                    runtime.plan = None
                    runtime.dwell_until_sec = None
                    vehicle.status = VehicleStatus.IDLE
                    vehicle.onboard_person_ids = ()
                    self.port.park_vehicle(vehicle.vehicle_id, current_edge, 86_400)
                else:
                    self._strand_vehicle(
                        vehicle, sim_time, "SHELTER_EDGE_CLOSED_AFTER_PICKUP"
                    )
                continue
            reroute = self.port.find_route(
                current_edge, target_edge, self._vehicle_type(vehicle)
            )
            if reroute is None or self.applied_closed_edges.intersection(reroute.edges):
                if vehicle.status is VehicleStatus.TO_PICKUP:
                    self._mark_plan_stranded(
                        runtime.plan, sim_time, "ROAD_CLOSED_BEFORE_PICKUP"
                    )
                    runtime.plan = None
                    runtime.dwell_until_sec = None
                    vehicle.status = VehicleStatus.IDLE
                    vehicle.onboard_person_ids = ()
                    self.port.park_vehicle(vehicle.vehicle_id, current_edge, 86_400)
                else:
                    self._strand_vehicle(
                        vehicle, sim_time, "ROAD_CLOSED_AFTER_PICKUP"
                    )
                continue
            dwell = int(
                self.parameters["fleet"][
                    "boarding_time_sec"
                    if vehicle.status is VehicleStatus.TO_PICKUP
                    else "alighting_time_sec"
                ]
            )
            if not self.port.set_route_and_stop(
                vehicle.vehicle_id, reroute.edges, target_edge, dwell
            ):
                self._strand_vehicle(vehicle, sim_time, "REROUTE_COMMAND_FAILED")
                continue
            if vehicle.status is VehicleStatus.TO_PICKUP:
                runtime.pickup_route = reroute.edges
            else:
                runtime.shelter_route = reroute.edges
            self._record(sim_time, "VEHICLE_REROUTED", vehicle.vehicle_id)

    def _advance_vehicle(self, vehicle: DRTVehicle, sim_time: int) -> None:
        runtime = self.runtime[vehicle.vehicle_id]
        plan = runtime.plan
        if plan is None:
            return
        if not self.port.vehicle_exists(vehicle.vehicle_id):
            self._strand_vehicle(vehicle, sim_time, "VEHICLE_MISSING")
            return
        vehicle.current_edge = self.port.vehicle_edge(vehicle.vehicle_id)

        if vehicle.status is VehicleStatus.TO_PICKUP and self.port.is_stopped_at(
            vehicle.vehicle_id, plan.request.origin_edge
        ):
            vehicle.status = VehicleStatus.BOARDING
            runtime.dwell_until_sec = sim_time + int(
                self.parameters["fleet"]["boarding_time_sec"]
            )
            self._record(sim_time, "BOARDING_STARTED", plan.request.request_id)
            return

        if (
            vehicle.status is VehicleStatus.BOARDING
            and runtime.dwell_until_sec is not None
            and sim_time >= runtime.dwell_until_sec
        ):
            route = self.port.find_route(
                vehicle.current_edge, plan.shelter_edge, self._vehicle_type(vehicle)
            )
            if route is None or self.applied_closed_edges.intersection(route.edges):
                self._strand_vehicle(vehicle, sim_time, "NO_SAFE_ROUTE_AFTER_PICKUP")
                return
            if not self.port.set_route_and_stop(
                vehicle.vehicle_id,
                route.edges,
                plan.shelter_edge,
                int(self.parameters["fleet"]["alighting_time_sec"]),
            ):
                self._strand_vehicle(vehicle, sim_time, "SHELTER_ROUTE_COMMAND_FAILED")
                return
            plan.request.status = RequestStatus.ONBOARD
            vehicle.onboard_person_ids = plan.request.person_ids
            for person_id in plan.request.person_ids:
                person = self.evacuees[person_id]
                person.status = EvacueeStatus.ONBOARD
                person.pickup_time = sim_time
            vehicle.status = VehicleStatus.TO_SHELTER
            runtime.dwell_until_sec = None
            runtime.shelter_route = route.edges
            self._record(sim_time, "PICKUP_COMPLETED", plan.request.request_id)
            return

        if vehicle.status is VehicleStatus.TO_SHELTER and self.port.is_stopped_at(
            vehicle.vehicle_id, plan.shelter_edge
        ):
            vehicle.status = VehicleStatus.ALIGHTING
            runtime.dwell_until_sec = sim_time + int(
                self.parameters["fleet"]["alighting_time_sec"]
            )
            self._record(sim_time, "ALIGHTING_STARTED", plan.request.request_id)
            return

        if (
            vehicle.status is VehicleStatus.ALIGHTING
            and runtime.dwell_until_sec is not None
            and sim_time >= runtime.dwell_until_sec
        ):
            plan.request.status = RequestStatus.COMPLETED
            for person_id in plan.request.person_ids:
                person = self.evacuees[person_id]
                person.status = EvacueeStatus.EVACUATED
                person.arrival_time = sim_time
            vehicle.onboard_person_ids = ()
            vehicle.status = VehicleStatus.IDLE
            runtime.plan = None
            runtime.pickup_route = ()
            runtime.shelter_route = ()
            runtime.dwell_until_sec = None
            dispatch_interval = int(
                self.parameters["operation"]["dispatch_interval_sec"]
            )
            has_waiting_request = any(
                item.request.status is RequestStatus.WAITING
                for item in self.plans.values()
            )
            if sim_time % dispatch_interval != 0 or not has_waiting_request:
                self.port.park_vehicle(vehicle.vehicle_id, plan.shelter_edge, 86_400)
            self._record(sim_time, "REQUEST_COMPLETED", plan.request.request_id)

    def _candidate(
        self,
        vehicle: DRTVehicle,
        plan: DRTRequestPlan,
        sim_time: int,
        route_cache: dict[tuple[str, str, str], RouteEstimate | None] | None = None,
    ) -> tuple[AssignmentCandidate, RouteEstimate, RouteEstimate] | None:
        if plan.request.party_size > vehicle.remaining_capacity:
            return None
        if (
            plan.request.origin_edge in self.applied_closed_edges
            or plan.shelter_edge in self.applied_closed_edges
        ):
            return None
        vehicle_type = self._vehicle_type(vehicle)
        cache = route_cache if route_cache is not None else {}

        def find(from_edge: str, to_edge: str) -> RouteEstimate | None:
            key = (from_edge, to_edge, vehicle_type)
            if key not in cache:
                cache[key] = self.port.find_route(from_edge, to_edge, vehicle_type)
            return cache[key]

        to_pickup = find(vehicle.current_edge, plan.request.origin_edge)
        to_shelter = find(plan.request.origin_edge, plan.shelter_edge)
        if to_pickup is None or to_shelter is None:
            return None
        candidate = AssignmentCandidate(
            request_id=plan.request.request_id,
            vehicle_id=vehicle.vehicle_id,
            route_to_pickup=to_pickup.edges,
            route_to_shelter=to_shelter.edges,
            pickup_time_sec=to_pickup.travel_time_sec,
            shelter_travel_time_sec=to_shelter.travel_time_sec,
            boarding_time_sec=float(self.parameters["fleet"]["boarding_time_sec"]),
            waiting_time_sec=float(sim_time - plan.request.request_time),
            vulnerability=plan.request.vulnerability,
            remaining_capacity=vehicle.remaining_capacity,
            party_size=plan.request.party_size,
            request_status=plan.request.status,
            vehicle_status=vehicle.status,
        )
        return candidate, to_pickup, to_shelter

    def _dispatch(self, sim_time: int) -> None:
        network_state = NetworkState(
            current_time=sim_time,
            closed_edges=frozenset(self.applied_closed_edges),
        )
        route_cache: dict[tuple[str, str, str], RouteEstimate | None] = {}
        for vehicle in sorted(self.vehicles.values(), key=lambda item: item.vehicle_id):
            if vehicle.status is not VehicleStatus.IDLE:
                continue
            if not self.port.vehicle_exists(vehicle.vehicle_id):
                if self.port.vehicle_pending(vehicle.vehicle_id):
                    continue
                vehicle.status = VehicleStatus.STRANDED
                continue
            vehicle.current_edge = self.port.vehicle_edge(vehicle.vehicle_id)
            waiting_plans = [
                plan
                for plan in sorted(
                    self.plans.values(), key=lambda item: item.request.request_id
                )
                if plan.request.status is RequestStatus.WAITING
            ]
            if (
                isinstance(self.dispatcher, DynamicTravelTimeDispatcher)
                and self.service_time_lower_bound is not None
            ):
                grouped: dict[tuple[str, str], list[DRTRequestPlan]] = {}
                for plan in waiting_plans:
                    if plan.request.party_size <= vehicle.remaining_capacity:
                        grouped.setdefault(
                            (plan.request.origin_edge, plan.shelter_edge), []
                        ).append(plan)
                bounded_plans = [
                    (
                        self.service_time_lower_bound(vehicle, plans[0]),
                        min(plans, key=lambda item: item.request.request_id),
                    )
                    for plans in grouped.values()
                ]
                prepared = []
                best_service_time = float("inf")
                for lower_bound, plan in sorted(
                    bounded_plans,
                    key=lambda item: (item[0], item[1].request.request_id),
                ):
                    if lower_bound > best_service_time:
                        break
                    value = self._candidate(
                        vehicle, plan, sim_time, route_cache=route_cache
                    )
                    if value is not None:
                        prepared.append(value)
                        best_service_time = min(
                            best_service_time, value[0].total_service_time_sec
                        )
            else:
                prepared = [
                    value
                    for plan in waiting_plans
                    for value in [
                        self._candidate(
                            vehicle, plan, sim_time, route_cache=route_cache
                        )
                    ]
                    if value is not None
                ]
            if not prepared:
                continue
            candidates = [item[0] for item in prepared]
            if isinstance(self.dispatcher, FloodRiskAwareDispatcher):
                forecast_state = ForecastState(
                    current_time=sim_time,
                    predicted_closure_time_by_edge=self.predicted_closures or {},
                )
                selected = self.dispatcher.select(
                    candidates, network_state, forecast_state
                )
            else:
                selected = self.dispatcher.select(candidates, network_state)
            if selected is None:
                continue
            selected_plan = self.plans[selected.request_id]
            route_index = {
                item[0].request_id: (item[1], item[2]) for item in prepared
            }
            pickup_route, shelter_route = route_index[selected.request_id]
            if not self.port.set_route_and_stop(
                vehicle.vehicle_id,
                pickup_route.edges,
                selected_plan.request.origin_edge,
                int(self.parameters["fleet"]["boarding_time_sec"]),
            ):
                self._strand_vehicle(vehicle, sim_time, "PICKUP_ROUTE_COMMAND_FAILED")
                continue
            selected_plan.request.status = RequestStatus.ASSIGNED
            selected_plan.request.assigned_vehicle_id = vehicle.vehicle_id
            for person_id in selected_plan.request.person_ids:
                self.evacuees[person_id].status = EvacueeStatus.ASSIGNED
            vehicle.status = VehicleStatus.TO_PICKUP
            runtime = self.runtime[vehicle.vehicle_id]
            runtime.plan = selected_plan
            runtime.pickup_route = pickup_route.edges
            runtime.shelter_route = shelter_route.edges
            self._record(
                sim_time,
                "REQUEST_ASSIGNED",
                selected_plan.request.request_id,
                {"vehicle_id": vehicle.vehicle_id},
            )

    def step(self) -> None:
        if self._finished:
            raise RuntimeError("controller is already finished")
        sim_time = self.port.current_time()
        self._apply_due_closures(sim_time)
        for vehicle in self.vehicles.values():
            self._advance_vehicle(vehicle, sim_time)
        if sim_time % int(self.parameters["operation"]["dispatch_interval_sec"]) == 0:
            self._dispatch(sim_time)

    def finish(self) -> dict[str, int]:
        if self._finished:
            raise RuntimeError("controller is already finished")
        sim_time = self.port.current_time()
        for plan in self.plans.values():
            if plan.request.status in {
                RequestStatus.WAITING,
                RequestStatus.ASSIGNED,
                RequestStatus.ONBOARD,
            }:
                self._mark_plan_stranded(plan, sim_time, "SIMULATION_TIMEOUT")
        self._finished = True
        return {
            "evacuated": sum(
                person.status is EvacueeStatus.EVACUATED
                for person in self.evacuees.values()
            ),
            "stranded": sum(
                person.status is EvacueeStatus.STRANDED
                for person in self.evacuees.values()
            ),
            "active": sum(
                person.status
                not in {EvacueeStatus.EVACUATED, EvacueeStatus.STRANDED}
                for person in self.evacuees.values()
            ),
        }
