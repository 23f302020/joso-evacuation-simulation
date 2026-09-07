"""Build Scenario C static snapshots with inputs aligned to the future SUMO run."""

from __future__ import annotations

import argparse
import glob
import heapq
import json
import math
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

import config
from p2_sumo_env import configure_sumo_environment
from scenario_c_car_walk import read_csv_rows, sha256, write_csv
from scenario_c_routes import load_sumo_net, private_assignment_templates


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
REGION_DIR = PROGRAM_DIR / "output" / "sumo" / "regions" / "08211"
SCENARIO_C_DIR = REGION_DIR / "experiments" / "scenario_c"
PED_NET = SCENARIO_C_DIR / "network" / "08211_ped.net.xml"
ROUTE_INPUT_DIR = SCENARIO_C_DIR / "inputs" / "routes_20260826"
OWNERSHIP_DIR = SCENARIO_C_DIR / "inputs" / "ownership_sensitivity_20260826"
CLOSURE_TIMELINE = REGION_DIR / "derived" / "closure_timeline_sumo.json"
A_ASSIGNMENTS = REGION_DIR / "derived" / "scenario_a_vehicle_assignments.csv"
OUTPUT_DIR = SCENARIO_C_DIR / "static_alignment_20260826"
GML_DIR = (SCRIPT_DIR / config.GML_DIR).resolve()
N03_PATH = (SCRIPT_DIR / config.N03_SHP_PATH).resolve()

CRS_METRIC = "EPSG:6690"
BREACH_LON = 139.9633
BREACH_LAT = 36.0885
PROGRESS = [5.2 / 141.5, 17.2 / 141.5, 29.2 / 141.5, 41.2 / 141.5,
            53.2 / 141.5, 65.2 / 141.5, 77.2 / 141.5, 1.0]
CLOSED_TRAVEL_TIME = 1_000_000_000.0
MAX_WALK_DISTANCE_M = 2000.0

SNAPSHOT_FIELDS = [
    "mode", "policy", "time_id", "sim_time_sec", "origin_id", "KEY_CODE",
    "from_edge_id", "shelter_id", "to_edge_id", "route_status",
    "network_distance_m", "connector_distance_m", "total_distance_m",
    "general_free_flow_time_s", "elderly_free_flow_time_s",
    "route_edge_count", "closed_edge_hit_count", "shallow_edge_count", "route_edges",
]
SUMMARY_FIELDS = [
    "scenario_id", "mode", "policy", "time_id", "sim_time_sec", "unit",
    "total_count", "reachable_count", "distance_limit_exceeded_count",
    "route_unreachable_count", "reachable_rate", "reachable_mean_distance_m",
]


