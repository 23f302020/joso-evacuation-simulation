"""Phase 3 E1: decompose not-arrived vehicles into stagnation layers.

The decomposition uses only reproducible run artifacts:

1. vehicle_log: identifies not-arrived vehicles and destinations.
2. final FCD timestep: identifies current lane/edge and position.
3. closure_timeline_sumo.json: builds the behavior-effective closure set
   by excluding closures applied at the final simulation second.
4. SUMO net.xml: supplies edge connectivity and lane lengths.

Layer definitions follow the 2026-07-10 A' interpretation memo:

- physical_isolation: current edge is closed and has no open outgoing edge.
- intersection_blockage: current edge is an internal SUMO junction edge.
- queue_behind_blockage: all remaining not-arrived vehicles.

The third layer intentionally includes vehicles with an open topological path
and vehicles whose coarse edge-level reachability is inconclusive.  The layer
means "queued behind the frozen blockage under SUMO's no-mid-edge-U-turn rule",
not proof that every individual vehicle can route at lane level.
"""

from __future__ import annotations

import argparse
import csv
import json
import xml.etree.ElementTree as ET
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROGRAM_DIR / "output"
SUMO_DIR = OUTPUT_DIR / "sumo"

LAYER_PHYSICAL = "physical_isolation"
LAYER_INTERSECTION = "intersection_blockage"
LAYER_QUEUE = "queue_behind_blockage"

DETAIL_FIELDS = [
    "vehicle_id",
    "origin_id",
    "KEY_CODE",
    "destination_edge",
    "lane_id",
    "current_edge",
    "speed_mps",
    "pos_m",
    "lane_length_m",
    "distance_to_lane_end_m",
    "near_lane_end",
    "current_edge_closed",
    "successor_count",
    "open_successor_count",
    "has_open_path_to_destination",
    "layer",
]


@dataclass(frozen=True)
class FcdVehicle:
    lane_id: str
    current_edge: str
    speed_mps: float
    pos_m: float


@dataclass
class NetGraph:
    adjacency: dict[str, set[str]]
    lane_lengths: dict[str, float]
    internal_edges: set[str]


def region_dir(city_code: str) -> Path:
    return SUMO_DIR / "regions" / city_code


def scenario_paths(city_code: str, scenario: str) -> dict[str, Path]:
    base = region_dir(city_code)
    results = base / "results"
    if scenario == "scenario_a":
        prefix = "scenario_a"
    elif scenario == "scenario_a_10pct":
        prefix = "scenario_a_10pct"
    elif scenario == "scenario_a_small":
        prefix = "scenario_a_small"
    elif scenario == "scenario_b":
        prefix = "scenario_b"
    else:
        raise ValueError(f"unknown scenario: {scenario}")
    return {
        "net": base / "network" / f"{city_code}.net.xml",
        "closure": base / "derived" / "closure_timeline_sumo.json",
        "vehicle_log": results / f"{prefix}_vehicle_log.csv",
        "fcd": results / f"{prefix}_fcd.xml",
        "detail_csv": results / f"{prefix}_stagnation_decomposition.csv",
        "summary_json": results / f"{prefix}_stagnation_decomposition_summary.json",
    }


def read_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def edge_from_lane(lane_id: str) -> str:
    if "_" not in lane_id:
        return lane_id
    edge_id, lane_index = lane_id.rsplit("_", 1)
    return edge_id if lane_index.isdigit() else lane_id


def load_not_arrived(vehicle_log_path: Path) -> dict[str, dict[str, str]]:
    with vehicle_log_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return {row["vehicle_id"]: row for row in rows if not read_bool(row.get("arrived"))}


def load_final_fcd_positions(fcd_path: Path) -> tuple[float, dict[str, FcdVehicle]]:
    final_time = -1.0
    final_rows: dict[str, FcdVehicle] = {}
    for event, elem in ET.iterparse(fcd_path, events=("end",)):
        if elem.tag != "timestep":
            continue
        time_value = float(elem.attrib["time"])
        rows: dict[str, FcdVehicle] = {}
        for vehicle in elem.findall("vehicle"):
            lane_id = vehicle.attrib.get("lane", "")
            rows[vehicle.attrib["id"]] = FcdVehicle(
                lane_id=lane_id,
                current_edge=edge_from_lane(lane_id),
                speed_mps=float(vehicle.attrib.get("speed", "0") or 0),
                pos_m=float(vehicle.attrib.get("pos", "0") or 0),
            )
        if time_value >= final_time:
            final_time = time_value
            final_rows = rows
        elem.clear()
    if final_time < 0:
        raise ValueError(f"no timestep found in fcd: {fcd_path}")
    return final_time, final_rows


