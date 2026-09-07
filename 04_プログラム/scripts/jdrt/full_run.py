"""One-cell-at-a-time runner for the Joso City JDRT core experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.etree import ElementTree as ET

from .controller import JDRTController, RouteEstimate, SumoTraCIPort, build_temporal_forecast
from .dispatch import (
    DynamicTravelTimeDispatcher,
    FloodRiskAwareDispatcher,
    WaitingVulnerabilityDispatcher,
)
from .domain import DRTVehicle, EvacueeStatus, RequestStatus, VehicleStatus
from .input_adapter import JDRTInputBundle, load_joso_input_bundle
from .run_records import JDRTEvent, RunRecorder
from .smoke import load_traci, resolve_sumo_binary
from .static_routing import StaticTravelTimeLowerBounds
from .validation import validate_final_state_conservation, validate_vehicle_capacity
from .workspace import JDRTWorkspace


CORE_SCENARIOS = ("JDRT-B2", "JDRT-B3", "JDRT-P1", "JDRT-P2-L15")
PROTOCOL_PARAMETER_FILES = {
    "v1": Path("04_プログラム/config/jdrt_parameters_v1.json"),
    "v2": Path("04_プログラム/config/jdrt_parameters_v2.json"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_sumo_error_log(path: Path) -> dict[str, int]:
    """Separate SUMO warnings from actual Error lines for the PAP gate."""

    warnings = 0
    errors = 0
    handled_route_rejections = 0
    collision_teleports = 0
    gridlock_teleports = 0
    if path.is_file():
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line.startswith("Warning:"):
                    warnings += 1
                    lowered = line.lower()
                    if line.startswith("Warning: Teleporting vehicle"):
                        if "collision" in lowered:
                            collision_teleports += 1
                        elif "waited too long" in lowered:
                            gridlock_teleports += 1
                elif line.startswith("Error:"):
                    errors += 1
                    if "Route replacement failed for vehicle 'bus_" in line:
                        handled_route_rejections += 1
    return {
        "bytes": path.stat().st_size if path.is_file() else 0,
        "warning_count": warnings,
        "error_count": errors,
        "handled_route_rejection_count": handled_route_rejections,
        "unhandled_error_count": errors - handled_route_rejections,
        "collision_teleport_count": collision_teleports,
        "gridlock_teleport_count": gridlock_teleports,
    }


def finalize_interrupted_run(
    project_root: Path,
    run_id: str,
    reason: str,
) -> Path:
    """Convert only an orphaned RUNNING manifest into an auditable FAILED run."""

    workspace = JDRTWorkspace(project_root.resolve() / "04_プログラム")
    run_dir = workspace.run_dir(run_id)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "RUNNING":
        raise ValueError("only a RUNNING manifest can be finalized as interrupted")
    events_path = run_dir / str(manifest.get("event_log", "events.jsonl"))
    event_count = 0
    if events_path.is_file():
        with events_path.open(encoding="utf-8") as handle:
            event_count = sum(1 for line in handle if line.strip())
    manifest["status"] = "FAILED"
    manifest["event_count"] = event_count
    manifest["event_log_sha256"] = (
        _sha256(events_path) if events_path.is_file() else None
    )
    manifest["summary"] = {
        "purpose": "core_experiment",
        "error_type": "ExternalInterruption",
        "error": reason,
        "recovered_from_orphaned_running_manifest": True,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _relative_xml_path(path: Path, base_dir: Path) -> str:
    return Path(os.path.relpath(path, base_dir)).as_posix()


def _scenario_slug(scenario_id: str) -> str:
    return scenario_id.lower().replace("jdrt-", "").replace("-", "_")


def build_dispatcher(
    scenario_id: str,
    bundle: JDRTInputBundle,
) -> tuple[object, Mapping[str, int] | None]:
    """Build only the four dispatch conditions fixed in the JDRT PAP."""

    if scenario_id not in CORE_SCENARIOS:
        raise ValueError(f"unsupported core scenario: {scenario_id}")
    weights = bundle.parameters["dispatchers"]["weights"]
    if scenario_id == "JDRT-B2":
        return DynamicTravelTimeDispatcher(), None
    if scenario_id == "JDRT-B3":
        return (
            WaitingVulnerabilityDispatcher(
                waiting_weight=float(weights["waiting"]),
                vulnerability_weight=float(weights["vulnerability"]),
                pickup_weight=float(weights["pickup"]),
            ),
            None,
        )
    error_sec = (
        int(bundle.parameters["forecast"]["perfect_error_sec"])
        if scenario_id == "JDRT-P1"
        else int(bundle.parameters["forecast"]["primary_temporal_error_sec"])
    )
    return (
        FloodRiskAwareDispatcher(
            waiting_weight=float(weights["waiting"]),
            flood_weight=float(weights["flood"]),
            vulnerability_weight=float(weights["vulnerability"]),
            pickup_weight=float(weights["pickup"]),
            safety_margin_sec=float(
                bundle.parameters["operation"]["safety_margin_sec"]
            ),
        ),
        build_temporal_forecast(bundle.true_closures, error_sec),
    )


def _parameter_path(project_root: Path, protocol_version: str) -> Path:
    try:
        relative_path = PROTOCOL_PARAMETER_FILES[protocol_version]
    except KeyError as error:
        raise ValueError(
            f"protocol_version must be one of {tuple(PROTOCOL_PARAMETER_FILES)}"
        ) from error
    path = (project_root.resolve() / relative_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _simulation_settings(parameters: Mapping[str, Any]) -> dict[str, float | str]:
    simulation = parameters.get("simulation", {})
    step_length_sec = float(simulation.get("step_length_sec", 1.0))
    controller_step_interval_sec = float(
        simulation.get("controller_step_interval_sec", 1.0)
    )
    collision_action = str(simulation.get("collision_action", "teleport"))
    time_to_teleport_sec = float(simulation.get("time_to_teleport_sec", -1))
    if step_length_sec <= 0:
        raise ValueError("simulation step_length_sec must be positive")
    if controller_step_interval_sec != 1.0:
        raise ValueError("controller_step_interval_sec must remain 1.0")
    steps_per_controller = controller_step_interval_sec / step_length_sec
    if not math.isclose(steps_per_controller, round(steps_per_controller)):
        raise ValueError("step_length_sec must divide controller_step_interval_sec")
    if collision_action != "teleport":
        raise ValueError("collision_action must remain teleport for the PAP gate")
    return {
        "step_length_sec": step_length_sec,
        "controller_step_interval_sec": controller_step_interval_sec,
        "collision_action": collision_action,
        "time_to_teleport_sec": time_to_teleport_sec,
    }


def _completed_core_cells(
    workspace: JDRTWorkspace,
    parameter_sha256: str,
) -> set[tuple[str, int]]:
    completed: set[tuple[str, int]] = set()
    for run_dir in workspace.iter_run_dirs():
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            manifest.get("status") == "COMPLETED"
            and manifest.get("scenario_id") in CORE_SCENARIOS
            and manifest.get("parameter_sha256") == parameter_sha256
            and manifest.get("summary", {}).get("purpose") == "core_experiment"
        ):
            completed.add((str(manifest["scenario_id"]), int(manifest["seed"])))
    return completed


def preflight_full_run(
    project_root: Path,
    scenario_id: str,
    seed: int,
    *,
    sumo_binary: str | None = None,
    protocol_version: str = "v1",
) -> dict[str, Any]:
    """Verify one core cell without creating a run directory."""

    root = project_root.resolve()
    parameters_path = _parameter_path(root, protocol_version)
    parameter_sha256 = _sha256(parameters_path)
    bundle = load_joso_input_bundle(root, parameters_path=parameters_path)
    simulation = _simulation_settings(bundle.parameters)
    paired_seeds = tuple(int(value) for value in bundle.parameters["experiment"]["paired_seeds"])
    if scenario_id not in CORE_SCENARIOS:
        raise ValueError(f"scenario must be one of {CORE_SCENARIOS}")
    if seed not in paired_seeds:
        raise ValueError(f"seed must be one of {paired_seeds}")
    workspace = JDRTWorkspace(root / "04_プログラム")
    if (scenario_id, seed) in _completed_core_cells(workspace, parameter_sha256):
        raise RuntimeError(f"completed core cell already exists: {scenario_id} seed {seed}")
    binary = resolve_sumo_binary(sumo_binary)
    version = subprocess.run(
        [str(binary), "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.splitlines()[0]
    dispatcher, predicted = build_dispatcher(scenario_id, bundle)
    return {
        "status": "READY",
        "protocol_version": protocol_version,
        "parameter_version": bundle.parameters["parameter_version"],
        "parameter_sha256": parameter_sha256,
        "city_code": bundle.city_code,
        "scenario_id": scenario_id,
        "seed": seed,
        "sumo_binary": str(binary),
        "sumo_version": version,
        "dispatcher": type(dispatcher).__name__,
        "predicted_closure_count": len(predicted or {}),
        "person_count": len(bundle.evacuees),
        "request_count": len(bundle.request_plans),
        "drt_vehicle_count": len(bundle.vehicles),
        "private_vehicle_count": len(bundle.private_vehicles),
        "input_sha_count": len(bundle.input_sha256_by_role),
        **simulation,
    }


def write_private_vehicle_route(path: Path, bundle: JDRTInputBundle) -> str:
    """Write exactly the 8,164 private trips, excluding rescue substitution trips."""

    root = ET.Element("routes")
    ET.SubElement(
        root,
        "vType",
        {
            "id": "passenger_car",
            "vClass": "passenger",
            "accel": "2.6",
            "decel": "4.5",
            "sigma": "0.5",
            "length": "5.0",
            "maxSpeed": "13.89",
        },
    )
    for item in bundle.private_vehicles:
        ET.SubElement(
            root,
            "trip",
            {
                "id": item.vehicle_id,
                "type": "passenger_car",
                "depart": str(item.depart_sec),
                "from": item.from_edge,
                "to": item.to_edge,
            },
        )
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return _sha256(path)


def write_initial_bus_route(
    path: Path,
    bundle: JDRTInputBundle,
    network_path: Path,
    end_sec: int,
) -> str:
    """Write the fixed fleet before private traffic so every bus starts available."""

    network_root = ET.parse(network_path).getroot()
    edge_by_id = {
        edge.attrib["id"]: edge
        for edge in network_root.findall("edge")
        if "id" in edge.attrib
    }
    root = ET.Element("routes")
    for vehicle in bundle.vehicles:
        edge = edge_by_id[vehicle.current_edge]
        lanes = [
            lane
            for lane in edge.findall("lane")
            if "bus" not in set(lane.attrib.get("disallow", "").split())
            and (
                not lane.attrib.get("allow")
                or "bus" in set(lane.attrib["allow"].split())
            )
        ]
        if not lanes:
            raise ValueError(f"no bus lane on initial edge: {vehicle.current_edge}")
        lane = lanes[0]
        vehicle_type = "bus_welfare" if vehicle.capacity == 4 else "bus_standard"
        vehicle_element = ET.SubElement(
            root,
            "vehicle",
            {
                "id": vehicle.vehicle_id,
                "type": vehicle_type,
                "depart": "0",
                "departLane": lane.attrib["index"],
                "departPos": "base",
            },
        )
        ET.SubElement(vehicle_element, "route", {"edges": vehicle.current_edge})
        ET.SubElement(
            vehicle_element,
            "stop",
            {
                "lane": lane.attrib["id"],
                "endPos": str(min(float(lane.attrib["length"]) - 1.0, 20.0)),
                "duration": str(end_sec + 1),
                "parking": "false",
            },
        )
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return _sha256(path)


def _write_sumocfg(
    path: Path,
    network_path: Path,
    initial_bus_route_path: Path,
    private_route_path: Path,
    bus_vtypes_path: Path,
    end_sec: int,
    *,
    step_length_sec: float = 1.0,
    collision_action: str = "teleport",
    time_to_teleport_sec: float = -1,
) -> None:
    root = ET.Element("configuration")
    input_element = ET.SubElement(root, "input")
    ET.SubElement(
        input_element,
        "net-file",
        {"value": _relative_xml_path(network_path, path.parent)},
    )
    ET.SubElement(
        input_element,
        "route-files",
        {
            "value": ",".join(
                (
                    _relative_xml_path(initial_bus_route_path, path.parent),
                    _relative_xml_path(private_route_path, path.parent),
                )
            )
        },
    )
    ET.SubElement(
        input_element,
        "additional-files",
        {"value": _relative_xml_path(bus_vtypes_path, path.parent)},
    )
    time_element = ET.SubElement(root, "time")
    ET.SubElement(time_element, "begin", {"value": "0"})
    ET.SubElement(time_element, "end", {"value": str(end_sec)})
    ET.SubElement(time_element, "step-length", {"value": f"{step_length_sec:g}"})
    processing = ET.SubElement(root, "processing")
    ET.SubElement(processing, "ignore-route-errors", {"value": "false"})
    ET.SubElement(
        processing,
        "time-to-teleport",
        {"value": f"{time_to_teleport_sec:g}"},
    )
    ET.SubElement(processing, "collision.action", {"value": collision_action})
    output = ET.SubElement(root, "output")
    ET.SubElement(output, "tripinfo-output", {"value": "tripinfo.xml"})
    report = ET.SubElement(root, "report")
    ET.SubElement(report, "no-step-log", {"value": "true"})
    ET.SubElement(report, "duration-log.disable", {"value": "true"})
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


class FullRunTraCIPort(SumoTraCIPort):
    """TraCI adapter with private-traffic and technical-gate accounting."""

    def __init__(
        self,
        traci_module: object,
        bundle: JDRTInputBundle,
    ) -> None:
        super().__init__(
            traci_module,
            {
                vehicle.vehicle_id: (
                    "bus_welfare" if vehicle.capacity == 4 else "bus_standard"
                )
                for vehicle in bundle.vehicles
            },
        )
        self._traci = traci_module
        self.drt_vehicle_ids = {vehicle.vehicle_id for vehicle in bundle.vehicles}
        self.private_by_id = {item.vehicle_id: item for item in bundle.private_vehicles}
        self.private_by_source: dict[str, list[str]] = {}
        for item in bundle.private_vehicles:
            self.private_by_source.setdefault(item.from_edge, []).append(item.vehicle_id)
        self.departed_private_ids: set[str] = set()
        self.arrived_private_ids: set[str] = set()
        self.blocked_before_depart: dict[str, int] = {}
        self.reroute_failed_ids: set[str] = set()
        self.teleport_ids: set[str] = set()
        self.closure_rows: list[dict[str, int]] = []
        self.congestion_rows: list[dict[str, float | int]] = []
        self.last_distance_by_bus: dict[str, float] = {}
        self.bus_distance: dict[str, dict[str, float]] = {
            vehicle_id: {"total_m": 0.0, "empty_m": 0.0, "occupied_m": 0.0}
            for vehicle_id in self.drt_vehicle_ids
        }
        self.bus_status_by_id: dict[str, VehicleStatus] = {}
        self.observation_count = 0

    def observe_step(self, sim_time: float, vehicles: Mapping[str, DRTVehicle]) -> None:
        self.observation_count += 1
        for vehicle_id in self._traci.simulation.getDepartedIDList():
            if vehicle_id in self.private_by_id:
                self.departed_private_ids.add(vehicle_id)
        for vehicle_id in self._traci.simulation.getArrivedIDList():
            if vehicle_id in self.private_by_id:
                self.arrived_private_ids.add(vehicle_id)
        self.teleport_ids.update(self._traci.simulation.getStartingTeleportIDList())
        self.teleport_ids.update(self._traci.simulation.getEndingTeleportIDList())
        active_ids = set(self._traci.vehicle.getIDList())
        for vehicle_id, vehicle in vehicles.items():
            if vehicle_id not in active_ids:
                continue
            distance = float(self._traci.vehicle.getDistance(vehicle_id))
            previous = self.last_distance_by_bus.get(vehicle_id, distance)
            delta = max(0.0, distance - previous)
            previous_status = self.bus_status_by_id.get(vehicle_id, vehicle.status)
            self.bus_distance[vehicle_id]["total_m"] += delta
            if previous_status is VehicleStatus.TO_SHELTER:
                self.bus_distance[vehicle_id]["occupied_m"] += delta
            elif previous_status is VehicleStatus.TO_PICKUP:
                self.bus_distance[vehicle_id]["empty_m"] += delta
            self.last_distance_by_bus[vehicle_id] = distance
            self.bus_status_by_id[vehicle_id] = vehicle.status
        if math.isclose(sim_time % 60, 0.0, abs_tol=1e-9):
            sampled_time = int(round(sim_time))
            speeds = [
                float(self._traci.vehicle.getSpeed(vehicle_id))
                for vehicle_id in active_ids
            ]
            self.congestion_rows.append(
                {
                    "sim_time_sec": sampled_time,
                    "active_vehicle_count": len(active_ids),
                    "mean_speed_mps": (
                        round(sum(speeds) / len(speeds), 6) if speeds else 0.0
                    ),
                    "halting_vehicle_count": sum(speed <= 0.1 for speed in speeds),
                }
            )

    def apply_closures(self, edge_ids: Sequence[str]) -> None:
        super().apply_closures(edge_ids)
        sim_time = self.current_time()
        blocked = 0
        for edge_id in edge_ids:
            for vehicle_id in self.private_by_source.get(edge_id, ()):
                if (
                    vehicle_id not in self.departed_private_ids
                    and vehicle_id not in self.blocked_before_depart
                ):
                    self.blocked_before_depart[vehicle_id] = sim_time
                    blocked += 1
                    try:
                        self._traci.vehicle.remove(vehicle_id)
                    except self._traci.TraCIException:
                        pass
        rerouted = 0
        failed = 0
        for vehicle_id in tuple(self._traci.vehicle.getIDList()):
            if vehicle_id in self.drt_vehicle_ids:
                continue
            try:
                self._traci.vehicle.rerouteTraveltime(vehicle_id)
                rerouted += 1
            except self._traci.TraCIException:
                failed += 1
                self.reroute_failed_ids.add(vehicle_id)
        self.closure_rows.append(
            {
                "sim_time_sec": sim_time,
                "new_closed_edge_count": len(edge_ids),
                "private_reroute_success_count": rerouted,
                "private_reroute_failed_count": failed,
                "private_blocked_before_depart_count": blocked,
            }
        )

    def remove_vehicle(self, vehicle_id: str) -> None:
        if self.vehicle_exists(vehicle_id):
            try:
                distance = float(self._traci.vehicle.getDistance(vehicle_id))
                previous = self.last_distance_by_bus.get(vehicle_id, distance)
                self.bus_distance[vehicle_id]["total_m"] += max(0.0, distance - previous)
            except self._traci.TraCIException:
                pass
        super().remove_vehicle(vehicle_id)


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _nearest_rank_p95(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def build_result_rows(
    bundle: JDRTInputBundle,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    people = [
        {
            "person_id": person.person_id,
            "origin_id": person.origin_id,
            "person_type": person.person_type,
            "vulnerability_score": person.vulnerability_score,
            "status": person.status.value,
            "request_time_sec": person.request_time,
            "pickup_time_sec": person.pickup_time,
            "arrival_time_sec": person.arrival_time,
        }
        for person in bundle.evacuees
    ]
    person_by_id = {person.person_id: person for person in bundle.evacuees}
    requests: list[dict[str, Any]] = []
    for plan in bundle.request_plans:
        members = [person_by_id[person_id] for person_id in plan.request.person_ids]
        pickup_times = [person.pickup_time for person in members if person.pickup_time is not None]
        arrival_times = [person.arrival_time for person in members if person.arrival_time is not None]
        requests.append(
            {
                "request_id": plan.request.request_id,
                "origin_edge": plan.request.origin_edge,
                "shelter_id": plan.shelter_id,
                "shelter_edge": plan.shelter_edge,
                "party_size": plan.request.party_size,
                "vulnerability": plan.request.vulnerability,
                "status": plan.request.status.value,
                "assigned_vehicle_id": plan.request.assigned_vehicle_id or "",
                "request_time_sec": plan.request.request_time,
                "pickup_time_sec": min(pickup_times) if pickup_times else "",
                "arrival_time_sec": min(arrival_times) if arrival_times else "",
            }
        )
    type_counts = Counter(person.person_type for person in bundle.evacuees)
    evacuated_counts = Counter(
        person.person_type
        for person in bundle.evacuees
        if person.status is EvacueeStatus.EVACUATED
    )
    arrival_times = [
        int(person.arrival_time)
        for person in bundle.evacuees
        if person.status is EvacueeStatus.EVACUATED and person.arrival_time is not None
    ]
    metrics = {
        "type4_denominator": type_counts[4],
        "type4_evacuated": evacuated_counts[4],
        "type4_success_rate": (
            evacuated_counts[4] / type_counts[4] if type_counts[4] else None
        ),
        "type3_denominator": type_counts[3],
        "type3_evacuated": evacuated_counts[3],
        "type3_success_rate": (
            evacuated_counts[3] / type_counts[3] if type_counts[3] else None
        ),
        "all_drt_denominator": len(bundle.evacuees),
        "all_drt_evacuated": sum(evacuated_counts.values()),
        "all_drt_success_rate": sum(evacuated_counts.values()) / len(bundle.evacuees),
        "arrival_time_p95_sec_nearest_rank": _nearest_rank_p95(arrival_times),
        "request_status_counts": dict(
            sorted(Counter(row["status"] for row in requests).items())
        ),
    }
    return people, requests, metrics


def run_full_experiment(
    project_root: Path,
    scenario_id: str,
    seed: int,
    *,
    run_id: str,
    sumo_binary: str | None = None,
    protocol_version: str = "v1",
) -> Path:
    """Run one PAP cell, validate it, and return the immutable manifest."""

    preflight = preflight_full_run(
        project_root,
        scenario_id,
        seed,
        sumo_binary=sumo_binary,
        protocol_version=protocol_version,
    )
    root = project_root.resolve()
    program_dir = root / "04_プログラム"
    workspace = JDRTWorkspace(program_dir)
    workspace.ensure_output_dirs()
    parameters_path = _parameter_path(root, protocol_version)
    bundle = load_joso_input_bundle(root, parameters_path=parameters_path)
    simulation = _simulation_settings(bundle.parameters)
    recorder = RunRecorder(
        workspace,
        run_id,
        scenario_id,
        seed,
        parameters_path,
        bundle.input_sha256_by_role,
    )
    run_dir = recorder.run_dir
    private_route_path = run_dir / "private_cars.rou.xml"
    private_route_sha = write_private_vehicle_route(private_route_path, bundle)
    end_sec = int(bundle.parameters["simulation_end_sec"])
    initial_bus_route_path = run_dir / "initial_buses.rou.xml"
    initial_bus_route_sha = write_initial_bus_route(
        initial_bus_route_path,
        bundle,
        workspace.network_dir / "08211.net.xml",
        end_sec,
    )
    sumocfg_path = run_dir / "jdrt.sumocfg"
    _write_sumocfg(
        sumocfg_path,
        workspace.network_dir / "08211.net.xml",
        initial_bus_route_path,
        private_route_path,
        workspace.scenarios_dir / "bus_vtypes.add.xml",
        end_sec,
        step_length_sec=float(simulation["step_length_sec"]),
        collision_action=str(simulation["collision_action"]),
        time_to_teleport_sec=float(simulation["time_to_teleport_sec"]),
    )
    binary = Path(preflight["sumo_binary"])
    traci = load_traci(binary)
    dispatcher, predicted = build_dispatcher(scenario_id, bundle)
    controller: JDRTController | None = None
    port: FullRunTraCIPort | None = None
    traci_started = False
    finalized = False
    try:
        traci.start(
            [
                str(binary),
                "-c",
                str(sumocfg_path),
                "--seed",
                str(seed),
                "--no-step-log",
                "true",
                "--log",
                str(run_dir / "sumo.log"),
                "--error-log",
                str(run_dir / "sumo_error.log"),
            ]
        )
        traci_started = True
        port = FullRunTraCIPort(traci, bundle)
        controller = JDRTController(
            bundle,
            port,
            dispatcher,
            scenario_id,
            predicted_closure_time_by_edge=predicted,
            recorder=recorder,
            service_time_lower_bound=StaticTravelTimeLowerBounds(
                workspace.network_dir / "08211.net.xml",
                boarding_time_sec=float(
                    bundle.parameters["fleet"]["boarding_time_sec"]
                ),
            ),
        )
        recorder.append(
            JDRTEvent(
                0,
                "CORE_RUN_STARTED",
                run_id,
                {
                    "scenario_id": scenario_id,
                    "seed": seed,
                    "protocol_version": protocol_version,
                    "parameter_version": bundle.parameters["parameter_version"],
                    "private_route_sha256": private_route_sha,
                    "initial_bus_route_sha256": initial_bus_route_sha,
                },
            )
        )
        controller_step_count = 0
        next_controller_time = float(simulation["controller_step_interval_sec"])
        while float(traci.simulation.getTime()) < end_sec:
            traci.simulationStep()
            sim_time = float(traci.simulation.getTime())
            if sim_time + 1e-9 >= next_controller_time:
                if not math.isclose(sim_time, next_controller_time, abs_tol=1e-9):
                    raise RuntimeError(
                        "SUMO step skipped a scheduled controller update: "
                        f"time={sim_time}, due={next_controller_time}"
                    )
                controller.step()
                controller_step_count += 1
                next_controller_time += float(
                    simulation["controller_step_interval_sec"]
                )
            port.observe_step(sim_time, controller.vehicles)
        controller_summary = controller.finish()
        conservation = validate_final_state_conservation(
            bundle.evacuees, len(bundle.evacuees)
        )
        validate_vehicle_capacity(bundle.vehicles)

        people, requests, metrics = build_result_rows(bundle)
        people_path = run_dir / "person_results.csv"
        requests_path = run_dir / "request_results.csv"
        bus_path = run_dir / "drt_vehicle_metrics.csv"
        congestion_path = run_dir / "congestion.csv"
        closure_path = run_dir / "closures.csv"
        metrics_path = run_dir / "metrics.json"
        _write_csv(people_path, people, list(people[0]))
        _write_csv(requests_path, requests, list(requests[0]))
        bus_rows = [
            {"vehicle_id": vehicle_id, **values}
            for vehicle_id, values in sorted(port.bus_distance.items())
        ]
        _write_csv(bus_path, bus_rows, ["vehicle_id", "total_m", "empty_m", "occupied_m"])
        _write_csv(
            congestion_path,
            port.congestion_rows,
            ["sim_time_sec", "active_vehicle_count", "mean_speed_mps", "halting_vehicle_count"],
        )
        _write_csv(
            closure_path,
            port.closure_rows,
            [
                "sim_time_sec",
                "new_closed_edge_count",
                "private_reroute_success_count",
                "private_reroute_failed_count",
                "private_blocked_before_depart_count",
            ],
        )
        metrics.update(
            {
                "scenario_id": scenario_id,
                "seed": seed,
                "protocol_version": protocol_version,
                "parameter_version": bundle.parameters["parameter_version"],
                "simulation_step_length_sec": simulation["step_length_sec"],
                "controller": controller_summary,
                "conservation": conservation,
                "private_vehicle_count": len(bundle.private_vehicles),
                "private_departed_count": len(port.departed_private_ids),
                "private_arrived_count": len(port.arrived_private_ids),
                "private_blocked_before_depart_count": len(port.blocked_before_depart),
                "private_reroute_failed_count": len(port.reroute_failed_ids),
                "teleport_count": len(port.teleport_ids),
                "final_closed_edge_count": len(controller.applied_closed_edges),
                "drt_total_vkt_km": sum(
                    values["total_m"] for values in port.bus_distance.values()
                )
                / 1000.0,
                "drt_empty_vkt_km": sum(
                    values["empty_m"] for values in port.bus_distance.values()
                )
                / 1000.0,
            }
        )
        if traci_started:
            traci.close()
            traci_started = False
        sumo_log_summary = summarize_sumo_error_log(run_dir / "sumo_error.log")
        metrics["collision_teleport_count"] = sumo_log_summary[
            "collision_teleport_count"
        ]
        metrics_path.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        output_paths = [
            initial_bus_route_path,
            private_route_path,
            sumocfg_path,
            people_path,
            requests_path,
            bus_path,
            congestion_path,
            closure_path,
            metrics_path,
        ]
        output_sha = {path.name: _sha256(path) for path in output_paths}
        valid = (
            conservation["active"] == 0
            and len(people) == len(bundle.evacuees)
            and len(requests) == len(bundle.request_plans)
            and len(bundle.private_vehicles)
            == int(bundle.parameters["traffic_demand"]["private_vehicle_count"])
            and len(bundle.vehicles) == int(bundle.parameters["fleet"]["total"])
            and len(port.teleport_ids) == 0
            and sumo_log_summary["collision_teleport_count"] == 0
            and sumo_log_summary["unhandled_error_count"] == 0
            and controller_step_count
            == round(end_sec / float(simulation["controller_step_interval_sec"]))
            and port.observation_count
            == round(end_sec / float(simulation["step_length_sec"]))
            and metrics["all_drt_evacuated"] > 0
            and metrics["drt_total_vkt_km"] > 0
        )
        summary = {
            "purpose": "core_experiment",
            "preflight": preflight,
            "simulation_end_time_sec": end_sec,
            "protocol_version": protocol_version,
            "parameter_version": bundle.parameters["parameter_version"],
            "simulation": simulation,
            "controller_step_count": controller_step_count,
            "technical_observation_count": port.observation_count,
            "controller": controller_summary,
            "conservation": conservation,
            "metrics": metrics,
            "private_route_sha256": private_route_sha,
            "initial_bus_route_sha256": initial_bus_route_sha,
            "output_sha256_by_file": output_sha,
            "sumo_error_log": sumo_log_summary,
            "valid": valid,
        }
        manifest = recorder.finalize("COMPLETED" if valid else "INVALID", summary)
        finalized = True
        return manifest
    except Exception as error:
        if not finalized:
            recorder.finalize(
                "FAILED",
                {
                    "purpose": "core_experiment",
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )
            finalized = True
        raise
    finally:
        if traci_started:
            traci.close(False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--scenario", required=True, choices=CORE_SCENARIOS)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--sumo-binary")
    parser.add_argument(
        "--protocol-version",
        choices=tuple(PROTOCOL_PARAMETER_FILES),
        default="v1",
    )
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        print(
            json.dumps(
                preflight_full_run(
                    args.project_root,
                    args.scenario,
                    args.seed,
                    sumo_binary=args.sumo_binary,
                    protocol_version=args.protocol_version,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    protocol_prefix = "" if args.protocol_version == "v1" else f"{args.protocol_version}_"
    run_id = args.run_id or (
        f"core_{protocol_prefix}{_scenario_slug(args.scenario)}_seed{args.seed}_"
        f"{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    )
    print(
        run_full_experiment(
            args.project_root,
            args.scenario,
            args.seed,
            run_id=run_id,
            sumo_binary=args.sumo_binary,
            protocol_version=args.protocol_version,
        )
    )


if __name__ == "__main__":
    main()
