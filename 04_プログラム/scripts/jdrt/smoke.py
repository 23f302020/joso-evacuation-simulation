"""Run the Joso-only, one-vehicle, no-closure JDRT technical smoke."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree as ET

from .controller import JDRTController, RouteEstimate, SumoTraCIPort
from .dispatch import WaitingVulnerabilityDispatcher
from .domain import DRTVehicle, RequestStatus, VehicleStatus
from .input_adapter import (
    DRTRequestPlan,
    JDRTInputBundle,
    TrueClosureTimeline,
    load_joso_input_bundle,
)
from .run_records import JDRTEvent, RunRecorder
from .validation import validate_final_state_conservation
from .workspace import JDRTWorkspace


RouteFinder = Callable[[str, str, str], RouteEstimate | None]


def resolve_sumo_binary(explicit: str | None = None) -> Path:
    """Resolve SUMO without assuming that it is on PATH."""

    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    path_match = shutil.which("sumo") or shutil.which("sumo.exe")
    if path_match:
        candidates.append(Path(path_match))
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        candidates.extend(
            [Path(sumo_home) / "bin" / "sumo.exe", Path(sumo_home) / "bin" / "sumo"]
        )
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.extend(
            sorted(
                Path(local_app_data).glob(
                    "Programs/sumo-*/PFiles/Eclipse/Sumo/bin/sumo.exe"
                ),
                reverse=True,
            )
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("SUMO binary was not found; pass --sumo-binary")


def load_traci(sumo_binary: Path):
    try:
        import traci  # type: ignore

        return traci
    except ImportError:
        tools_dir = sumo_binary.parent.parent / "tools"
        if not tools_dir.is_dir():
            raise RuntimeError(f"SUMO tools directory was not found: {tools_dir}")
        sys.path.insert(0, str(tools_dir))
        import traci  # type: ignore

        return traci


def select_smoke_plans(
    bundle: JDRTInputBundle,
    vehicle: DRTVehicle,
    route_finder: RouteFinder,
    request_count: int = 10,
    *,
    origin_closure_time_sec: int | None = None,
) -> tuple[DRTRequestPlan, ...]:
    """Select one-shelter requests reachable before and after the first trip."""

    if request_count <= 0:
        raise ValueError("request_count must be positive")
    vehicle_type = "bus_welfare" if vehicle.capacity == 4 else "bus_standard"
    selected: list[DRTRequestPlan] = []
    shelter_edge: str | None = None
    for plan in bundle.request_plans:
        if plan.request.party_size > vehicle.capacity:
            continue
        if origin_closure_time_sec is not None and (
            bundle.true_closures.closure_time_by_edge.get(plan.request.origin_edge)
            != origin_closure_time_sec
        ):
            continue
        if shelter_edge is not None and plan.shelter_edge != shelter_edge:
            continue
        initial_pickup = route_finder(
            vehicle.current_edge, plan.request.origin_edge, vehicle_type
        )
        pickup_to_shelter = route_finder(
            plan.request.origin_edge, plan.shelter_edge, vehicle_type
        )
        later_pickup = route_finder(
            plan.shelter_edge, plan.request.origin_edge, vehicle_type
        )
        if initial_pickup is None or pickup_to_shelter is None or later_pickup is None:
            continue
        shelter_edge = plan.shelter_edge
        selected.append(plan)
        if len(selected) == request_count:
            return tuple(selected)
    raise RuntimeError(
        f"only {len(selected)} reachable requests found; required {request_count}"
    )


def build_smoke_bundle(
    source: JDRTInputBundle,
    vehicle: DRTVehicle,
    plans: tuple[DRTRequestPlan, ...],
    *,
    include_true_closures: bool = False,
) -> JDRTInputBundle:
    """Copy only the selected technical-smoke entities into an isolated bundle."""

    selected_person_ids = {
        person_id for plan in plans for person_id in plan.request.person_ids
    }
    evacuees = tuple(
        copy.deepcopy(person)
        for person in source.evacuees
        if person.person_id in selected_person_ids
    )
    copied_plans = tuple(copy.deepcopy(plan) for plan in plans)
    selected_shelter_ids = {plan.shelter_id for plan in plans}
    shelters = tuple(
        shelter
        for shelter in source.shelters
        if shelter.shelter_id in selected_shelter_ids
    )
    return JDRTInputBundle(
        city_code=source.city_code,
        evacuees=evacuees,
        request_plans=copied_plans,
        vehicles=(copy.deepcopy(vehicle),),
        shelters=shelters,
        private_vehicles=(),
        true_closures=(
            source.true_closures
            if include_true_closures
            else TrueClosureTimeline({}, 0)
        ),
        parameters=source.parameters,
        input_sha256_by_role=source.input_sha256_by_role,
    )


def _relative_xml_path(path: Path, base_dir: Path) -> str:
    return Path(os.path.relpath(path, base_dir)).as_posix()


def _write_sumocfg(
    path: Path,
    network_path: Path,
    vtypes_path: Path,
    end_sec: int,
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
        "additional-files",
        {"value": _relative_xml_path(vtypes_path, path.parent)},
    )
    time_element = ET.SubElement(root, "time")
    ET.SubElement(time_element, "begin", {"value": "0"})
    ET.SubElement(time_element, "end", {"value": str(end_sec)})
    processing = ET.SubElement(root, "processing")
    ET.SubElement(processing, "ignore-route-errors", {"value": "false"})
    ET.SubElement(processing, "time-to-teleport", {"value": "-1"})
    output = ET.SubElement(root, "output")
    ET.SubElement(output, "tripinfo-output", {"value": "tripinfo.xml"})
    report = ET.SubElement(root, "report")
    ET.SubElement(report, "no-step-log", {"value": "true"})
    ET.SubElement(report, "duration-log.disable", {"value": "true"})
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def run_no_closure_smoke(
    project_root: Path,
    *,
    run_id: str,
    request_count: int = 10,
    seed: int = 23423,
    sumo_binary: str | None = None,
    apply_true_closures: bool = False,
) -> Path:
    """Execute SMK1 or SMK2 and return its finalized manifest path."""

    root = project_root.resolve()
    program_dir = root / "04_プログラム"
    workspace = JDRTWorkspace(program_dir)
    workspace.ensure_output_dirs()
    parameters_path = program_dir / "config" / "jdrt_parameters_v1.json"
    source = load_joso_input_bundle(root)
    recorder = RunRecorder(
        workspace,
        run_id,
        "JDRT-B3-SMK2" if apply_true_closures else "JDRT-B3-SMK1",
        seed,
        parameters_path,
        source.input_sha256_by_role,
    )
    run_dir = recorder.run_dir
    network_path = workspace.network_dir / "08211.net.xml"
    vtypes_path = workspace.scenarios_dir / "bus_vtypes.add.xml"
    end_sec = int(source.parameters["simulation_end_sec"])
    sumocfg_path = run_dir / "smoke.sumocfg"
    _write_sumocfg(sumocfg_path, network_path, vtypes_path, end_sec)

    binary = resolve_sumo_binary(sumo_binary)
    traci = load_traci(binary)
    controller: JDRTController | None = None
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
            ],
        )
        traci_started = True
        port = SumoTraCIPort(traci, {})
        vehicle = next(item for item in source.vehicles if item.capacity == 8)
        first_closure_time = (
            min(source.true_closures.closure_time_by_edge.values())
            if apply_true_closures
            else None
        )
        plans = select_smoke_plans(
            source,
            vehicle,
            port.find_route,
            request_count,
            origin_closure_time_sec=first_closure_time,
        )
        smoke_bundle = build_smoke_bundle(
            source,
            vehicle,
            plans,
            include_true_closures=apply_true_closures,
        )
        selection = {
            "purpose": "technical_smoke_not_research_result",
            "closure_enabled": apply_true_closures,
            "private_vehicle_count": 0,
            "vehicle": {
                "vehicle_id": vehicle.vehicle_id,
                "capacity": vehicle.capacity,
                "initial_edge": vehicle.current_edge,
            },
            "requests": [
                {
                    "request_id": plan.request.request_id,
                    "person_ids": list(plan.request.person_ids),
                    "origin_edge": plan.request.origin_edge,
                    "shelter_id": plan.shelter_id,
                    "shelter_edge": plan.shelter_edge,
                }
                for plan in plans
            ],
        }
        (run_dir / "selected_requests.json").write_text(
            json.dumps(selection, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        recorder.append(
            JDRTEvent(
                0,
                "SMOKE_INPUT_SELECTED",
                run_id,
                {
                    "request_count": len(plans),
                    "person_count": len(smoke_bundle.evacuees),
                },
            )
        )

        vehicle_type = "bus_standard"
        initial_route = port.find_route(
            vehicle.current_edge, plans[0].request.origin_edge, vehicle_type
        )
        if initial_route is None:
            raise RuntimeError("initial smoke route disappeared after selection")
        route_id = f"{run_id}_initial"
        traci.route.add(route_id, list(initial_route.edges))
        traci.vehicle.add(
            vehicle.vehicle_id,
            route_id,
            typeID=vehicle_type,
            depart="0",
            departLane="best",
            departPos="base",
        )
        traci.vehicle.setStop(
            vehicle.vehicle_id,
            vehicle.current_edge,
            duration=float(end_sec + 1),
        )

        weights = source.parameters["dispatchers"]["weights"]
        controller = JDRTController(
            smoke_bundle,
            port,
            WaitingVulnerabilityDispatcher(
                waiting_weight=float(weights["waiting"]),
                vulnerability_weight=float(weights["vulnerability"]),
                pickup_weight=float(weights["pickup"]),
            ),
            "JDRT-B3-SMK2" if apply_true_closures else "JDRT-B3-SMK1",
            recorder=recorder,
        )
        while int(traci.simulation.getTime()) < end_sec:
            traci.simulationStep()
            controller.step()
            terminal = all(
                plan.request.status
                in {RequestStatus.COMPLETED, RequestStatus.STRANDED}
                for plan in smoke_bundle.request_plans
            )
            if terminal and smoke_bundle.vehicles[0].status is VehicleStatus.IDLE:
                break

        controller_summary = controller.finish()
        conservation = validate_final_state_conservation(
            smoke_bundle.evacuees, len(smoke_bundle.evacuees)
        )
        event_rows = [
            json.loads(line)
            for line in recorder.events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        stranded_reasons: dict[str, int] = {}
        for row in event_rows:
            if row["event_type"] != "REQUEST_STRANDED":
                continue
            reason = str(row.get("details", {}).get("reason", "UNKNOWN"))
            stranded_reasons[reason] = stranded_reasons.get(reason, 0) + 1
        closure_reason_count = sum(
            count
            for reason, count in stranded_reasons.items()
            if reason != "SIMULATION_TIMEOUT"
        )
        all_terminal = controller_summary["active"] == 0 and all(
            plan.request.status
            in {RequestStatus.COMPLETED, RequestStatus.STRANDED}
            for plan in smoke_bundle.request_plans
        )
        if apply_true_closures:
            success = (
                all_terminal
                and bool(controller.applied_closed_edges)
                and closure_reason_count > 0
            )
        else:
            success = (
                all_terminal
                and controller_summary["evacuated"] == len(smoke_bundle.evacuees)
                and controller_summary["stranded"] == 0
            )
        summary = {
            "purpose": "technical_smoke_not_research_result",
            "sumo_binary": str(binary),
            "simulation_end_time_sec": int(traci.simulation.getTime()),
            "request_count": len(smoke_bundle.request_plans),
            "person_count": len(smoke_bundle.evacuees),
            "vehicle_count": 1,
            "private_vehicle_count": 0,
            "closure_enabled": apply_true_closures,
            "applied_closed_edge_count": len(controller.applied_closed_edges),
            "stranded_reasons": dict(sorted(stranded_reasons.items())),
            "closure_reason_count": closure_reason_count,
            "controller": controller_summary,
            "conservation": conservation,
            "all_requests_completed": success,
        }
        manifest = recorder.finalize("COMPLETED" if success else "INVALID", summary)
        finalized = True
        return manifest
    except Exception as error:
        if not finalized:
            recorder.finalize(
                "FAILED",
                {
                    "purpose": "technical_smoke_not_research_result",
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
    parser.add_argument(
        "--run-id",
        default=f"smk1_no_closure_{datetime.now().strftime('%Y%m%dT%H%M%S')}",
    )
    parser.add_argument("--request-count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=23423)
    parser.add_argument("--sumo-binary")
    parser.add_argument("--with-closures", action="store_true")
    args = parser.parse_args()
    manifest = run_no_closure_smoke(
        args.project_root,
        run_id=args.run_id,
        request_count=args.request_count,
        seed=args.seed,
        sumo_binary=args.sumo_binary,
        apply_true_closures=args.with_closures,
    )
    print(manifest)


if __name__ == "__main__":
    main()
