"""Prepare and run the PRE-8 approved Scenario C integrated experiment."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from p2_sumo_env import configure_sumo_environment
from scenario_c_car_walk import read_csv_rows, sha256, write_csv
from scenario_c_routes import (
    DEFAULT_A_ASSIGNMENTS,
    private_assignment_templates,
    write_car_trips,
)


PROGRAM_DIR = Path(__file__).resolve().parents[1]
REGION_DIR = PROGRAM_DIR / "output" / "sumo" / "regions" / "08211"
SCENARIO_C_DIR = REGION_DIR / "experiments" / "scenario_c"
OWNERSHIP_DIR = SCENARIO_C_DIR / "inputs" / "ownership_sensitivity_20260826"
ROUTES_DIR = SCENARIO_C_DIR / "inputs" / "routes_20260826"
PED_NET = SCENARIO_C_DIR / "network" / "08211_ped.net.xml"
PREFLIGHT_DIR = SCENARIO_C_DIR / "preflight_20260810"
RUNS_DIR = SCENARIO_C_DIR / "runs"
VEHICLE_CLOSURE_TIMELINE = REGION_DIR / "derived" / "closure_timeline_sumo.json"
PEDESTRIAN_CLOSURE_TIMELINE = (
    SCENARIO_C_DIR / "static_alignment_20260826" / "pedestrian_flood_timeline.json"
)
SCENARIO_IDS = ("non_car_10pct", "non_car_15pct", "non_car_20pct")
TOTAL_POPULATION = 21_539
FULL_END_SEC = 21_600
SEEDS = (23423, 42, 1)
CONDITIONS = {
    "c1_15_strict": {
        "cohort": "C1", "scenario_id": "non_car_15pct", "policy": "strict",
        "elderly_speed": 0.58,
    },
    "c2_10_strict": {
        "cohort": "C2-low", "scenario_id": "non_car_10pct", "policy": "strict",
        "elderly_speed": 0.58,
    },
    "c2_20_strict": {
        "cohort": "C2-high", "scenario_id": "non_car_20pct", "policy": "strict",
        "elderly_speed": 0.58,
    },
    "c3_15_wade": {
        "cohort": "C3", "scenario_id": "non_car_15pct", "policy": "wade",
        "elderly_speed": 0.58,
    },
    "c4_15_strict_slow": {
        "cohort": "C4", "scenario_id": "non_car_15pct", "policy": "strict",
        "elderly_speed": 0.50,
    },
}

CAR_ASSIGNMENT_FIELDS = [
    "vehicle_id", "origin_id", "KEY_CODE", "from_sumo_edge_id", "shelter_id",
    "shelter_name", "to_sumo_edge_id", "depart",
]
OCCUPANCY_FIELDS = [
    "scenario_id", "person_id", "age_group", "origin_id", "KEY_CODE", "vehicle_id",
]
ADJUSTMENT_FIELDS = [
    "scenario_id", "origin_id", "car_people", "vehicle_count_before",
    "vehicle_count_after", "delta", "reason",
]
VEHICLE_LOG_FIELDS = [
    "vehicle_id", "origin_id", "KEY_CODE", "from_sumo_edge_id", "to_sumo_edge_id",
    "occupancy_count", "depart", "arrival", "duration", "arrived", "final_status",
    "termination_time_sec", "reroute_count", "reroute_failed", "long_stopped",
    "max_consecutive_stop_sec",
]
PERSON_LOG_FIELDS = [
    "person_id", "origin_id", "KEY_CODE", "age_group", "planned_speed_mps",
    "person_xml_emitted", "preflight_route_status", "depart", "arrival", "duration",
    "arrived", "final_status", "termination_time_sec", "reroute_count",
    "reroute_failed", "shallow_time_sec", "shallow_entry_count",
    "dry_speed_restore_count", "distance_integral_m",
    "max_consecutive_stop_sec",
]
TIMESERIES_FIELDS = [
    "sim_time_sec", "car_people_not_departed", "car_people_active", "car_people_arrived",
    "car_people_terminated", "walk_not_emitted", "walk_not_departed", "walk_active",
    "walk_arrived", "walk_terminated", "completed_people", "unfinished_people",
    "active_vehicle_count", "active_person_count", "mean_vehicle_speed_mps",
    "mean_person_speed_mps",
]
COMBINED_CLOSURE_FIELDS = [
    "time_id", "source_timestamp", "sim_time_sec", "vehicle_new_closed_edges",
    "vehicle_cumulative_closed_edges", "pedestrian_new_closed_edges",
    "pedestrian_cumulative_closed_edges", "wade_shallow_edges", "vehicle_blocked_on_edge",
    "vehicle_departure_blocked", "vehicle_reroute_success", "vehicle_reroute_failed",
    "person_blocked_on_edge", "person_departure_blocked", "person_reroute_success",
    "person_reroute_failed", "person_reroute_deferred",
]


def vehicle_counts(rows: list[dict[str, str]]) -> Counter[str]:
    return Counter(row["origin_id"] for row in rows)


def car_people_by_origin(
    mode_rows: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mode_rows:
        if row["assigned_mode"] == "car":
            grouped[row["origin_id"]].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: row["person_id"])
    return dict(grouped)


def rebalance_vehicle_counts(
    scenario_id: str,
    people_by_origin: dict[str, list[dict[str, str]]],
    original_counts: Counter[str],
) -> tuple[Counter[str], list[dict[str, Any]]]:
    """Give every car-person origin a vehicle while preserving the city total."""
    adjusted = Counter(original_counts)
    before = Counter(original_counts)
    deficits = sorted(
        origin_id
        for origin_id, people in people_by_origin.items()
        if people and adjusted[origin_id] == 0
    )
    for origin_id in deficits:
        adjusted[origin_id] = 1

    for _ in deficits:
        eligible = [
            origin_id
            for origin_id, count in adjusted.items()
            if count > math.ceil(len(people_by_origin.get(origin_id, [])) / 3)
        ]
        if not eligible:
            raise ValueError(f"{scenario_id}: no donor origin for vehicle lower-bound correction")
        donor = min(
            eligible,
            key=lambda origin_id: (
                -(adjusted[origin_id] - math.ceil(len(people_by_origin.get(origin_id, [])) / 3)),
                -adjusted[origin_id],
                origin_id,
            ),
        )
        adjusted[donor] -= 1

    if sum(adjusted.values()) != sum(before.values()):
        raise AssertionError("vehicle rebalancing changed the citywide vehicle total")
    if any(adjusted[origin_id] == 0 for origin_id in people_by_origin):
        raise AssertionError("a car-person origin still has no vehicle")

    changes = []
    for origin_id in sorted(set(before) | set(adjusted)):
        delta = adjusted[origin_id] - before[origin_id]
        if delta:
            changes.append({
                "scenario_id": scenario_id,
                "origin_id": origin_id,
                "car_people": len(people_by_origin.get(origin_id, [])),
                "vehicle_count_before": before[origin_id],
                "vehicle_count_after": adjusted[origin_id],
                "delta": delta,
                "reason": "minimum_one_for_car_people" if delta > 0 else "city_total_balancing_donor",
            })
    return adjusted, changes


def build_adjusted_car_assignments(
    counts: Counter[str],
    people_by_origin: dict[str, list[dict[str, str]]],
    templates: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for origin_id in sorted(counts):
        count = counts[origin_id]
        if not count:
            continue
        template = templates.get(origin_id)
        if template is None:
            raise ValueError(f"{origin_id}: private-car OD template is missing")
        key_code = (
            people_by_origin[origin_id][0]["KEY_CODE"]
            if origin_id in people_by_origin
            else template["KEY_CODE"]
        )
        for index in range(1, count + 1):
            rows.append({
                "vehicle_id": f"scen_c_{origin_id}_{index:04d}",
                "origin_id": origin_id,
                "KEY_CODE": str(key_code).zfill(10),
                "from_sumo_edge_id": template["from_sumo_edge_id"],
                "shelter_id": template["shelter_id"],
                "shelter_name": template["shelter_name"],
                "to_sumo_edge_id": template["to_sumo_edge_id"],
                "depart": "0",
            })
    return rows


def build_occupancy_ledger(
    scenario_id: str,
    mode_rows: list[dict[str, str]],
    car_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    people = car_people_by_origin(mode_rows)
    vehicles: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in car_rows:
        vehicles[row["origin_id"]].append(row)
    output: list[dict[str, Any]] = []
    for origin_id, origin_people in sorted(people.items()):
        origin_vehicles = sorted(vehicles.get(origin_id, []), key=lambda row: row["vehicle_id"])
        if not origin_vehicles:
            raise ValueError(f"{scenario_id}/{origin_id}: car people have no vehicle")
        quotient, remainder = divmod(len(origin_people), len(origin_vehicles))
        cursor = 0
        for index, vehicle in enumerate(origin_vehicles):
            occupancy = quotient + (1 if index < remainder else 0)
            if occupancy < 1:
                raise ValueError(f"{scenario_id}/{origin_id}: empty evacuation car")
            for person in origin_people[cursor: cursor + occupancy]:
                output.append({
                    "scenario_id": scenario_id,
                    "person_id": person["person_id"],
                    "age_group": person["age_group"],
                    "origin_id": origin_id,
                    "KEY_CODE": str(person["KEY_CODE"]).zfill(10),
                    "vehicle_id": vehicle["vehicle_id"],
                })
            cursor += occupancy
        if cursor != len(origin_people):
            raise AssertionError(f"{scenario_id}/{origin_id}: occupancy assignment did not close")
    return output


def write_person_variant(source: Path, target: Path, elderly_speed: float) -> None:
    tree = ET.parse(source)
    root = tree.getroot()
    elderly_type = root.find("vType[@id='walk_elderly']")
    if elderly_type is None:
        raise ValueError(f"{source}: walk_elderly type is missing")
    elderly_type.set("desiredMaxSpeed", f"{elderly_speed:.2f}")
    ET.indent(root)
    tree.write(target, encoding="utf-8", xml_declaration=True)


def run_duarouter(net_path: Path, trips_path: Path, route_path: Path, log_path: Path) -> None:
    configure_sumo_environment(require_tools=True)
    executable = Path(os.environ["SUMO_HOME"]) / "bin" / "duarouter.exe"
    command = [
        str(executable), "--net-file", str(net_path), "--route-files", str(trips_path),
        "--output-file", str(route_path), "--ignore-errors", "false",
        "--xml-validation", "always", "--seed", "23423",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"duarouter failed; see {log_path}")
    alternatives = route_path.with_name(route_path.stem + ".alt.xml")
    if alternatives.exists():
        alternatives.unlink()


def validate_prepared_scenario(
    scenario_id: str,
    mode_rows: list[dict[str, str]],
    car_rows: list[dict[str, Any]],
    occupancy_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    all_person_ids = [row["person_id"] for row in mode_rows]
    car_person_ids = {row["person_id"] for row in mode_rows if row["assigned_mode"] == "car"}
    walk_person_ids = {row["person_id"] for row in mode_rows if row["assigned_mode"] == "walk"}
    occupied_ids = [row["person_id"] for row in occupancy_rows]
    vehicle_ids = {row["vehicle_id"] for row in car_rows}
    validation = {
        "population": len(all_person_ids),
        "person_id_unique": len(all_person_ids) == len(set(all_person_ids)),
        "car_people": len(car_person_ids),
        "walk_people": len(walk_person_ids),
        "car_vehicle_count": len(car_rows),
        "occupancy_rows": len(occupancy_rows),
        "occupancy_person_unique": len(occupied_ids) == len(set(occupied_ids)),
        "occupancy_matches_car_people": set(occupied_ids) == car_person_ids,
        "occupancy_walk_overlap": len(set(occupied_ids) & walk_person_ids),
        "occupancy_unknown_vehicle_count": sum(
            row["vehicle_id"] not in vehicle_ids for row in occupancy_rows
        ),
    }
    if validation != {
        **validation,
        "population": TOTAL_POPULATION,
        "person_id_unique": True,
        "occupancy_rows": len(car_person_ids),
        "occupancy_person_unique": True,
        "occupancy_matches_car_people": True,
        "occupancy_walk_overlap": 0,
        "occupancy_unknown_vehicle_count": 0,
    }:
        raise AssertionError(f"{scenario_id}: prepared accounting validation failed: {validation}")
    return validation


def prepare_inputs(output_dir: Path = PREFLIGHT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    templates = private_assignment_templates(DEFAULT_A_ASSIGNMENTS)
    scenarios = []
    for scenario_id in SCENARIO_IDS:
        scenario_dir = output_dir / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        mode_path = OWNERSHIP_DIR / scenario_id / "scenario_c_mode_ledger.csv"
        source_car_path = ROUTES_DIR / scenario_id / "car_assignment.csv"
        source_person_path = ROUTES_DIR / scenario_id / f"scenario_c_{scenario_id}_persons.rou.xml"
        mode_rows = read_csv_rows(mode_path)
        original_car_rows = read_csv_rows(source_car_path)
        people = car_people_by_origin(mode_rows)
        counts, adjustments = rebalance_vehicle_counts(
            scenario_id, people, vehicle_counts(original_car_rows)
        )
        car_rows = build_adjusted_car_assignments(counts, people, templates)
        occupancy_rows = build_occupancy_ledger(scenario_id, mode_rows, car_rows)
        validation = validate_prepared_scenario(
            scenario_id, mode_rows, car_rows, occupancy_rows
        )

        assignment_path = scenario_dir / "car_assignment.csv"
        adjustments_path = scenario_dir / "car_allocation_adjustments.csv"
        occupancy_path = scenario_dir / "car_occupancy_ledger.csv"
        trips_path = scenario_dir / "cars.trips.xml"
        routes_path = scenario_dir / "cars.rou.xml"
        duarouter_log = scenario_dir / "duarouter.log"
        persons_normal = scenario_dir / "persons_elderly_0.58.rou.xml"
        persons_slow = scenario_dir / "persons_elderly_0.50.rou.xml"
        write_csv(assignment_path, CAR_ASSIGNMENT_FIELDS, car_rows)
        write_csv(adjustments_path, ADJUSTMENT_FIELDS, adjustments)
        write_csv(occupancy_path, OCCUPANCY_FIELDS, occupancy_rows)
        write_car_trips(trips_path, car_rows)
        run_duarouter(PED_NET, trips_path, routes_path, duarouter_log)
        write_person_variant(source_person_path, persons_normal, 0.58)
        write_person_variant(source_person_path, persons_slow, 0.50)

        outputs = [
            assignment_path, adjustments_path, occupancy_path, trips_path, routes_path,
            duarouter_log, persons_normal, persons_slow,
        ]
        scenarios.append({
            "scenario_id": scenario_id,
            "validation": validation,
            "adjustment_count": len(adjustments),
            "input_sha256": {
                "mode_ledger": sha256(mode_path),
                "source_car_assignment": sha256(source_car_path),
                "source_person_routes": sha256(source_person_path),
            },
            "output_sha256": {path.name: sha256(path) for path in outputs},
        })

    manifest = {
        "stage": "C8_preflight_input_preparation",
        "pre8_authorized": True,
        "authorized_full_run_count": 15,
        "full_sumo_run_executed": False,
        "ped_net_sha256": sha256(PED_NET),
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def condition_spec(condition_id: str) -> dict[str, Any]:
    if condition_id not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition_id}")
    return {"condition_id": condition_id, **CONDITIONS[condition_id]}


def verify_preflight(preflight_dir: Path = PREFLIGHT_DIR) -> dict[str, Any]:
    manifest_path = preflight_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("pre8_authorized") or manifest.get("authorized_full_run_count") != 15:
        raise ValueError("PRE-8 authorization is not fixed in the preflight manifest")
    for scenario in manifest["scenarios"]:
        scenario_dir = preflight_dir / scenario["scenario_id"]
        for name, expected in scenario["output_sha256"].items():
            path = scenario_dir / name
            if not path.exists() or sha256(path) != expected:
                raise ValueError(f"preflight SHA mismatch: {path}")
    if sha256(PED_NET) != manifest["ped_net_sha256"]:
        raise ValueError("pedestrian network SHA mismatch")
    return manifest


def build_closure_events(
    policy: str,
    *,
    compressed: bool = False,
) -> list[dict[str, Any]]:
    vehicle_data = json.loads(VEHICLE_CLOSURE_TIMELINE.read_text(encoding="utf-8"))
    pedestrian_data = json.loads(PEDESTRIAN_CLOSURE_TIMELINE.read_text(encoding="utf-8"))
    vehicle_by_time = {row["time_id"]: row for row in vehicle_data["closures"]}
    events = []
    for index, pedestrian in enumerate(pedestrian_data["timeline"]):
        vehicle = vehicle_by_time[pedestrian["time_id"]]
        if policy == "strict":
            pedestrian_closed = pedestrian["strict_closed_edge_ids"]
            shallow: list[str] = []
        elif policy == "wade":
            pedestrian_closed = pedestrian["wade_closed_edge_ids"]
            shallow = pedestrian["wade_shallow_edge_ids"]
        else:
            raise ValueError(policy)
        events.append({
            "time_id": pedestrian["time_id"],
            "source_timestamp": pedestrian["source_timestamp"],
            "sim_time_sec": 2 * (index + 1) if compressed else int(pedestrian["sim_time_sec"]),
            "vehicle_closed_edge_ids": sorted(vehicle["closed_sumo_edge_ids"]),
            "pedestrian_closed_edge_ids": sorted(pedestrian_closed),
            "wade_shallow_edge_ids": sorted(shallow),
        })
    if compressed and policy == "wade" and events:
        events.append({
            "time_id": "smoke_dry_restore",
            "source_timestamp": "synthetic_smoke_only",
            "sim_time_sec": 28,
            "vehicle_closed_edge_ids": list(events[-1]["vehicle_closed_edge_ids"]),
            "pedestrian_closed_edge_ids": list(events[-1]["pedestrian_closed_edge_ids"]),
            "wade_shallow_edge_ids": [],
        })
    return events


def write_run_sumocfg(
    path: Path,
    *,
    end_sec: int,
    tripinfo: Path,
    personinfo: Path,
    fcd: Path,
) -> None:
    root = ET.Element("configuration")
    input_element = ET.SubElement(root, "input")
    ET.SubElement(input_element, "net-file", value=str(PED_NET.resolve()))
    ET.SubElement(input_element, "route-files", value="cars.rou.xml,persons.rou.xml")
    time_element = ET.SubElement(root, "time")
    ET.SubElement(time_element, "begin", value="0")
    ET.SubElement(time_element, "end", value=str(end_sec))
    processing = ET.SubElement(root, "processing")
    ET.SubElement(processing, "time-to-teleport", value="-1")
    ET.SubElement(processing, "pedestrian.striping.jamtime", value="-1")
    ET.SubElement(processing, "person-device.fcd.probability", value="1")
    output = ET.SubElement(root, "output")
    ET.SubElement(output, "tripinfo-output", value=tripinfo.name)
    ET.SubElement(output, "personinfo-output", value=personinfo.name)
    ET.SubElement(output, "fcd-output", value=fcd.name)
    ET.SubElement(output, "device.fcd.period", value="60")
    ET.SubElement(output, "fcd-output.geo", value="true")
    ET.SubElement(output, "tripinfo-output.write-unfinished", value="true")
    ET.SubElement(output, "tripinfo-output.write-undeparted", value="true")
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def run_input_paths(
    condition_id: str,
    run_dir: Path,
    preflight_dir: Path = PREFLIGHT_DIR,
) -> dict[str, Path]:
    spec = condition_spec(condition_id)
    source_dir = preflight_dir / spec["scenario_id"]
    speed_text = f"{spec['elderly_speed']:.2f}"
    sources = {
        "cars": source_dir / "cars.rou.xml",
        "persons": source_dir / f"persons_elderly_{speed_text}.rou.xml",
        "assignments": source_dir / "car_assignment.csv",
        "occupancy": source_dir / "car_occupancy_ledger.csv",
        "adjustments": source_dir / "car_allocation_adjustments.csv",
        "walk_ledger": ROUTES_DIR / spec["scenario_id"] / "walk_person_ledger.csv",
        "mode_ledger": OWNERSHIP_DIR / spec["scenario_id"] / "scenario_c_mode_ledger.csv",
    }
    targets = {
        "cars": run_dir / "cars.rou.xml",
        "persons": run_dir / "persons.rou.xml",
        "assignments": run_dir / "car_assignment.csv",
        "occupancy": run_dir / "car_occupancy_ledger.csv",
        "adjustments": run_dir / "car_allocation_adjustments.csv",
        "walk_ledger": run_dir / "walk_person_ledger.csv",
        "mode_ledger": run_dir / "scenario_c_mode_ledger.csv",
    }
    for key, source in sources.items():
        if not source.exists():
            raise FileNotFoundError(source)
        shutil.copy2(source, targets[key])
    assign_unique_vehicle_routes(targets["cars"])
    return targets


def assign_unique_vehicle_routes(path: Path) -> None:
    """Replace embedded routes with equivalent per-vehicle route IDs."""
    tree = ET.parse(path)
    root = tree.getroot()
    vehicles = root.findall("vehicle")
    route_elements: list[ET.Element] = []
    for vehicle in vehicles:
        embedded = vehicle.find("route")
        if embedded is None or not embedded.attrib.get("edges"):
            raise ValueError(f"embedded route missing for {vehicle.attrib.get('id', '')}")
        route_id = f"route__{vehicle.attrib['id']}"
        route_elements.append(ET.Element("route", id=route_id, edges=embedded.attrib["edges"]))
        vehicle.remove(embedded)
        vehicle.set("route", route_id)
    first_vehicle_index = min(
        (index for index, child in enumerate(list(root)) if child.tag == "vehicle"),
        default=len(root),
    )
    for offset, route in enumerate(route_elements):
        root.insert(first_vehicle_index + offset, route)
    ET.indent(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def initialize_person_state(
    walk_rows: list[dict[str, str]],
    elderly_speed: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    state: dict[str, dict[str, Any]] = {}
    by_source: dict[str, list[str]] = defaultdict(list)
    for row in walk_rows:
        emitted = row["person_xml_emitted"] == "true"
        base_speed = elderly_speed if row["age_group"] == "elderly" else 1.0
        state[row["person_id"]] = {
            "person_id": row["person_id"],
            "origin_id": row["origin_id"],
            "KEY_CODE": row["KEY_CODE"],
            "age_group": row["age_group"],
            "planned_speed_mps": base_speed,
            "person_xml_emitted": emitted,
            "preflight_route_status": row["route_status"],
            "shelter_edge_id": row["shelter_edge_id"],
            "depart": "",
            "arrival": "",
            "arrived": False,
            "final_status": "" if emitted else f"preflight_{row['not_emitted_reason']}",
            "termination_time_sec": "",
            "reroute_count": 0,
            "reroute_failed": False,
            "shallow_time_sec": 0,
            "shallow_entry_count": 0,
            "dry_speed_restore_count": 0,
            "in_shallow": False,
            "distance_integral_m": 0.0,
            "current_stop_sec": 0,
            "max_consecutive_stop_sec": 0,
            "last_speed_limit": None,
        }
        if emitted:
            by_source[row["origin_edge_id"]].append(row["person_id"])
    return state, dict(by_source)


def add_disallowed_on_edges(
    traci: Any,
    net: Any,
    edge_ids: set[str],
    vehicle_class: str,
) -> int:
    changed = 0
    for edge_id in sorted(edge_ids):
        try:
            edge = net.getEdge(edge_id)
        except KeyError:
            continue
        edge_changed = False
        for lane in edge.getLanes():
            lane_id = lane.getID()
            try:
                disallowed = set(traci.lane.getDisallowed(lane_id))
                if vehicle_class not in disallowed:
                    traci.lane.setDisallowed(lane_id, sorted(disallowed | {vehicle_class}))
                    edge_changed = True
            except traci.TraCIException:
                continue
        changed += int(edge_changed)
    return changed


def remaining_person_edges(traci: Any, person_id: str) -> list[str]:
    """Return the untraversed external edges of the current walking stage."""
    route = list(traci.person.getEdges(person_id))
    if not route:
        return []
    road_id = traci.person.getRoadID(person_id)
    next_edge = traci.person.getNextEdge(person_id)
    if road_id in route:
        candidates = [index for index, edge_id in enumerate(route) if edge_id == road_id]
        if next_edge:
            for index in candidates:
                if index + 1 < len(route) and route[index + 1] == next_edge:
                    return route[index:]
        return route[candidates[-1]:]
    if next_edge in route:
        return route[route.index(next_edge):]
    return route


def reroute_person_to_shelter(
    traci: Any,
    tc: Any,
    person_id: str,
    item: dict[str, Any],
    closed_edges: set[str],
) -> str:
    """Replace the current walking stage with a validated pedestrian-only stage."""
    road_id = traci.person.getRoadID(person_id)
    if not road_id or road_id.startswith(":"):
        return "deferred"
    stages = traci.simulation.findIntermodalRoute(
        road_id,
        item["shelter_edge_id"],
        modes="",
        speed=item["planned_speed_mps"],
        departPos=traci.person.getLanePosition(person_id),
    )
    walking = [stage for stage in stages if stage.type == tc.STAGE_WALKING]
    if len(walking) != 1 or not walking[0].edges:
        return "failed"
    if closed_edges.intersection(walking[0].edges):
        return "failed"
    traci.person.replaceStage(person_id, 0, walking[0])
    item["reroute_count"] += 1
    return "success"


def final_vehicle_rows(
    planned: dict[str, dict[str, str]],
    state: dict[str, dict[str, Any]],
    occupancy_counts: Counter[str],
    end_sec: int,
) -> list[dict[str, Any]]:
    rows = []
    for vehicle_id, plan in sorted(planned.items()):
        item = state.get(vehicle_id, {})
        arrived = bool(item.get("arrived"))
        final_status = item.get("final_status")
        if not final_status:
            final_status = "arrived" if arrived else (
                "simulation_end_active" if item.get("depart") != "" else "not_departed"
            )
        depart = item.get("depart", "")
        arrival = item.get("arrival", "")
        duration = arrival - depart if isinstance(arrival, int) and isinstance(depart, int) else ""
        rows.append({
            "vehicle_id": vehicle_id,
            "origin_id": plan["origin_id"],
            "KEY_CODE": plan["KEY_CODE"],
            "from_sumo_edge_id": plan["from_sumo_edge_id"],
            "to_sumo_edge_id": plan["to_sumo_edge_id"],
            "occupancy_count": occupancy_counts[vehicle_id],
            "depart": depart,
            "arrival": arrival,
            "duration": duration,
            "arrived": arrived,
            "final_status": final_status,
            "termination_time_sec": item.get("termination_time_sec", ""),
            "reroute_count": item.get("reroute_count", 0),
            "reroute_failed": item.get("reroute_failed", False),
            "long_stopped": item.get("max_consecutive_stop_sec", 0) >= 600,
            "max_consecutive_stop_sec": item.get("max_consecutive_stop_sec", 0),
        })
    return rows


def final_person_rows(
    state: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for person_id, item in sorted(state.items()):
        final_status = item["final_status"]
        if not final_status:
            final_status = "arrived" if item["arrived"] else (
                "simulation_end_active" if item["depart"] != "" else "not_departed"
            )
        depart = item["depart"]
        arrival = item["arrival"]
        duration = arrival - depart if isinstance(arrival, int) and isinstance(depart, int) else ""
        rows.append({
            "person_id": person_id,
            "origin_id": item["origin_id"],
            "KEY_CODE": item["KEY_CODE"],
            "age_group": item["age_group"],
            "planned_speed_mps": f"{item['planned_speed_mps']:.2f}",
            "person_xml_emitted": item["person_xml_emitted"],
            "preflight_route_status": item["preflight_route_status"],
            "depart": depart,
            "arrival": arrival,
            "duration": duration,
            "arrived": item["arrived"],
            "final_status": final_status,
            "termination_time_sec": item["termination_time_sec"],
            "reroute_count": item["reroute_count"],
            "reroute_failed": item["reroute_failed"],
            "shallow_time_sec": item["shallow_time_sec"],
            "shallow_entry_count": item["shallow_entry_count"],
            "dry_speed_restore_count": item["dry_speed_restore_count"],
            "distance_integral_m": f"{item['distance_integral_m']:.3f}",
            "max_consecutive_stop_sec": item["max_consecutive_stop_sec"],
        })
    return rows


def timeseries_row(
    sim_time: int,
    vehicle_state: dict[str, dict[str, Any]],
    person_state: dict[str, dict[str, Any]],
    occupancy_counts: Counter[str],
    vehicle_speeds: list[float],
    person_speeds: list[float],
) -> dict[str, Any]:
    car_counts = Counter()
    for vehicle_id, count in occupancy_counts.items():
        item = vehicle_state.get(vehicle_id, {})
        if item.get("arrived"):
            car_counts["arrived"] += count
        elif item.get("final_status"):
            car_counts["terminated"] += count
        elif item.get("depart") != "" and item:
            car_counts["active"] += count
        else:
            car_counts["not_departed"] += count
    walk_counts = Counter()
    for item in person_state.values():
        if not item["person_xml_emitted"]:
            walk_counts["not_emitted"] += 1
        elif item["arrived"]:
            walk_counts["arrived"] += 1
        elif item["final_status"]:
            walk_counts["terminated"] += 1
        elif item["depart"] != "":
            walk_counts["active"] += 1
        else:
            walk_counts["not_departed"] += 1
    completed = car_counts["arrived"] + walk_counts["arrived"]
    return {
        "sim_time_sec": sim_time,
        "car_people_not_departed": car_counts["not_departed"],
        "car_people_active": car_counts["active"],
        "car_people_arrived": car_counts["arrived"],
        "car_people_terminated": car_counts["terminated"],
        "walk_not_emitted": walk_counts["not_emitted"],
        "walk_not_departed": walk_counts["not_departed"],
        "walk_active": walk_counts["active"],
        "walk_arrived": walk_counts["arrived"],
        "walk_terminated": walk_counts["terminated"],
        "completed_people": completed,
        "unfinished_people": TOTAL_POPULATION - completed,
        "active_vehicle_count": len(vehicle_speeds),
        "active_person_count": len(person_speeds),
        "mean_vehicle_speed_mps": f"{sum(vehicle_speeds) / len(vehicle_speeds):.4f}" if vehicle_speeds else "",
        "mean_person_speed_mps": f"{sum(person_speeds) / len(person_speeds):.4f}" if person_speeds else "",
    }


def build_run_summary(
    vehicle_rows: list[dict[str, Any]],
    person_rows: list[dict[str, Any]],
    condition: dict[str, Any],
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    arrived_car_people = sum(
        int(row["occupancy_count"]) for row in vehicle_rows if row["arrived"]
    )
    arrived_walk_people = sum(1 for row in person_rows if row["arrived"])
    car_people = sum(int(row["occupancy_count"]) for row in vehicle_rows)
    walk_people = len(person_rows)
    completed = arrived_car_people + arrived_walk_people
    vehicle_status = Counter(row["final_status"] for row in vehicle_rows)
    person_status = Counter(row["final_status"] for row in person_rows)
    accounting = {
        "car_people": car_people,
        "walk_people": walk_people,
        "population": car_people + walk_people,
        "completed_people": completed,
        "unfinished_people": car_people + walk_people - completed,
        "population_closes": car_people + walk_people == TOTAL_POPULATION,
        "completion_accounting_closes": completed + (car_people + walk_people - completed) == TOTAL_POPULATION,
    }
    summary = {
        "condition_id": condition["condition_id"],
        "cohort": condition["cohort"],
        "scenario_id": condition["scenario_id"],
        "policy": condition["policy"],
        "elderly_speed_mps": condition["elderly_speed"],
        "seed": seed,
        "population": TOTAL_POPULATION,
        "completed_people": completed,
        "completion_rate": completed / TOTAL_POPULATION,
        "arrived_car_people": arrived_car_people,
        "arrived_walk_people": arrived_walk_people,
        "vehicle_status_counts": dict(sorted(vehicle_status.items())),
        "person_status_counts": dict(sorted(person_status.items())),
    }
    return summary, accounting


def run_integrated(
    condition_id: str,
    seed: int,
    *,
    end_sec: int = FULL_END_SEC,
    compressed_closures: bool = False,
    apply_closures: bool = True,
    smoke_label: str = "",
    runs_root: Path = RUNS_DIR,
) -> dict[str, Any]:
    verify_preflight()
    condition = condition_spec(condition_id)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    label = smoke_label or "full"
    run_id = (
        f"scenario_c_{condition_id}_{seed}_{label}_{timestamp}_{uuid4().hex[:8]}"
    )
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    paths = run_input_paths(condition_id, run_dir)
    tripinfo = run_dir / "tripinfo.xml"
    personinfo = run_dir / "personinfo.xml"
    fcd = run_dir / "fcd.xml"
    sumocfg = run_dir / "scenario_c.sumocfg"
    write_run_sumocfg(
        sumocfg, end_sec=end_sec, tripinfo=tripinfo, personinfo=personinfo, fcd=fcd
    )

    assignments = {row["vehicle_id"]: row for row in read_csv_rows(paths["assignments"])}
    occupancy = read_csv_rows(paths["occupancy"])
    occupancy_counts = Counter(row["vehicle_id"] for row in occupancy)
    walk_rows = read_csv_rows(paths["walk_ledger"])
    person_state, persons_by_source = initialize_person_state(
        walk_rows, float(condition["elderly_speed"])
    )
    vehicle_state: dict[str, dict[str, Any]] = {}
    departed_vehicles: set[str] = set()
    departed_persons: set[str] = set()
    events = build_closure_events(
        condition["policy"], compressed=compressed_closures
    ) if apply_closures else []

    configure_sumo_environment(require_tools=True)
    import traci
    import traci.constants as tc
    import sumolib

    net = sumolib.net.readNet(str(PED_NET))
    sumo = Path(os.environ["SUMO_HOME"]) / "bin" / "sumo.exe"
    sumo_log = run_dir / "sumo.log"
    command = [
        str(sumo), "-c", str(sumocfg), "--seed", str(seed),
        "--no-step-log", "true", "--duration-log.disable", "true",
        "--log", str(sumo_log),
    ]
    input_hashes = {
        "ped_net": sha256(PED_NET),
        "vehicle_closure_timeline": sha256(VEHICLE_CLOSURE_TIMELINE),
        "pedestrian_closure_timeline": sha256(PEDESTRIAN_CLOSURE_TIMELINE),
        **{path.name: sha256(path) for path in paths.values()},
        "scenario_c.sumocfg": sha256(sumocfg),
        "scenario_c_integrated.py": sha256(Path(__file__)),
    }
    sentinel_paths = {
        name: REGION_DIR / "scenarios" / name
        for name in ("scenario_a.rou.xml", "scenario_b.rou.xml")
    }
    sentinel_before = {
        name: sha256(path) for name, path in sentinel_paths.items() if path.exists()
    }

    vehicle_closed: set[str] = set()
    pedestrian_closed: set[str] = set()
    current_shallow: set[str] = set()
    closure_rows: list[dict[str, Any]] = []
    timeseries: list[dict[str, Any]] = []
    event_index = 0
    pending_person_reroutes: dict[str, int] = {}
    pending_vehicle_reroutes: dict[str, tuple[int, int]] = {}
    closed_entry_violations = 0
    last_sim_time = 0
    run_error = ""
    fatal_exception: Exception | None = None
    started_at = datetime.now().isoformat(timespec="seconds")
    try:
        traci.start(command)
        while traci.simulation.getTime() <= end_sec and (
            traci.simulation.getMinExpectedNumber() > 0 or event_index < len(events)
        ):
            traci.simulationStep()
            sim_time = int(traci.simulation.getTime())
            last_sim_time = sim_time

            for vehicle_id in traci.simulation.getDepartedIDList():
                departed_vehicles.add(vehicle_id)
                item = vehicle_state.setdefault(vehicle_id, {
                    "depart": sim_time, "arrival": "", "arrived": False,
                    "final_status": "", "termination_time_sec": "",
                    "reroute_count": 0, "reroute_failed": False,
                    "current_stop_sec": 0, "max_consecutive_stop_sec": 0,
                })
                if item.get("final_status") == "departure_blocked":
                    traci.vehicle.remove(vehicle_id)
                    continue
                traci.vehicle.subscribe(vehicle_id, [tc.VAR_SPEED, tc.VAR_ROAD_ID])
            for person_id in traci.simulation.getDepartedPersonIDList():
                departed_persons.add(person_id)
                if person_id in person_state:
                    if person_state[person_id]["final_status"] == "departure_blocked":
                        traci.person.remove(person_id)
                        continue
                    person_state[person_id]["depart"] = sim_time
                    traci.person.subscribe(person_id, [tc.VAR_SPEED, tc.VAR_ROAD_ID])

            for vehicle_id in traci.simulation.getArrivedIDList():
                item = vehicle_state.setdefault(vehicle_id, {})
                item.update({"arrival": sim_time, "arrived": True, "final_status": "arrived"})
            for person_id in traci.simulation.getArrivedPersonIDList():
                if person_id in person_state:
                    person_state[person_id].update({
                        "arrival": sim_time, "arrived": True, "final_status": "arrived"
                    })

            while event_index < len(events) and sim_time >= int(events[event_index]["sim_time_sec"]):
                event = events[event_index]
                new_vehicle = set(event["vehicle_closed_edge_ids"]) - vehicle_closed
                new_person = set(event["pedestrian_closed_edge_ids"]) - pedestrian_closed
                current_shallow = set(event["wade_shallow_edge_ids"])
                vehicle_blocked = person_blocked = 0
                vehicle_departure_blocked = person_departure_blocked = 0
                vehicle_reroute_success = vehicle_reroute_failed = 0
                person_reroute_success = person_reroute_failed = 0
                person_reroute_deferred = 0

                for vehicle_id in list(traci.vehicle.getIDList()):
                    try:
                        road_id = traci.vehicle.getRoadID(vehicle_id)
                    except traci.TraCIException:
                        continue
                    if road_id in new_vehicle:
                        traci.vehicle.unsubscribe(vehicle_id)
                        traci.vehicle.remove(vehicle_id)
                        vehicle_state[vehicle_id].update({
                            "final_status": "flood_blocked_on_edge",
                            "termination_time_sec": sim_time,
                        })
                        vehicle_blocked += 1
                for edge_id in new_vehicle:
                    for vehicle_id, plan in assignments.items():
                        if (
                            plan["from_sumo_edge_id"] == edge_id
                            and vehicle_id not in departed_vehicles
                            and not vehicle_state.get(vehicle_id, {}).get("final_status")
                        ):
                            vehicle_state.setdefault(vehicle_id, {}).update({
                                "final_status": "departure_blocked",
                                "termination_time_sec": sim_time,
                            })
                            traci.simulation.clearPending(f"route__{vehicle_id}")
                            vehicle_departure_blocked += 1
                add_disallowed_on_edges(traci, net, new_vehicle, "passenger")
                vehicle_closed.update(new_vehicle)
                for vehicle_id in list(traci.vehicle.getIDList()):
                    if vehicle_state.get(vehicle_id, {}).get("final_status"):
                        continue
                    try:
                        route = list(traci.vehicle.getRoute(vehicle_id))
                        route_index = max(0, traci.vehicle.getRouteIndex(vehicle_id))
                        if not vehicle_closed.intersection(route[route_index:]):
                            continue
                        traci.vehicle.unsubscribe(vehicle_id)
                        traci.vehicle.rerouteTraveltime(vehicle_id)
                        vehicle_state[vehicle_id]["reroute_count"] += 1
                        pending_vehicle_reroutes[vehicle_id] = (len(closure_rows), sim_time)
                    except traci.TraCIException:
                        vehicle_reroute_failed += 1
                        if vehicle_id in vehicle_state:
                            vehicle_state[vehicle_id].update({
                                "final_status": "reroute_failed", "reroute_failed": True,
                                "termination_time_sec": sim_time,
                            })
                        if vehicle_id in traci.vehicle.getIDList():
                            try:
                                traci.vehicle.remove(vehicle_id)
                            except traci.TraCIException:
                                pass

                for person_id in list(traci.person.getIDList()):
                    if person_id not in person_state:
                        continue
                    try:
                        road_id = traci.person.getRoadID(person_id)
                    except traci.TraCIException:
                        continue
                    if road_id in new_person:
                        traci.person.remove(person_id)
                        person_state[person_id].update({
                            "final_status": "flood_blocked_on_edge",
                            "termination_time_sec": sim_time,
                        })
                        person_blocked += 1
                for edge_id in new_person:
                    for person_id in persons_by_source.get(edge_id, []):
                        if (
                            person_id not in departed_persons
                            and not person_state[person_id]["final_status"]
                        ):
                            person_state[person_id].update({
                                "final_status": "departure_blocked",
                                "termination_time_sec": sim_time,
                            })
                            person_departure_blocked += 1
                add_disallowed_on_edges(traci, net, new_person, "pedestrian")
                pedestrian_closed.update(new_person)
                for person_id in list(traci.person.getIDList()):
                    if person_id not in person_state or person_state[person_id]["final_status"]:
                        continue
                    try:
                        road_id = traci.person.getRoadID(person_id)
                        next_edge = traci.person.getNextEdge(person_id)
                        if road_id.startswith(":") and next_edge in pedestrian_closed:
                            traci.person.remove(person_id)
                            person_state[person_id].update({
                                "final_status": "flood_blocked_on_edge",
                                "termination_time_sec": sim_time,
                            })
                            person_blocked += 1
                            continue
                        route = set(remaining_person_edges(traci, person_id))
                        if not pedestrian_closed.intersection(route):
                            continue
                        result = reroute_person_to_shelter(
                            traci, tc, person_id, person_state[person_id], pedestrian_closed
                        )
                        if result == "success":
                            person_reroute_success += 1
                        elif result == "deferred":
                            person_reroute_deferred += 1
                            raise traci.TraCIException("cannot reroute person on internal edge")
                        else:
                            raise traci.TraCIException("no validated pedestrian reroute")
                    except traci.TraCIException:
                        person_reroute_failed += 1
                        person_state[person_id].update({
                            "final_status": "reroute_failed", "reroute_failed": True,
                            "termination_time_sec": sim_time,
                        })
                        try:
                            traci.person.remove(person_id)
                        except traci.TraCIException:
                            pass
                closure_rows.append({
                    "time_id": event["time_id"],
                    "source_timestamp": event["source_timestamp"],
                    "sim_time_sec": sim_time,
                    "vehicle_new_closed_edges": len(new_vehicle),
                    "vehicle_cumulative_closed_edges": len(vehicle_closed),
                    "pedestrian_new_closed_edges": len(new_person),
                    "pedestrian_cumulative_closed_edges": len(pedestrian_closed),
                    "wade_shallow_edges": len(current_shallow),
                    "vehicle_blocked_on_edge": vehicle_blocked,
                    "vehicle_departure_blocked": vehicle_departure_blocked,
                    "vehicle_reroute_success": vehicle_reroute_success,
                    "vehicle_reroute_failed": vehicle_reroute_failed,
                    "person_blocked_on_edge": person_blocked,
                    "person_departure_blocked": person_departure_blocked,
                    "person_reroute_success": person_reroute_success,
                    "person_reroute_failed": person_reroute_failed,
                    "person_reroute_deferred": person_reroute_deferred,
                })
                event_index += 1

            active_vehicle_ids = set(traci.vehicle.getIDList())
            for vehicle_id, (closure_index, requested_at) in list(pending_vehicle_reroutes.items()):
                if sim_time <= requested_at:
                    continue
                if vehicle_id not in active_vehicle_ids:
                    if vehicle_state[vehicle_id].get("arrived"):
                        closure_rows[closure_index]["vehicle_reroute_success"] += 1
                    else:
                        closure_rows[closure_index]["vehicle_reroute_failed"] += 1
                        vehicle_state[vehicle_id].update({
                            "final_status": "reroute_failed", "reroute_failed": True,
                            "termination_time_sec": sim_time,
                        })
                    pending_vehicle_reroutes.pop(vehicle_id, None)
                    continue
                try:
                    route = list(traci.vehicle.getRoute(vehicle_id))
                    route_index = max(0, traci.vehicle.getRouteIndex(vehicle_id))
                    if vehicle_closed.intersection(route[route_index:]):
                        raise traci.TraCIException("closed edge remains after vehicle reroute")
                    closure_rows[closure_index]["vehicle_reroute_success"] += 1
                    traci.vehicle.subscribe(vehicle_id, [tc.VAR_SPEED, tc.VAR_ROAD_ID])
                except traci.TraCIException:
                    closure_rows[closure_index]["vehicle_reroute_failed"] += 1
                    vehicle_state[vehicle_id].update({
                        "final_status": "reroute_failed", "reroute_failed": True,
                        "termination_time_sec": sim_time,
                    })
                    if vehicle_id in traci.vehicle.getIDList():
                        try:
                            traci.vehicle.remove(vehicle_id)
                        except traci.TraCIException:
                            pass
                pending_vehicle_reroutes.pop(vehicle_id, None)

            vehicle_results = traci.vehicle.getAllSubscriptionResults() or {}
            vehicle_speeds = []
            for vehicle_id, values in vehicle_results.items():
                if vehicle_id not in vehicle_state or vehicle_state[vehicle_id].get("final_status"):
                    continue
                speed = max(0.0, float(values.get(tc.VAR_SPEED, 0.0)))
                road_id = values.get(tc.VAR_ROAD_ID, "")
                vehicle_speeds.append(speed)
                item = vehicle_state[vehicle_id]
                item["current_stop_sec"] = item.get("current_stop_sec", 0) + 1 if speed <= 0.1 else 0
                item["max_consecutive_stop_sec"] = max(
                    item.get("max_consecutive_stop_sec", 0), item["current_stop_sec"]
                )
                if road_id in vehicle_closed:
                    closed_entry_violations += 1
                    item.update({
                        "final_status": "closed_edge_entry_violation",
                        "termination_time_sec": sim_time,
                    })
                    try:
                        traci.vehicle.unsubscribe(vehicle_id)
                        traci.vehicle.remove(vehicle_id)
                    except traci.TraCIException:
                        pass

            person_results = traci.person.getAllSubscriptionResults() or {}
            person_speeds = []
            for person_id, values in person_results.items():
                if person_id not in person_state or person_state[person_id]["final_status"]:
                    continue
                speed = max(0.0, float(values.get(tc.VAR_SPEED, 0.0)))
                road_id = values.get(tc.VAR_ROAD_ID, "")
                person_speeds.append(speed)
                item = person_state[person_id]
                if road_id in pedestrian_closed:
                    closed_entry_violations += 1
                    item.update({
                        "final_status": "closed_edge_entry_violation",
                        "termination_time_sec": sim_time,
                    })
                    try:
                        traci.person.remove(person_id)
                    except traci.TraCIException:
                        pass
                    continue
                shallow = condition["policy"] == "wade" and road_id in current_shallow
                target_speed = item["planned_speed_mps"] * (0.60 if shallow else 1.0)
                if shallow and not item["in_shallow"]:
                    item["shallow_entry_count"] += 1
                elif not shallow and item["in_shallow"]:
                    item["dry_speed_restore_count"] += 1
                item["in_shallow"] = shallow
                if item["last_speed_limit"] != target_speed:
                    traci.person.setSpeed(person_id, target_speed)
                    item["last_speed_limit"] = target_speed
                if shallow:
                    item["shallow_time_sec"] += 1
                item["distance_integral_m"] += speed
                item["current_stop_sec"] = item["current_stop_sec"] + 1 if speed <= 0.1 else 0
                item["max_consecutive_stop_sec"] = max(
                    item["max_consecutive_stop_sec"], item["current_stop_sec"]
                )

            if sim_time % 60 == 0 or sim_time == 1 or sim_time >= end_sec:
                timeseries.append(timeseries_row(
                    sim_time, vehicle_state, person_state, occupancy_counts,
                    vehicle_speeds, person_speeds,
                ))
    except Exception as exc:
        run_error = f"{type(exc).__name__}: {exc}"
        fatal_exception = exc
    finally:
        try:
            traci.close()
        except Exception:
            pass
        ended_at = datetime.now().isoformat(timespec="seconds")

    vehicle_rows = final_vehicle_rows(
        assignments, vehicle_state, occupancy_counts, end_sec
    )
    person_rows = final_person_rows(person_state)
    write_csv(run_dir / "vehicle_log.csv", VEHICLE_LOG_FIELDS, vehicle_rows)
    write_csv(run_dir / "person_log.csv", PERSON_LOG_FIELDS, person_rows)
    write_csv(run_dir / "person_timeseries.csv", TIMESERIES_FIELDS, timeseries)
    write_csv(run_dir / "closure_log.csv", COMBINED_CLOSURE_FIELDS, closure_rows)
    summary, accounting = build_run_summary(
        vehicle_rows, person_rows, condition, seed
    )
    accounting.update({
        "closed_edge_entry_violation_count": closed_entry_violations,
        "processed_closure_event_count": len(closure_rows),
        "expected_closure_event_count": sum(
            int(event["sim_time_sec"]) <= end_sec for event in events
        ),
        "pending_person_reroute_count": len(pending_person_reroutes),
        "pending_vehicle_reroute_count": len(pending_vehicle_reroutes),
        "run_error": run_error,
    })
    accounting["technical_valid"] = (
        not run_error
        and accounting["population_closes"]
        and accounting["completion_accounting_closes"]
        and accounting["closed_edge_entry_violation_count"] == 0
        and accounting["processed_closure_event_count"] == accounting["expected_closure_event_count"]
        and accounting["pending_person_reroute_count"] == 0
        and accounting["pending_vehicle_reroute_count"] == 0
    )
    (run_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "accounting_validation.json").write_text(
        json.dumps(accounting, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    sentinel_after = {
        name: sha256(path) for name, path in sentinel_paths.items() if path.exists()
    }
    output_paths = [
        path for path in run_dir.iterdir()
        if path.is_file() and path.name != "run_manifest.json"
    ]
    manifest = {
        "run_id": run_id,
        "condition": condition,
        "seed": seed,
        "started_at": started_at,
        "ended_at": ended_at,
        "last_sim_time": last_sim_time,
        "requested_end_sec": end_sec,
        "smoke_label": smoke_label,
        "compressed_closures": compressed_closures,
        "apply_closures": apply_closures,
        "pre8_authorized": True,
        "full_sumo_run_executed": end_sec >= FULL_END_SEC and not smoke_label,
        "technical_valid": accounting["technical_valid"],
        "run_error": run_error,
        "input_sha256": input_hashes,
        "sentinel_before": sentinel_before,
        "sentinel_after": sentinel_after,
        "existing_outputs_modified": sentinel_before != sentinel_after,
        "output_sha256": {path.name: sha256(path) for path in sorted(output_paths)},
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if manifest["existing_outputs_modified"]:
        raise AssertionError("Scenario A/B sentinel changed during Scenario C run")
    if fatal_exception is not None:
        raise RuntimeError(f"invalid run preserved at {run_dir}: {run_error}") from fatal_exception
    if not manifest["technical_valid"]:
        raise AssertionError(f"technical validation failed: {accounting}")
    return {"manifest": manifest, "summary": summary, "accounting": accounting}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--output-dir", type=Path, default=PREFLIGHT_DIR)
    run = subparsers.add_parser("run")
    run.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    run.add_argument("--seed", type=int, required=True)
    run.add_argument("--end", type=int, default=FULL_END_SEC)
    run.add_argument("--compressed-closures", action="store_true")
    run.add_argument("--no-closures", action="store_true")
    run.add_argument("--smoke-label", default="")
    run.add_argument("--runs-root", type=Path, default=RUNS_DIR)
    run_all = subparsers.add_parser("run-all")
    run_all.add_argument("--runs-root", type=Path, default=RUNS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare_inputs(args.output_dir), ensure_ascii=False, indent=2))
        return 0
    if args.command == "run":
        print(json.dumps(run_integrated(
            args.condition,
            args.seed,
            end_sec=args.end,
            compressed_closures=args.compressed_closures,
            apply_closures=not args.no_closures,
            smoke_label=args.smoke_label,
            runs_root=args.runs_root,
        ), ensure_ascii=False, indent=2))
        return 0
    if args.command == "run-all":
        completed: set[tuple[str, int]] = set()
        if args.runs_root.exists():
            for manifest_path in args.runs_root.glob("*/run_manifest.json"):
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("full_sumo_run_executed") and manifest.get("technical_valid"):
                    completed.add((manifest["condition"]["condition_id"], int(manifest["seed"])))
        results = []
        for condition_id in CONDITIONS:
            for seed in SEEDS:
                if (condition_id, seed) in completed:
                    continue
                results.append(run_integrated(
                    condition_id, seed, runs_root=args.runs_root
                )["manifest"]["run_id"])
        print(json.dumps({"completed_run_ids": results}, ensure_ascii=False, indent=2))
        return 0
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