def load_effective_closures(closure_timeline_path: Path, final_time_sec: float) -> set[str]:
    data = json.loads(closure_timeline_path.read_text(encoding="utf-8"))
    closed: set[str] = set()
    for item in data.get("closures", []):
        if float(item["sim_time_sec"]) >= final_time_sec:
            continue
        closed.update(str(edge_id) for edge_id in item.get("closed_sumo_edge_ids", []))
    return closed


def load_net_graph(net_xml_path: Path) -> NetGraph:
    adjacency: dict[str, set[str]] = {}
    lane_lengths: dict[str, float] = {}
    internal_edges: set[str] = set()
    edge_ids: set[str] = set()

    for event, elem in ET.iterparse(net_xml_path, events=("end",)):
        if elem.tag == "edge":
            edge_id = elem.attrib.get("id", "")
            if not edge_id:
                elem.clear()
                continue
            edge_ids.add(edge_id)
            if elem.attrib.get("function") == "internal" or edge_id.startswith(":"):
                internal_edges.add(edge_id)
            adjacency.setdefault(edge_id, set())
            for lane in elem.findall("lane"):
                lane_id = lane.attrib.get("id", "")
                if lane_id:
                    lane_lengths[lane_id] = float(lane.attrib.get("length", "0") or 0)
            elem.clear()
        elif elem.tag == "connection":
            from_edge = elem.attrib.get("from", "")
            to_edge = elem.attrib.get("to", "")
            if from_edge and to_edge:
                adjacency.setdefault(from_edge, set()).add(to_edge)
            via_lane = elem.attrib.get("via", "")
            if via_lane and to_edge:
                adjacency.setdefault(edge_from_lane(via_lane), set()).add(to_edge)
            elem.clear()

    for edge_id in edge_ids:
        adjacency.setdefault(edge_id, set())
    return NetGraph(adjacency=adjacency, lane_lengths=lane_lengths, internal_edges=internal_edges)


def has_open_path(
    graph: NetGraph,
    start_edge: str,
    destination_edge: str,
    closed_edges: set[str],
) -> bool:
    if not start_edge or not destination_edge:
        return False
    if start_edge == destination_edge:
        return start_edge not in closed_edges
    queue: deque[str] = deque([start_edge])
    seen = {start_edge}
    while queue:
        edge_id = queue.popleft()
        for next_edge in graph.adjacency.get(edge_id, set()):
            if next_edge in seen or next_edge in closed_edges:
                continue
            if next_edge == destination_edge:
                return True
            seen.add(next_edge)
            queue.append(next_edge)
    return False


def classify_vehicle(
    *,
    vehicle: FcdVehicle,
    destination_edge: str,
    graph: NetGraph,
    closed_edges: set[str],
) -> dict[str, Any]:
    current_edge = vehicle.current_edge
    successors = graph.adjacency.get(current_edge, set())
    open_successors = {edge_id for edge_id in successors if edge_id not in closed_edges}
    current_edge_closed = current_edge in closed_edges
    is_internal = current_edge in graph.internal_edges or current_edge.startswith(":")
    path_exists = has_open_path(graph, current_edge, destination_edge, closed_edges)

    if current_edge_closed and not open_successors:
        layer = LAYER_PHYSICAL
    elif is_internal:
        layer = LAYER_INTERSECTION
    else:
        layer = LAYER_QUEUE

    lane_length = graph.lane_lengths.get(vehicle.lane_id, 0.0)
    distance_to_end = max(lane_length - vehicle.pos_m, 0.0) if lane_length else ""
    near_lane_end = bool(lane_length and float(distance_to_end) <= 10.0)
    return {
        "lane_length_m": round(lane_length, 3) if lane_length else "",
        "distance_to_lane_end_m": round(float(distance_to_end), 3) if distance_to_end != "" else "",
        "near_lane_end": near_lane_end,
        "current_edge_closed": current_edge_closed,
        "successor_count": len(successors),
        "open_successor_count": len(open_successors),
        "has_open_path_to_destination": path_exists,
        "layer": layer,
    }


