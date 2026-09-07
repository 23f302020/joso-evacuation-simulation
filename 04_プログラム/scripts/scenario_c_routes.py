"""Build Scenario C pedestrian and private-car input files without running SUMO."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

from p2_sumo_env import configure_sumo_environment
from scenario_c_car_walk import (
    allocate_bounded_proportional,
    read_csv_rows,
    round_half_up,
    sha256,
    write_csv,
)


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
REGION_DIR = PROGRAM_DIR / "output" / "sumo" / "regions" / "08211"
SCENARIO_C_DIR = REGION_DIR / "experiments" / "scenario_c"
DEFAULT_PED_NET = SCENARIO_C_DIR / "network" / "08211_ped.net.xml"
DEFAULT_OSM = REGION_DIR / "network" / "08211.osm.xml"
DEFAULT_NETWORK_LOG = SCENARIO_C_DIR / "network" / "netconvert_ped.log"
DEFAULT_OWNERSHIP_DIR = (
    SCENARIO_C_DIR / "inputs" / "ownership_sensitivity_20260826"
)
DEFAULT_OUTPUT_DIR = SCENARIO_C_DIR / "inputs" / "routes_20260826"
DEFAULT_ORIGINS = REGION_DIR / "derived" / "agent_origins_10pct.csv"
DEFAULT_SHELTERS = REGION_DIR / "derived" / "shelters_sumo.csv"
DEFAULT_A_ASSIGNMENTS = REGION_DIR / "derived" / "scenario_a_vehicle_assignments.csv"
DEFAULT_EXISTING_NET = REGION_DIR / "network" / "08211.net.xml"
DEFAULT_CLOSURE_TIMELINE = REGION_DIR / "derived" / "closure_timeline_sumo.json"

HOUSEHOLD_SIZE = 2.3
MAX_WALK_DISTANCE_M = 2000.0
WALK_SPEEDS = {"non_elderly": 1.00, "elderly": 0.58}
LOW_ELDERLY_SPEED = 0.50
ROUTE_FIELDS = [
    "origin_id",
    "KEY_CODE",
    "origin_edge_id",
    "origin_connector_m",
    "shelter_id",
    "shelter_name",
    "shelter_edge_id",
    "shelter_connector_m",
    "network_distance_m",
    "total_walk_distance_m",
    "route_status",
    "route_edge_count",
    "route_edges",
]
PERSON_FIELDS = [
    "person_id",
    "origin_id",
    "KEY_CODE",
    "person_type",
    "age_group",
    "walk_speed_mps",
    "origin_edge_id",
    "shelter_id",
    "shelter_edge_id",
    "total_walk_distance_m",
    "free_flow_walk_time_s",
    "route_status",
    "person_xml_emitted",
    "not_emitted_reason",
    "route_edges",
]
CAR_FIELDS = [
    "vehicle_id",
    "origin_id",
    "KEY_CODE",
    "from_sumo_edge_id",
    "shelter_id",
    "shelter_name",
    "to_sumo_edge_id",
    "depart",
]


def build_pedestrian_network(
    osm_path: Path = DEFAULT_OSM,
    output_path: Path = DEFAULT_PED_NET,
    log_path: Path = DEFAULT_NETWORK_LOG,
) -> dict[str, Any]:
    """Create a Scenario C-only SUMO network with pedestrian infrastructure."""
    configure_sumo_environment(require_tools=True)
    netconvert = Path(os.environ["SUMO_HOME"]) / "bin" / "netconvert.exe"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(netconvert),
        "--osm-files",
        str(osm_path),
        "--output-file",
        str(output_path),
        "--geometry.remove",
        "false",
        "--roundabouts.guess",
        "true",
        "--ramps.guess",
        "true",
        "--osm.sidewalks",
        "true",
        "--osm.crossings",
        "true",
        "--sidewalks.guess",
        "true",
        "--sidewalks.guess.from-permissions",
        "true",
        "--crossings.guess",
        "true",
        "--walkingareas",
        "true",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"netconvert failed; see {log_path}")
    return {
        "network": str(output_path),
        "network_sha256": sha256(output_path),
        "log": str(log_path),
        "warning_count": (result.stdout + result.stderr).count("Warning:"),
        "command": command,
    }


def load_sumo_net(path: Path, *, with_internal: bool = False):
    configure_sumo_environment(require_tools=True)
    import sumolib

    return sumolib.net.readNet(str(path), withInternal=with_internal)


def pedestrian_edges(net) -> list[Any]:
    return [
        edge
        for edge in net.getEdges(withInternal=False)
        if edge.allows("pedestrian")
    ]


def largest_pedestrian_component(edges: list[Any]) -> tuple[set[Any], list[Any]]:
    adjacency: dict[Any, set[Any]] = defaultdict(set)
    node_edges: dict[Any, list[Any]] = defaultdict(list)
    for edge in edges:
        start, end = edge.getFromNode(), edge.getToNode()
        adjacency[start].add(end)
        adjacency[end].add(start)
        node_edges[start].append(edge)
        node_edges[end].append(edge)
    remaining = set(adjacency)
    best: set[Any] = set()
    while remaining:
        root = next(iter(remaining))
        component = {root}
        queue = deque([root])
        remaining.remove(root)
        while queue:
            node = queue.popleft()
            for neighbor in adjacency[node]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        if len(component) > len(best):
            best = component
    selected = [
        edge
        for edge in edges
        if edge.getFromNode() in best and edge.getToNode() in best
    ]
    return best, selected


def point_segment_distance(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    fraction = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + fraction * dx), py - (ay + fraction * dy))


def edge_distance(edge: Any, x: float, y: float) -> float:
    shape = edge.getShape(includeJunctions=True)
    return min(
        point_segment_distance(x, y, ax, ay, bx, by)
        for (ax, ay), (bx, by) in zip(shape, shape[1:])
    )


def build_edge_grid(edges: list[Any], cell_size: float = 500.0) -> dict[tuple[int, int], list[Any]]:
    grid: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for edge in edges:
        shape = edge.getShape(includeJunctions=True)
        xs = [point[0] for point in shape]
        ys = [point[1] for point in shape]
        for gx in range(math.floor(min(xs) / cell_size), math.floor(max(xs) / cell_size) + 1):
            for gy in range(math.floor(min(ys) / cell_size), math.floor(max(ys) / cell_size) + 1):
                grid[gx, gy].append(edge)
    return grid


def snap_point(
    net,
    grid: dict[tuple[int, int], list[Any]],
    lon: float,
    lat: float,
    *,
    cell_size: float = 500.0,
) -> tuple[Any, float]:
    x, y = net.convertLonLat2XY(lon, lat)
    gx, gy = math.floor(x / cell_size), math.floor(y / cell_size)
    for radius in range(0, 8):
        candidates: dict[str, Any] = {}
        for ix in range(gx - radius, gx + radius + 1):
            for iy in range(gy - radius, gy + radius + 1):
                for edge in grid.get((ix, iy), []):
                    candidates[edge.getID()] = edge
        if candidates:
            edge, distance = min(
                ((edge, edge_distance(edge, x, y)) for edge in candidates.values()),
                key=lambda item: (item[1], item[0].getID()),
            )
            if distance <= (radius + 1) * cell_size:
                return edge, distance
    raise ValueError(f"no pedestrian edge found near ({lon}, {lat})")


def snap_origins_and_shelters(
    net,
    component_edges: list[Any],
    origins_path: Path,
    shelters_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grid = build_edge_grid(component_edges)
    origins: list[dict[str, Any]] = []
    for row in sorted(read_csv_rows(origins_path), key=lambda item: item["origin_id"]):
        edge, distance = snap_point(net, grid, float(row["lon"]), float(row["lat"]))
        origins.append({**row, "ped_edge_id": edge.getID(), "ped_snap_distance_m": distance})
    shelters: list[dict[str, Any]] = []
    for row in read_csv_rows(shelters_path):
        if str(row.get("is_safe_destination", "")).lower() != "true":
            continue
        edge, distance = snap_point(net, grid, float(row["lon"]), float(row["lat"]))
        shelters.append({**row, "ped_edge_id": edge.getID(), "ped_snap_distance_m": distance})
    if not shelters:
        raise ValueError("no safe pedestrian shelters are available")
    return origins, shelters


def route_walk_candidates(
    net,
    net_path: Path,
    origins: list[dict[str, Any]],
    shelters: list[dict[str, Any]],
    output_dir: Path,
) -> tuple[dict[tuple[str, str], tuple[list[str], float]], dict[str, Any]]:
    """Use SUMO's own router to retain only valid origin-shelter walk routes."""
    configure_sumo_environment(require_tools=True)
    duarouter = Path(os.environ["SUMO_HOME"]) / "bin" / "duarouter.exe"
    input_path = output_dir / "walk_od_candidates.trips.xml"
    routed_path = output_dir / "walk_od_candidates.routed.xml"
    log_path = output_dir / "walk_od_duarouter.log"
    root = ET.Element("routes")
    ET.SubElement(
        root,
        "vType",
        id="routing_pedestrian",
        vClass="pedestrian",
        desiredMaxSpeed="1.00",
    )
    for origin in origins:
        for shelter in shelters:
            person = ET.SubElement(
                root,
                "person",
                id=f"od__{origin['origin_id']}__{shelter['shelter_id']}",
                type="routing_pedestrian",
                depart="0",
            )
            ET.SubElement(
                person,
                "walk",
                **{"from": origin["ped_edge_id"], "to": shelter["ped_edge_id"]},
            )
    ET.indent(root)
    ET.ElementTree(root).write(input_path, encoding="utf-8", xml_declaration=True)
    command = [
        str(duarouter),
        "--net-file",
        str(net_path),
        "--route-files",
        str(input_path),
        "--output-file",
        str(routed_path),
        "--ignore-errors",
        "true",
        "--xml-validation",
        "always",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"duarouter failed; see {log_path}")
    routes: dict[tuple[str, str], tuple[list[str], float]] = {}
    routed_tree = ET.parse(routed_path)
    for person in routed_tree.getroot().findall("person"):
        identifier = person.attrib["id"]
        _, origin_id, shelter_id = identifier.split("__", 2)
        walk = person.find("walk")
        if walk is None or not walk.attrib.get("edges"):
            continue
        edge_ids = walk.attrib["edges"].split()
        distance = sum(net.getEdge(edge_id).getLength() for edge_id in edge_ids)
        routes[(origin_id, shelter_id)] = (edge_ids, distance)
    ET.indent(routed_tree.getroot())
    routed_tree.write(routed_path, encoding="utf-8", xml_declaration=True)
    alternatives_path = routed_path.with_name(routed_path.stem + ".alt.xml")
    if alternatives_path.exists():
        alternatives_path.unlink()
    return routes, {
        "candidate_count": len(origins) * len(shelters),
        "routed_candidate_count": len(routes),
        "unrouted_candidate_count": len(origins) * len(shelters) - len(routes),
        "log": str(log_path),
        "warning_count": (result.stdout + result.stderr).count("Warning:"),
    }