def load_depth_one_polygons(gml_dir: Path) -> gpd.GeoDataFrame:
    """Read A31a waterDepth=1 polygons without changing Phase 1 configuration."""
    ns = {
        "gml": "http://schemas.opengis.net/gml/3.2.1",
        "ksj": "http://nlftp.mlit.go.jp/ksj/schemas/ksj-app",
        "xlink": "http://www.w3.org/1999/xlink",
    }
    rows: list[dict[str, Any]] = []
    paths = [
        path
        for path in glob.glob(str(gml_dir / "**" / "*.xml"), recursive=True)
        if "META" not in Path(path).name.upper()
    ]
    for path in paths:
        tree = ET.parse(path)
        root = tree.getroot()
        curves: dict[str, list[tuple[float, float]]] = {}
        for curve in root.iter(f"{{{ns['gml']}}}Curve"):
            curve_id = curve.get(f"{{{ns['gml']}}}id")
            positions = curve.find(f".//{{{ns['gml']}}}posList")
            if curve_id is None or positions is None or not positions.text:
                continue
            values = list(map(float, positions.text.split()))
            curves[curve_id] = [
                (values[index + 1], values[index])
                for index in range(0, len(values) - 1, 2)
            ]
        surfaces: dict[str, Polygon] = {}
        for surface in root.iter(f"{{{ns['gml']}}}Surface"):
            surface_id = surface.get(f"{{{ns['gml']}}}id")
            ring = surface.find(
                f".//{{{ns['gml']}}}exterior/{{{ns['gml']}}}Ring"
            )
            if surface_id is None or ring is None:
                continue
            coordinates: list[tuple[float, float]] = []
            for member in ring.findall(f"{{{ns['gml']}}}curveMember"):
                reference = member.get(f"{{{ns['xlink']}}}href", "").lstrip("#")
                coordinates.extend(curves.get(reference, []))
            if len(coordinates) >= 3:
                surfaces[surface_id] = Polygon(coordinates)
        for tag_name in ("PlanScale", "MaximumScale"):
            for feature in root.iter(f"{{{ns['ksj']}}}{tag_name}"):
                bounds = feature.find(f"{{{ns['ksj']}}}bounds")
                depth = feature.find(f"{{{ns['ksj']}}}waterDepth")
                if bounds is None or depth is None or int(depth.text or 0) != 1:
                    continue
                reference = bounds.get(f"{{{ns['xlink']}}}href", "").lstrip("#")
                if reference in surfaces:
                    rows.append({"waterDepth": 1, "geometry": surfaces[reference]})
    if not rows:
        raise ValueError("A31a waterDepth=1 polygons were not found")
    return gpd.GeoDataFrame(rows, crs="EPSG:6668")