def decompose_stagnation(
    *,
    vehicle_log_path: Path,
    fcd_path: Path,
    net_xml_path: Path,
    closure_timeline_path: Path,
) -> dict[str, Any]:
    not_arrived = load_not_arrived(vehicle_log_path)
    final_time, fcd_positions = load_final_fcd_positions(fcd_path)
    closed_edges = load_effective_closures(closure_timeline_path, final_time)
    graph = load_net_graph(net_xml_path)

    detail_rows: list[dict[str, Any]] = []
    missing_fcd: list[str] = []
    for vehicle_id, log_row in sorted(not_arrived.items()):
        vehicle = fcd_positions.get(vehicle_id)
        if vehicle is None:
            missing_fcd.append(vehicle_id)
            continue
        destination_edge = log_row.get("to_sumo_edge_id", "")
        facts = classify_vehicle(
            vehicle=vehicle,
            destination_edge=destination_edge,
            graph=graph,
            closed_edges=closed_edges,
        )
        detail_rows.append(
            {
                "vehicle_id": vehicle_id,
                "origin_id": log_row.get("origin_id", ""),
                "KEY_CODE": log_row.get("KEY_CODE", ""),
                "destination_edge": destination_edge,
                "lane_id": vehicle.lane_id,
                "current_edge": vehicle.current_edge,
                "speed_mps": vehicle.speed_mps,
                "pos_m": vehicle.pos_m,
                **facts,
            }
        )

    layer_counts = Counter(row["layer"] for row in detail_rows)
    closed_edge_rows = sum(1 for row in detail_rows if row["current_edge_closed"])
    open_path_rows = sum(1 for row in detail_rows if row["has_open_path_to_destination"])
    summary = {
        "vehicle_log": str(vehicle_log_path),
        "fcd": str(fcd_path),
        "net_xml": str(net_xml_path),
        "closure_timeline": str(closure_timeline_path),
        "fcd_final_time_sec": final_time,
        "effective_closure_rule": "closed edges with sim_time_sec < fcd_final_time_sec",
        "effective_closed_edge_count": len(closed_edges),
        "not_arrived_count": len(not_arrived),
        "classified_count": len(detail_rows),
        "missing_fcd_count": len(missing_fcd),
        "missing_fcd_vehicle_ids": missing_fcd,
        "layer_counts": {
            LAYER_PHYSICAL: layer_counts.get(LAYER_PHYSICAL, 0),
            LAYER_INTERSECTION: layer_counts.get(LAYER_INTERSECTION, 0),
            LAYER_QUEUE: layer_counts.get(LAYER_QUEUE, 0),
        },
        "closed_current_edge_vehicle_count": closed_edge_rows,
        "open_path_to_destination_vehicle_count": open_path_rows,
        "distinct_current_edge_count": len({row["current_edge"] for row in detail_rows}),
    }
    return {"summary": summary, "detail_rows": detail_rows}


def write_decomposition_outputs(result: dict[str, Any], detail_csv: Path, summary_json: Path) -> None:
    detail_csv.parent.mkdir(parents=True, exist_ok=True)
    with detail_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DETAIL_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["detail_rows"])
    summary = dict(result["summary"])
    summary["detail_csv"] = str(detail_csv)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-code", default="08211")
    parser.add_argument(
        "--scenario",
        choices=["scenario_a", "scenario_a_10pct", "scenario_a_small", "scenario_b"],
        default="scenario_a",
    )
    parser.add_argument("--vehicle-log", type=Path)
    parser.add_argument("--fcd", type=Path)
    parser.add_argument("--net-xml", type=Path)
    parser.add_argument("--closure-timeline", type=Path)
    parser.add_argument("--detail-csv", type=Path)
    parser.add_argument("--summary-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    defaults = scenario_paths(args.city_code, args.scenario)
    result = decompose_stagnation(
        vehicle_log_path=args.vehicle_log or defaults["vehicle_log"],
        fcd_path=args.fcd or defaults["fcd"],
        net_xml_path=args.net_xml or defaults["net"],
        closure_timeline_path=args.closure_timeline or defaults["closure"],
    )
    detail_csv = args.detail_csv or defaults["detail_csv"]
    summary_json = args.summary_json or defaults["summary_json"]
    write_decomposition_outputs(result, detail_csv, summary_json)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