def choose_walk_routes(
    origins: list[dict[str, Any]],
    shelters: list[dict[str, Any]],
    candidate_routes: dict[tuple[str, str], tuple[list[str], float]],
) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for origin in origins:
        candidates: list[tuple[float, str, dict[str, Any], list[str], float]] = []
        for shelter in shelters:
            routed = candidate_routes.get((origin["origin_id"], shelter["shelter_id"]))
            if routed is None:
                continue
            path, cost = routed
            total = float(origin["ped_snap_distance_m"]) + float(cost) + float(shelter["ped_snap_distance_m"])
            candidates.append((total, shelter["shelter_id"], shelter, path, float(cost)))
        if not candidates:
            routes.append({
                "origin_id": origin["origin_id"],
                "KEY_CODE": str(origin["KEY_CODE"]).zfill(10),
                "origin_edge_id": origin["ped_edge_id"],
                "origin_connector_m": f"{float(origin['ped_snap_distance_m']):.3f}",
                "shelter_id": "",
                "shelter_name": "",
                "shelter_edge_id": "",
                "shelter_connector_m": "",
                "network_distance_m": "",
                "total_walk_distance_m": "",
                "route_status": "route_unreachable",
                "route_edge_count": 0,
                "route_edges": "",
            })
            continue
        total, _, shelter, path, cost = min(candidates, key=lambda item: (item[0], item[1]))
        routes.append({
            "origin_id": origin["origin_id"],
            "KEY_CODE": str(origin["KEY_CODE"]).zfill(10),
            "origin_edge_id": origin["ped_edge_id"],
            "origin_connector_m": f"{float(origin['ped_snap_distance_m']):.3f}",
            "shelter_id": shelter["shelter_id"],
            "shelter_name": shelter["name"],
            "shelter_edge_id": shelter["ped_edge_id"],
            "shelter_connector_m": f"{float(shelter['ped_snap_distance_m']):.3f}",
            "network_distance_m": f"{cost:.3f}",
            "total_walk_distance_m": f"{total:.3f}",
            "route_status": "reachable" if total <= MAX_WALK_DISTANCE_M else "distance_limit_exceeded",
            "route_edge_count": len(path),
            "route_edges": " ".join(path),
        })
    return routes