def clip_to_joso(polygons: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    boundary = gpd.read_file(N03_PATH, engine="pyogrio")
    joso = boundary[boundary["N03_007"] == config.JOSO_CODE].to_crs(polygons.crs)
    if joso.empty:
        raise ValueError("Joso boundary was not found")
    union = joso.geometry.union_all()
    selected = polygons[polygons.geometry.intersects(union)].copy()
    selected["geometry"] = selected.geometry.intersection(union)
    return selected[~selected.geometry.is_empty].copy()


def pedestrian_edge_geodataframe(net) -> gpd.GeoDataFrame:
    projection = net.getGeoProj()
    offset_x, offset_y = net.getLocationOffset()
    rows = []
    for edge in net.getEdges(withInternal=False):
        if not edge.allows("pedestrian"):
            continue
        lon_lat = [
            projection(x - offset_x, y - offset_y, inverse=True)
            for x, y in edge.getShape(includeJunctions=True)
        ]
        rows.append({"edge_id": edge.getID(), "geometry": LineString(lon_lat)})
    return gpd.GeoDataFrame(rows, crs="EPSG:4326").to_crs(CRS_METRIC)


def build_pedestrian_flood_timeline(
    net,
    vehicle_closure_path: Path = CLOSURE_TIMELINE,
) -> dict[str, Any]:
    depth_one = clip_to_joso(load_depth_one_polygons(GML_DIR)).to_crs(CRS_METRIC)
    breach = gpd.GeoSeries([Point(BREACH_LON, BREACH_LAT)], crs="EPSG:4326").to_crs(CRS_METRIC).iloc[0]
    distances = depth_one.geometry.centroid.distance(breach)
    edge_gdf = pedestrian_edge_geodataframe(net)
    pedestrian_ids = set(edge_gdf["edge_id"])
    vehicle_data = json.loads(vehicle_closure_path.read_text(encoding="utf-8"))
    timeline = []
    for closure, progress in zip(vehicle_data["closures"], PROGRESS):
        threshold = distances.quantile(progress)
        selected = depth_one[distances <= threshold]
        shallow_union = selected.geometry.union_all()
        shallow_ids = set(edge_gdf.loc[edge_gdf.geometry.intersects(shallow_union), "edge_id"])
        deep_ids = set(closure["closed_sumo_edge_ids"]) & pedestrian_ids
        wade_shallow = shallow_ids - deep_ids
        strict_closed = shallow_ids | deep_ids
        timeline.append(
            {
                "time_id": closure["time_id"],
                "source_timestamp": closure["source_timestamp"],
                "sim_time_sec": int(closure["sim_time_sec"]),
                "progress_ratio": progress,
                "depth_one_polygon_count": int(len(selected)),
                "wade_closed_edge_ids": sorted(deep_ids),
                "wade_shallow_edge_ids": sorted(wade_shallow),
                "strict_closed_edge_ids": sorted(strict_closed),
            }
        )
    return {
        "method": "A31a_depth1_BP030_distance_quantile_plus_existing_depth_ge2_closure",
        "observed_depth_timeline": False,
        "depth_one_source_polygon_count": int(len(depth_one)),
        "timeline": timeline,
    }


def write_weight_file(path: Path, timeline: list[dict[str, Any]], net, policy: str) -> None:
    xsi = "http://www.w3.org/2001/XMLSchema-instance"
    ET.register_namespace("xsi", xsi)
    root = ET.Element(
        "meandata",
        {f"{{{xsi}}}noNamespaceSchemaLocation": "http://sumo.dlr.de/xsd/meandata_file.xsd"},
    )
    for index, row in enumerate(timeline):
        end = timeline[index + 1]["sim_time_sec"] if index + 1 < len(timeline) else 21601
        interval = ET.SubElement(
            root,
            "interval",
            id=f"{policy}_{row['time_id']}",
            begin=str(row["sim_time_sec"]),
            end=str(end),
        )
        if policy == "vehicle":
            closed = row["vehicle_closed_edge_ids"]
            shallow: list[str] = []
        elif policy == "strict":
            closed = row["strict_closed_edge_ids"]
            shallow = []
        elif policy == "wade":
            closed = row["wade_closed_edge_ids"]
            shallow = row["wade_shallow_edge_ids"]
        else:
            raise ValueError(policy)
        for edge_id in closed:
            ET.SubElement(interval, "edge", id=edge_id, traveltime=f"{CLOSED_TRAVEL_TIME:.1f}")
        for edge_id in shallow:
            travel_time = net.getEdge(edge_id).getLength() / 0.60
            ET.SubElement(interval, "edge", id=edge_id, traveltime=f"{travel_time:.6f}")
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def write_routing_demand(
    path: Path,
    mode: str,
    times: list[dict[str, Any]],
    car_od: dict[str, dict[str, str]],
    walk_od: dict[str, dict[str, str]],
) -> None:
    root = ET.Element("routes")
    if mode == "car":
        ET.SubElement(root, "vType", id="static_car", vClass="passenger")
        for time in times:
            for origin_id, row in sorted(car_od.items()):
                ET.SubElement(
                    root, "trip", id=f"car__{time['time_id']}__{origin_id}",
                    type="static_car", depart=str(time["sim_time_sec"]),
                    **{"from": row["from_sumo_edge_id"], "to": row["to_sumo_edge_id"]},
                )
    else:
        ET.SubElement(root, "vType", id="static_walk", vClass="pedestrian", desiredMaxSpeed="1.00")
        for time in times:
            for origin_id, row in sorted(walk_od.items()):
                if not row["shelter_edge_id"]:
                    continue
                person = ET.SubElement(
                    root, "person", id=f"walk__{time['time_id']}__{origin_id}",
                    type="static_walk", depart=str(time["sim_time_sec"]),
                )
                ET.SubElement(
                    person,
                    "personTrip",
                    **{"from": row["origin_edge_id"], "to": row["shelter_edge_id"]},
                )
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def run_duarouter(net_path: Path, demand_path: Path, weight_path: Path, output_path: Path, log_path: Path) -> None:
    configure_sumo_environment(require_tools=True)
    executable = Path(os.environ["SUMO_HOME"]) / "bin" / "duarouter.exe"
    command = [
        str(executable), "--net-file", str(net_path), "--route-files", str(demand_path),
        "--weight-files", str(weight_path), "--weight-attribute", "traveltime",
        "--output-file", str(output_path), "--ignore-errors", "true",
        "--routing-algorithm", "dijkstra", "--weight-period", "1",
        "--weights.expand", "true", "--max-traveltime", "1000000",
        "--write-costs", "true",
        "--xml-validation", "always",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"duarouter failed; see {log_path}")
    tree = ET.parse(output_path)
    ET.indent(tree.getroot())
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    alternatives = output_path.with_name(output_path.stem + ".alt.xml")
    if alternatives.exists():
        alternatives.unlink()


def parse_routed_edges(path: Path, mode: str) -> dict[tuple[str, str], list[str]]:
    routes: dict[tuple[str, str], list[str]] = {}
    root = ET.parse(path).getroot()
    if mode == "car":
        for vehicle in root.findall("vehicle"):
            _, time_id, origin_id = vehicle.attrib["id"].split("__", 2)
            route = vehicle.find("route")
            if route is not None and route.attrib.get("edges"):
                routes[(time_id, origin_id)] = route.attrib["edges"].split()
    else:
        for person in root.findall("person"):
            _, time_id, origin_id = person.attrib["id"].split("__", 2)
            walk = person.find("walk")
            if walk is not None and walk.attrib.get("edges"):
                routes[(time_id, origin_id)] = walk.attrib["edges"].split()
    return routes


def build_intermodal_graph(
    net_path: Path,
    demand_path: Path,
) -> tuple[dict[str, float], dict[str, list[str]], dict[str, str]]:
    """Read SUMO's pedestrian forward/backward/crossing connectivity graph."""
    configure_sumo_environment(require_tools=True)
    executable = Path(os.environ["SUMO_HOME"]) / "bin" / "duarouter.exe"
    with tempfile.TemporaryDirectory(prefix="scenario_c_intermodal_") as temp_text:
        temp_dir = Path(temp_text)
        route_output = temp_dir / "probe_routes.xml"
        graph_output = temp_dir / "intermodal_network.xml"
        command = [
            str(executable), "--net-file", str(net_path), "--route-files", str(demand_path),
            "--output-file", str(route_output), "--intermodal-network-output", str(graph_output),
            "--end", "790", "--ignore-errors", "true", "--xml-validation", "always",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError("failed to export SUMO intermodal network")
        lengths: dict[str, float] = {}
        raw_successors: dict[str, list[str]] = {}
        base_edges: dict[str, str] = {}
        for _, element in ET.iterparse(graph_output, events=("end",)):
            if element.tag != "edge":
                continue
            line = element.attrib.get("line")
            if line not in {"!ped", "!connector"}:
                element.clear()
                continue
            node_id = element.attrib["id"]
            lengths[node_id] = float(element.attrib.get("length", 0))
            raw_successors[node_id] = element.attrib.get("successors", "").split()
            for suffix in ("_fwd-1.00", "_bwd-1.00"):
                if node_id.endswith(suffix):
                    base_edges[node_id] = node_id[: -len(suffix)]
                    break
            element.clear()
    valid = set(lengths)
    reverse: dict[str, list[str]] = {node_id: [] for node_id in valid}
    for node_id, successors in raw_successors.items():
        for successor in successors:
            if successor in valid:
                reverse[successor].append(node_id)
    return lengths, reverse, base_edges


def route_walk_intermodal(
    lengths: dict[str, float],
    reverse: dict[str, list[str]],
    base_edges: dict[str, str],
    walk_od: dict[str, dict[str, str]],
    times: list[dict[str, Any]],
    policy: str,
) -> dict[tuple[str, str], list[str]]:
    """Route fixed pedestrian OD on SUMO's exported intermodal graph."""
    routes: dict[tuple[str, str], list[str]] = {}
    groups: dict[str, list[str]] = {}
    for origin_id, row in walk_od.items():
        if row["shelter_edge_id"]:
            groups.setdefault(row["shelter_edge_id"], []).append(origin_id)
    for time in times:
        closed = set(time["strict_closed_edge_ids"] if policy == "strict" else time["wade_closed_edge_ids"])
        shallow = set() if policy == "strict" else set(time["wade_shallow_edge_ids"])
        blocked_nodes = {node_id for node_id, edge_id in base_edges.items() if edge_id in closed}
        for shelter_edge, origin_ids in groups.items():
            if shelter_edge in closed:
                continue
            goal = f"{shelter_edge}_arrival_connector"
            if goal not in lengths:
                continue
            targets: dict[str, list[str]] = {}
            unresolved: set[str] = set()
            for origin_id in origin_ids:
                edge_id = walk_od[origin_id]["origin_edge_id"]
                if edge_id in closed:
                    continue
                has_start = False
                for direction in ("fwd", "bwd"):
                    node_id = f"{edge_id}_{direction}-1.00"
                    if node_id in lengths:
                        targets.setdefault(node_id, []).append(origin_id)
                        has_start = True
                if has_start:
                    unresolved.add(origin_id)
            distance = {goal: 0.0}
            next_node: dict[str, str] = {}
            heap = [(0.0, goal)]
            chosen: dict[str, str] = {}
            while heap and unresolved:
                cost, node_id = heapq.heappop(heap)
                if cost != distance.get(node_id):
                    continue
                for origin_id in targets.get(node_id, []):
                    if origin_id in unresolved:
                        chosen[origin_id] = node_id
                        unresolved.remove(origin_id)
                for predecessor in reverse.get(node_id, []):
                    if predecessor in blocked_nodes:
                        continue
                    base_edge = base_edges.get(predecessor)
                    factor = 1 / 0.60 if base_edge in shallow else 1.0
                    candidate = cost + lengths[predecessor] * factor
                    if candidate < distance.get(predecessor, math.inf):
                        distance[predecessor] = candidate
                        next_node[predecessor] = node_id
                        heapq.heappush(heap, (candidate, predecessor))
            for origin_id, start in chosen.items():
                node_ids = []
                current = start
                seen = set()
                while current != goal and current not in seen:
                    seen.add(current)
                    node_ids.append(current)
                    if current not in next_node:
                        node_ids = []
                        break
                    current = next_node[current]
                edge_ids = []
                for node_id in node_ids:
                    edge_id = base_edges.get(node_id)
                    if (
                        edge_id
                        and not edge_id.startswith(":")
                        and (not edge_ids or edge_ids[-1] != edge_id)
                    ):
                        edge_ids.append(edge_id)
                if edge_ids:
                    routes[(time["time_id"], origin_id)] = edge_ids
    return routes


def build_snapshots(
    net,
    mode: str,
    policy: str,
    times: list[dict[str, Any]],
    routed: dict[tuple[str, str], list[str]],
    car_od: dict[str, dict[str, str]],
    walk_od: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    output = []
    origins = car_od if mode == "car" else walk_od
    for time in times:
        if policy == "vehicle":
            closed = set(time["vehicle_closed_edge_ids"])
            shallow: set[str] = set()
        elif policy == "strict":
            closed = set(time["strict_closed_edge_ids"])
            shallow = set()
        else:
            closed = set(time["wade_closed_edge_ids"])
            shallow = set(time["wade_shallow_edge_ids"])
        for origin_id, od in sorted(origins.items()):
            edge_ids = routed.get((time["time_id"], origin_id), [])
            closed_hits = closed.intersection(edge_ids)
            shallow_hits = shallow.intersection(edge_ids)
            if not edge_ids or closed_hits:
                status = "route_unreachable"
            else:
                status = "reachable"
            network_distance = sum(net.getEdge(edge_id).getLength() for edge_id in edge_ids) if edge_ids else math.nan
            connector = 0.0 if mode == "car" else float(od["origin_connector_m"] or 0) + float(od["shelter_connector_m"] or 0)
            total_distance = network_distance + connector if edge_ids else math.nan
            if mode == "walk" and status == "reachable" and total_distance > MAX_WALK_DISTANCE_M:
                status = "distance_limit_exceeded"
            general_time = math.nan
            elderly_time = math.nan
            if edge_ids:
                if mode == "car":
                    general_time = sum(net.getEdge(edge_id).getLength() / net.getEdge(edge_id).getSpeed() for edge_id in edge_ids)
                else:
                    dry_length = sum(net.getEdge(edge_id).getLength() for edge_id in edge_ids if edge_id not in shallow)
                    shallow_length = sum(net.getEdge(edge_id).getLength() for edge_id in edge_ids if edge_id in shallow)
                    general_time = dry_length / 1.00 + shallow_length / 0.60
                    elderly_time = dry_length / 0.58 + shallow_length / (0.58 * 0.60)
            output.append({
                "mode": mode, "policy": policy, "time_id": time["time_id"],
                "sim_time_sec": time["sim_time_sec"], "origin_id": origin_id,
                "KEY_CODE": od["KEY_CODE"],
                "from_edge_id": od["from_sumo_edge_id"] if mode == "car" else od["origin_edge_id"],
                "shelter_id": od["shelter_id"],
                "to_edge_id": od["to_sumo_edge_id"] if mode == "car" else od["shelter_edge_id"],
                "route_status": status,
                "network_distance_m": "" if math.isnan(network_distance) else f"{network_distance:.3f}",
                "connector_distance_m": f"{connector:.3f}",
                "total_distance_m": "" if math.isnan(total_distance) else f"{total_distance:.3f}",
                "general_free_flow_time_s": "" if math.isnan(general_time) else f"{general_time:.3f}",
                "elderly_free_flow_time_s": "" if math.isnan(elderly_time) else f"{elderly_time:.3f}",
                "route_edge_count": len(edge_ids), "closed_edge_hit_count": len(closed_hits),
                "shallow_edge_count": len(shallow_hits), "route_edges": " ".join(edge_ids),
            })
    return output


def summarize(
    snapshots: list[dict[str, Any]],
    ownership_dir: Path = OWNERSHIP_DIR,
    routes_dir: Path = ROUTE_INPUT_DIR,
) -> list[dict[str, Any]]:
    by_key = {(row["mode"], row["policy"], row["time_id"], row["origin_id"]): row for row in snapshots}
    output = []
    for scenario_dir in sorted(path for path in ownership_dir.iterdir() if path.is_dir()):
        scenario_id = scenario_dir.name
        agents = read_csv_rows(scenario_dir / "scenario_c_agent_types.csv")
        car_alloc = {row["origin_id"]: int(row["car_households"]) for row in read_csv_rows(routes_dir / scenario_id / "household_car_allocation.csv")}
        walk_alloc = {
            row["origin_id"]: int(row["type3_no_car_non_elderly_pop"]) + int(row["type4_no_car_elderly_pop"])
            for row in agents
        }
        for mode, policy in (("car", "vehicle"), ("walk", "strict"), ("walk", "wade")):
            allocations = car_alloc if mode == "car" else walk_alloc
            for time_id in [f"t{index}" for index in range(8)]:
                counts = Counter()
                distance_sum = 0.0
                for origin_id, count in allocations.items():
                    row = by_key[(mode, policy, time_id, origin_id)]
                    counts[row["route_status"]] += count
                    if row["route_status"] == "reachable":
                        distance_sum += float(row["total_distance_m"]) * count
                total = sum(allocations.values())
                reachable = counts["reachable"]
                sample = by_key[(mode, policy, time_id, next(iter(allocations)))]
                output.append({
                    "scenario_id": scenario_id, "mode": mode, "policy": policy,
                    "time_id": time_id, "sim_time_sec": sample["sim_time_sec"],
                    "unit": "vehicles" if mode == "car" else "persons",
                    "total_count": total, "reachable_count": reachable,
                    "distance_limit_exceeded_count": counts["distance_limit_exceeded"],
                    "route_unreachable_count": counts["route_unreachable"],
                    "reachable_rate": f"{reachable / total:.9f}" if total else "",
                    "reachable_mean_distance_m": f"{distance_sum / reachable:.3f}" if reachable else "",
                })
    return output


def build_alignment(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    net = load_sumo_net(PED_NET)
    vehicle_data = json.loads(CLOSURE_TIMELINE.read_text(encoding="utf-8"))
    pedestrian_data = build_pedestrian_flood_timeline(net)
    pedestrian_path = output_dir / "pedestrian_flood_timeline.json"
    pedestrian_path.write_text(json.dumps(pedestrian_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    vehicle_by_time = {row["time_id"]: row for row in vehicle_data["closures"]}
    times = []
    for row in pedestrian_data["timeline"]:
        times.append({**row, "vehicle_closed_edge_ids": vehicle_by_time[row["time_id"]]["closed_sumo_edge_ids"]})
    car_od = private_assignment_templates(A_ASSIGNMENTS)
    walk_od = {row["origin_id"]: row for row in read_csv_rows(ROUTE_INPUT_DIR / "walk_od.csv")}
    if len(car_od) != 405 or len(walk_od) != 405:
        raise ValueError("aligned static analysis requires 405 car and walk origins")

    all_snapshots = []
    walk_demand: Path | None = None
    for mode, policy in (("car", "vehicle"),):
        demand = output_dir / f"{mode}_{policy}_static_demand.xml"
        weights = output_dir / f"{mode}_{policy}_static_weights.xml"
        routed = output_dir / f"{mode}_{policy}_static_routed.xml"
        log = output_dir / f"{mode}_{policy}_duarouter.log"
        write_routing_demand(demand, mode, times, car_od, walk_od)
        write_weight_file(weights, times, net, policy)
        run_duarouter(PED_NET, demand, weights, routed, log)
        route_map = parse_routed_edges(routed, mode)
        all_snapshots.extend(build_snapshots(net, mode, policy, times, route_map, car_od, walk_od))

    walk_demand = output_dir / "walk_intermodal_probe_demand.xml"
    write_routing_demand(walk_demand, "walk", times, car_od, walk_od)
    lengths, reverse, base_edges = build_intermodal_graph(PED_NET, walk_demand)
    for policy in ("strict", "wade"):
        route_map = route_walk_intermodal(
            lengths, reverse, base_edges, walk_od, times, policy
        )
        all_snapshots.extend(
            build_snapshots(net, "walk", policy, times, route_map, car_od, walk_od)
        )

    for obsolete_name in (
        "walk_strict_duarouter.log", "walk_strict_static_demand.xml",
        "walk_strict_static_routed.xml", "walk_strict_static_weights.xml",
        "walk_wade_duarouter.log", "walk_wade_static_demand.xml",
        "walk_wade_static_routed.xml", "walk_wade_static_weights.xml",
        "intermodal_probe_routes.xml", "intermodal_probe_routes.alt.xml",
        "intermodal_network.xml",
    ):
        obsolete = output_dir / obsolete_name
        if obsolete.exists():
            obsolete.unlink()

    write_csv(output_dir / "static_route_snapshots.csv", SNAPSHOT_FIELDS, all_snapshots)
    summaries = summarize(all_snapshots)
    write_csv(output_dir / "static_summary.csv", SUMMARY_FIELDS, summaries)

    matrix = [
        {"condition": "region", "static": "08211 Joso", "sumo": "08211 Joso", "classification": "identical"},
        {"condition": "origins", "static": "405", "sumo": "405", "classification": "identical"},
        {"condition": "population", "static": "21539", "sumo": "21539", "classification": "identical"},
        {"condition": "ownership_sensitivity", "static": "10/15/20%", "sumo": "10/15/20%", "classification": "identical"},
        {"condition": "safe_shelters", "static": "9", "sumo": "9", "classification": "identical"},
        {"condition": "OD", "static": "S5 fixed OD", "sumo": "S5 fixed OD", "classification": "identical"},
        {"condition": "closure_times", "static": "t0-t7", "sumo": "t0-t7", "classification": "identical"},
        {"condition": "traffic_interaction", "static": "none", "sumo": "enabled", "classification": "method_specific"},
        {"condition": "time_evolution", "static": "independent snapshots", "sumo": "continuous", "classification": "method_specific"},
    ]
    write_csv(output_dir / "alignment_matrix.csv", ["condition", "static", "sumo", "classification"], matrix)
    common = {
        "scenario": "C", "region_code": "08211", "origin_count": 405,
        "population": 21539, "safe_shelter_count": 9,
        "ownership_scenarios": ["non_car_10pct", "non_car_15pct", "non_car_20pct"],
        "time_ids": [f"t{index}" for index in range(8)],
        "static_definition": "independent_route_snapshot_without_traffic_interaction",
        "sumo_run_authorized": False, "full_sumo_run_executed": False,
    }
    (output_dir / "common_conditions_manifest.json").write_text(json.dumps(common, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    expected_rows = 405 * 8 * 3
    if len(all_snapshots) != expected_rows or len(summaries) != 3 * 3 * 8:
        raise AssertionError("static output row accounting does not close")
    for row in summaries:
        if int(row["reachable_count"]) + int(row["distance_limit_exceeded_count"]) + int(row["route_unreachable_count"]) != int(row["total_count"]):
            raise AssertionError("static summary accounting does not close")
    strict_superset_wade = all(
        set(row["wade_closed_edge_ids"]) | set(row["wade_shallow_edge_ids"])
        == set(row["strict_closed_edge_ids"])
        and not set(row["wade_closed_edge_ids"]) & set(row["wade_shallow_edge_ids"])
        for row in times
    )
    reachable_closed_edge_hit_count = sum(
        int(row["closed_edge_hit_count"])
        for row in all_snapshots
        if row["route_status"] == "reachable"
    )
    strict_walk = {
        (row["time_id"], row["origin_id"]): row
        for row in all_snapshots
        if row["mode"] == "walk" and row["policy"] == "strict"
    }
    wade_walk = {
        (row["time_id"], row["origin_id"]): row
        for row in all_snapshots
        if row["mode"] == "walk" and row["policy"] == "wade"
    }
    walk_policy_status_difference_count = sum(
        strict_walk[key]["route_status"] != wade_walk[key]["route_status"]
        for key in strict_walk
    )
    walk_policy_route_difference_count = sum(
        strict_walk[key]["route_edges"] != wade_walk[key]["route_edges"]
        for key in strict_walk
    )
    if not strict_superset_wade:
        raise AssertionError("STRICT closure set must equal WADE closed plus shallow sets")
    if reachable_closed_edge_hit_count:
        raise AssertionError("reachable route intersects a closed edge")
    manifest = {
        "stage": "S6_static_alignment", "sumo_run_authorized": False,
        "full_sumo_run_executed": False,
        "snapshot_row_count": len(all_snapshots), "summary_row_count": len(summaries),
        "pedestrian_depth_timeline_is_scenario_assumption": True,
        "pedestrian_router": "SUMO_intermodal_graph_dijkstra",
        "inputs": {
            "ped_net": sha256(PED_NET), "route_manifest": sha256(ROUTE_INPUT_DIR / "manifest.json"),
            "vehicle_closure_timeline": sha256(CLOSURE_TIMELINE),
            "car_od_template": sha256(A_ASSIGNMENTS),
        },
        "output_sha256": {
            path.name: sha256(path)
            for path in sorted(output_dir.iterdir())
            if path.is_file() and path.name != "manifest.json"
        },
        "validation": {
            "origin_count": 405, "time_count": 8, "scenario_count": 3,
            "summary_accounting_closed": True,
            "strict_closure_is_wade_closed_plus_shallow": strict_superset_wade,
            "reachable_closed_edge_hit_count": reachable_closed_edge_hit_count,
            "walk_policy_status_difference_count": walk_policy_status_difference_count,
            "walk_policy_route_difference_count": walk_policy_route_difference_count,
            "existing_outputs_modified": False,
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(json.dumps(build_alignment(args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