def allocate_households(agent_rows: list[dict[str, str]], non_car_rate: float) -> tuple[list[dict[str, Any]], dict[str, int]]:
    populations = [int(row["total_pop"]) for row in agent_rows]
    total_households = round_half_up(sum(populations) / HOUSEHOLD_SIZE)
    households = allocate_bounded_proportional(populations, total_households, populations)
    non_owner_total = round_half_up(total_households * non_car_rate)
    non_owner = allocate_bounded_proportional(populations, non_owner_total, households)
    rows = []
    for row, all_households, no_car in zip(agent_rows, households, non_owner):
        rows.append({
            "origin_id": row["origin_id"],
            "KEY_CODE": str(row["KEY_CODE"]).zfill(10),
            "total_pop": int(row["total_pop"]),
            "households": all_households,
            "non_owner_households": no_car,
            "car_households": all_households - no_car,
        })
    return rows, {
        "population": sum(populations),
        "households": total_households,
        "non_owner_households": non_owner_total,
        "car_households": total_households - non_owner_total,
    }


def private_assignment_templates(path: Path) -> dict[str, dict[str, str]]:
    templates: dict[str, dict[str, str]] = {}
    for row in read_csv_rows(path):
        if row.get("vehicle_kind") != "private_car":
            continue
        templates.setdefault(row["origin_id"], row)
    return templates


def build_car_assignments(
    household_rows: list[dict[str, Any]], templates: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for origin in household_rows:
        template = templates.get(origin["origin_id"])
        if template is None and origin["car_households"]:
            raise ValueError(f"{origin['origin_id']}: private-car assignment template is missing")
        for index in range(1, origin["car_households"] + 1):
            rows.append({
                "vehicle_id": f"scen_c_{origin['origin_id']}_{index:04d}",
                "origin_id": origin["origin_id"],
                "KEY_CODE": origin["KEY_CODE"],
                "from_sumo_edge_id": template["from_sumo_edge_id"],
                "shelter_id": template["shelter_id"],
                "shelter_name": template["shelter_name"],
                "to_sumo_edge_id": template["to_sumo_edge_id"],
                "depart": "0",
            })
    return rows


def write_car_trips(path: Path, rows: list[dict[str, Any]]) -> None:
    root = ET.Element("routes")
    ET.SubElement(root, "vType", id="scenario_c_car", vClass="passenger")
    for row in rows:
        ET.SubElement(
            root,
            "trip",
            id=row["vehicle_id"],
            type="scenario_c_car",
            depart=row["depart"],
            **{"from": row["from_sumo_edge_id"], "to": row["to_sumo_edge_id"]},
        )
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def build_person_ledger(
    mode_rows: list[dict[str, str]], routes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    route_by_origin = {row["origin_id"]: row for row in routes}
    output: list[dict[str, Any]] = []
    for person in mode_rows:
        if person["assigned_mode"] != "walk":
            continue
        route = route_by_origin[person["origin_id"]]
        speed = WALK_SPEEDS[person["age_group"]]
        emitted = route["route_status"] == "reachable"
        distance = route["total_walk_distance_m"] if route["total_walk_distance_m"] != "" else ""
        output.append({
            "person_id": person["person_id"],
            "origin_id": person["origin_id"],
            "KEY_CODE": str(person["KEY_CODE"]).zfill(10),
            "person_type": person["person_type"],
            "age_group": person["age_group"],
            "walk_speed_mps": f"{speed:.2f}",
            "origin_edge_id": route["origin_edge_id"],
            "shelter_id": route["shelter_id"],
            "shelter_edge_id": route["shelter_edge_id"],
            "total_walk_distance_m": distance,
            "free_flow_walk_time_s": f"{float(distance) / speed:.3f}" if distance else "",
            "route_status": route["route_status"],
            "person_xml_emitted": str(emitted).lower(),
            "not_emitted_reason": "" if emitted else route["route_status"],
            "route_edges": route["route_edges"],
        })
    return output


def write_person_routes(path: Path, rows: list[dict[str, Any]]) -> None:
    root = ET.Element("routes")
    ET.SubElement(root, "vType", id="walk_general", vClass="pedestrian", desiredMaxSpeed="1.00")
    ET.SubElement(root, "vType", id="walk_elderly", vClass="pedestrian", desiredMaxSpeed="0.58")
    for row in rows:
        if row["person_xml_emitted"] != "true":
            continue
        person = ET.SubElement(
            root,
            "person",
            id=row["person_id"],
            type="walk_elderly" if row["age_group"] == "elderly" else "walk_general",
            depart="0",
        )
        ET.SubElement(
            person,
            "walk",
            edges=row["route_edges"],
        )
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def validate_vehicle_edges(net, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        for field in ("from_sumo_edge_id", "to_sumo_edge_id"):
            edge = net.getEdge(row[field])
            if not edge.allows("passenger"):
                raise ValueError(f"{row['vehicle_id']}: {field} does not allow passenger")


def xml_counts(path: Path) -> Counter[str]:
    root = ET.parse(path).getroot()
    return Counter(child.tag for child in root)


def validate_inputs_with_sumo(
    ped_net_path: Path = DEFAULT_PED_NET,
    input_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Run a one-second syntax/insertion check; this is not a Scenario C experiment."""
    configure_sumo_environment(require_tools=True)
    sumo = Path(os.environ["SUMO_HOME"]) / "bin" / "sumo.exe"
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    validation_dir = input_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for scenario in manifest["scenarios"]:
        scenario_id = scenario["scenario_id"]
        scenario_dir = input_dir / scenario_id
        car_xml = scenario_dir / f"scenario_c_{scenario_id}_cars.trips.xml"
        person_xml = scenario_dir / f"scenario_c_{scenario_id}_persons.rou.xml"
        command = [
            str(sumo),
            "--net-file",
            str(ped_net_path),
            "--route-files",
            f"{car_xml},{person_xml}",
            "--begin",
            "0",
            "--end",
            "1",
            "--step-length",
            "1",
            "--xml-validation",
            "always",
            "--no-step-log",
            "true",
            "--duration-log.disable",
            "true",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        log_path = validation_dir / f"{scenario_id}_sumo_input_validation.log"
        log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
        rows.append(
            {
                "scenario_id": scenario_id,
                "returncode": result.returncode,
                "passed": result.returncode == 0,
                "validation_seconds": 1,
                "car_xml_sha256": sha256(car_xml),
                "person_xml_sha256": sha256(person_xml),
                "log": str(log_path),
            }
        )
    output = {
        "validation_type": "one_second_xml_and_insertion_check",
        "full_sumo_run": False,
        "sumo_run_authorized": False,
        "all_passed": all(row["passed"] for row in rows),
        "scenarios": rows,
    }
    (validation_dir / "validation.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not output["all_passed"]:
        raise RuntimeError("one or more Scenario C input validation checks failed")
    return output


def build_inputs(
    *,
    ped_net_path: Path = DEFAULT_PED_NET,
    existing_net_path: Path = DEFAULT_EXISTING_NET,
    ownership_dir: Path = DEFAULT_OWNERSHIP_DIR,
    origins_path: Path = DEFAULT_ORIGINS,
    shelters_path: Path = DEFAULT_SHELTERS,
    scenario_a_assignments_path: Path = DEFAULT_A_ASSIGNMENTS,
    closure_timeline_path: Path = DEFAULT_CLOSURE_TIMELINE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    ped_net = load_sumo_net(ped_net_path)
    existing_net = load_sumo_net(existing_net_path)
    ped_all = pedestrian_edges(ped_net)
    component_nodes, component_edges = largest_pedestrian_component(ped_all)
    normal_ids = {edge.getID() for edge in ped_net.getEdges(withInternal=False)}
    existing_normal_ids = {edge.getID() for edge in existing_net.getEdges(withInternal=False)}
    passenger_ids = {edge.getID() for edge in ped_net.getEdges(withInternal=False) if edge.allows("passenger")}
    existing_passenger_ids = {edge.getID() for edge in existing_net.getEdges(withInternal=False) if edge.allows("passenger")}
    if normal_ids != existing_normal_ids or passenger_ids != existing_passenger_ids:
        raise ValueError("Scenario C network changed the existing normal/passenger edge sets")
    closure_data = json.loads(closure_timeline_path.read_text(encoding="utf-8"))
    closure_edge_ids = {
        edge_id
        for closure in closure_data["closures"]
        for edge_id in closure["closed_sumo_edge_ids"]
    }
    missing_closure_edges = sorted(closure_edge_ids - normal_ids)
    if missing_closure_edges:
        raise ValueError("Scenario C network is missing vehicle closure edges")

    origins, shelters = snap_origins_and_shelters(ped_net, component_edges, origins_path, shelters_path)
    if len(origins) != 405 or len(shelters) != 9:
        raise ValueError("Scenario C expects 405 origins and 9 safe shelters")
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_routes, routing_diagnostics = route_walk_candidates(
        ped_net, ped_net_path, origins, shelters, output_dir
    )
    routes = choose_walk_routes(origins, shelters, candidate_routes)
    if len(routes) != 405:
        raise ValueError("Scenario C expects 405 walk OD rows")
    write_csv(output_dir / "walk_od.csv", ROUTE_FIELDS, routes)

    templates = private_assignment_templates(scenario_a_assignments_path)
    scenario_manifests: list[dict[str, Any]] = []
    for scenario_dir in sorted(path for path in ownership_dir.iterdir() if path.is_dir()):
        scenario_id = scenario_dir.name
        agent_path = scenario_dir / "scenario_c_agent_types.csv"
        mode_path = scenario_dir / "scenario_c_mode_ledger.csv"
        agent_rows = read_csv_rows(agent_path)
        mode_rows = read_csv_rows(mode_path)
        if not agent_rows or not mode_rows:
            raise ValueError(f"{scenario_id}: formal ownership inputs are empty")
        non_car_rate = float(agent_rows[0]["non_car_rate"])
        household_rows, household_counts = allocate_households(agent_rows, non_car_rate)
        car_rows = build_car_assignments(household_rows, templates)
        person_rows = build_person_ledger(mode_rows, routes)

        destination = output_dir / scenario_id
        destination.mkdir(parents=True, exist_ok=True)
        household_fields = list(household_rows[0])
        write_csv(destination / "household_car_allocation.csv", household_fields, household_rows)
        write_csv(destination / "car_assignment.csv", CAR_FIELDS, car_rows)
        write_csv(destination / "walk_person_ledger.csv", PERSON_FIELDS, person_rows)
        car_xml = destination / f"scenario_c_{scenario_id}_cars.trips.xml"
        person_xml = destination / f"scenario_c_{scenario_id}_persons.rou.xml"
        write_car_trips(car_xml, car_rows)
        write_person_routes(person_xml, person_rows)
        validate_vehicle_edges(ped_net, car_rows)

        status_counts = Counter(row["route_status"] for row in person_rows)
        age_counts = Counter(row["age_group"] for row in person_rows)
        emitted = sum(row["person_xml_emitted"] == "true" for row in person_rows)
        expected_walk = sum(row["assigned_mode"] == "walk" for row in mode_rows)
        if len(person_rows) != expected_walk or sum(status_counts.values()) != expected_walk:
            raise AssertionError(f"{scenario_id}: pedestrian accounting does not close")
        if len(car_rows) != household_counts["car_households"]:
            raise AssertionError(f"{scenario_id}: vehicle accounting does not close")
        if xml_counts(car_xml)["trip"] != len(car_rows) or xml_counts(person_xml)["person"] != emitted:
            raise AssertionError(f"{scenario_id}: XML accounting does not close")
        scenario_manifests.append({
            "scenario_id": scenario_id,
            "non_car_rate": non_car_rate,
            "ownership_role": agent_rows[0]["ownership_role"],
            "household_counts": household_counts,
            "walk_people": expected_walk,
            "walk_emitted": emitted,
            "walk_status_counts": dict(sorted(status_counts.items())),
            "walk_age_counts": dict(sorted(age_counts.items())),
            "car_trip_count": len(car_rows),
            "input_sha256": {"agent_types": sha256(agent_path), "mode_ledger": sha256(mode_path)},
            "output_sha256": {path.name: sha256(path) for path in sorted(destination.iterdir()) if path.is_file()},
        })

    manifest = {
        "scenario": "C",
        "stage": "S5_input_generation_only",
        "sumo_run_authorized": False,
        "full_sumo_run_executed": False,
        "pedestrian_network": {
            "path": str(ped_net_path),
            "sha256": sha256(ped_net_path),
            "normal_edge_count": len(normal_ids),
            "pedestrian_normal_edge_count": len(ped_all),
            "largest_component_node_count": len(component_nodes),
            "largest_component_edge_count": len(component_edges),
            "normal_edge_set_matches_existing": True,
            "passenger_edge_set_matches_existing": True,
            "vehicle_closure_edge_count": len(closure_edge_ids),
            "vehicle_closure_edges_missing": 0,
        },
        "walking": {
            "origin_count": len(origins),
            "safe_shelter_count": len(shelters),
            "max_walk_distance_m": MAX_WALK_DISTANCE_M,
            "general_speed_mps": WALK_SPEEDS["non_elderly"],
            "elderly_speed_mps": WALK_SPEEDS["elderly"],
            "elderly_low_speed_sensitivity_mps": LOW_ELDERLY_SPEED,
            "flood_policies": {
                "primary": "W-FLOOD-STRICT",
                "sensitivity": "W-FLOOD-WADE",
                "dynamic_application_deferred_to": "S7_after_PRE-8",
            },
            "od_status_counts": dict(sorted(Counter(row["route_status"] for row in routes).items())),
            "routing_diagnostics": routing_diagnostics,
        },
        "vehicle_model": {
            "household_size": HOUSEHOLD_SIZE,
            "one_evacuation_car_per_owner_household": True,
            "rescue_cars_included": False,
            "buses_included": False,
        },
        "inputs": {
            "origins": {"path": str(origins_path), "sha256": sha256(origins_path)},
            "shelters": {"path": str(shelters_path), "sha256": sha256(shelters_path)},
            "scenario_a_assignment_template": {"path": str(scenario_a_assignments_path), "sha256": sha256(scenario_a_assignments_path)},
            "ownership_dir": str(ownership_dir),
            "closure_timeline": {"path": str(closure_timeline_path), "sha256": sha256(closure_timeline_path)},
        },
        "scenarios": scenario_manifests,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build-network", "build-inputs", "validate-inputs"])
    parser.add_argument("--osm", type=Path, default=DEFAULT_OSM)
    parser.add_argument("--ped-net", type=Path, default=DEFAULT_PED_NET)
    parser.add_argument("--network-log", type=Path, default=DEFAULT_NETWORK_LOG)
    parser.add_argument("--existing-net", type=Path, default=DEFAULT_EXISTING_NET)
    parser.add_argument("--ownership-dir", type=Path, default=DEFAULT_OWNERSHIP_DIR)
    parser.add_argument("--origins", type=Path, default=DEFAULT_ORIGINS)
    parser.add_argument("--shelters", type=Path, default=DEFAULT_SHELTERS)
    parser.add_argument("--scenario-a-assignments", type=Path, default=DEFAULT_A_ASSIGNMENTS)
    parser.add_argument("--closure-timeline", type=Path, default=DEFAULT_CLOSURE_TIMELINE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "build-network":
        result = build_pedestrian_network(args.osm, args.ped_net, args.network_log)
    elif args.command == "build-inputs":
        result = build_inputs(
            ped_net_path=args.ped_net,
            existing_net_path=args.existing_net,
            ownership_dir=args.ownership_dir,
            origins_path=args.origins,
            shelters_path=args.shelters,
            scenario_a_assignments_path=args.scenario_a_assignments,
            closure_timeline_path=args.closure_timeline,
            output_dir=args.output_dir,
        )
    else:
        result = validate_inputs_with_sumo(args.ped_net, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
