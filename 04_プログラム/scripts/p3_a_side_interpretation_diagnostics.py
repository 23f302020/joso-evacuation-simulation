"""Phase 3 A-side interpretation diagnostics before B measurement run.

The outputs cover the remaining Decision 46 checks:

- Not-arrived vehicles by origin, vehicle_kind, and closure timing.
- Route length and destination shelter by vehicle_kind.
- Type3/Type4 completion gap allocation-shadow diagnostics.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

from p3_e1_type_metrics import assign_vehicle_types, parse_float, percentile, read_bool


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROGRAM_DIR / "output"
SUMO_DIR = OUTPUT_DIR / "sumo"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def safe_rate(numerator: float, denominator: float) -> float | str:
    if denominator == 0:
        return ""
    return round(numerator / denominator, 6)


def route_length_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "route_length_available_count": 0,
            "route_length_mean_m": "",
            "route_length_median_m": "",
            "route_length_p90_m": "",
            "route_length_max_m": "",
        }
    sorted_values = sorted(values)
    return {
        "route_length_available_count": len(values),
        "route_length_mean_m": round(sum(values) / len(values), 3),
        "route_length_median_m": round(percentile(sorted_values, 0.50), 3),
        "route_length_p90_m": round(percentile(sorted_values, 0.90), 3),
        "route_length_max_m": round(max(values), 3),
    }


def load_first_closure_times(closure_timeline_path: Path) -> dict[str, int]:
    data = json.loads(closure_timeline_path.read_text(encoding="utf-8"))
    first_time: dict[str, int] = {}
    for event in data.get("closures", []):
        sim_time = int(event["sim_time_sec"])
        for edge_id in event.get("closed_sumo_edge_ids", []):
            first_time.setdefault(edge_id, sim_time)
    return first_time


def load_tripinfo_route_lengths(tripinfo_path: Path) -> dict[str, float]:
    route_lengths: dict[str, float] = {}
    for _event, elem in ET.iterparse(tripinfo_path, events=("end",)):
        if elem.tag != "tripinfo":
            continue
        vehicle_id = elem.attrib.get("id")
        if vehicle_id:
            route_lengths[vehicle_id] = parse_float(elem.attrib.get("routeLength"))
        elem.clear()
    return route_lengths


def pearson(xs: list[float], ys: list[float]) -> float | str:
    if len(xs) < 2 or len(xs) != len(ys):
        return ""
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    dx = [value - mean_x for value in xs]
    dy = [value - mean_y for value in ys]
    denom_x = math.sqrt(sum(value * value for value in dx))
    denom_y = math.sqrt(sum(value * value for value in dy))
    if denom_x == 0 or denom_y == 0:
        return ""
    return round(sum(x * y for x, y in zip(dx, dy)) / (denom_x * denom_y), 6)


def build_vehicle_context(
    *,
    vehicle_log_path: Path,
    assignments_path: Path,
    agent_types_path: Path,
    tripinfo_path: Path,
    stagnation_path: Path | None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    assignments = {row["vehicle_id"]: row for row in read_csv_rows(assignments_path)}
    type_map, _diagnostics = assign_vehicle_types(assignments_path, agent_types_path)
    route_lengths = load_tripinfo_route_lengths(tripinfo_path)
    stagnation_by_vehicle = {
        row["vehicle_id"]: row
        for row in read_csv_rows(stagnation_path)
    } if stagnation_path and stagnation_path.exists() else {}

    rows: list[dict[str, Any]] = []
    for row in read_csv_rows(vehicle_log_path):
        vehicle_id = row["vehicle_id"]
        assignment = assignments.get(vehicle_id, {})
        typed = type_map.get(vehicle_id, {})
        stagnation = stagnation_by_vehicle.get(vehicle_id, {})
        rows.append(
            {
                **row,
                "vehicle_kind": assignment.get("vehicle_kind", ""),
                "shelter_id": assignment.get("shelter_id", ""),
                "shelter_name": assignment.get("shelter_name", ""),
                "from_sumo_edge_id": assignment.get("from_sumo_edge_id", row.get("from_sumo_edge_id", "")),
                "to_sumo_edge_id": assignment.get("to_sumo_edge_id", row.get("to_sumo_edge_id", "")),
                "person_type": typed.get("person_type", "unknown"),
                "type_label": typed.get("type_label", "unknown"),
                "route_length_m": route_lengths.get(vehicle_id, ""),
                "current_edge": stagnation.get("current_edge", ""),
                "current_edge_closed": stagnation.get("current_edge_closed", ""),
                "has_open_path_to_destination": stagnation.get("has_open_path_to_destination", ""),
            }
        )
    agent_by_origin = {row["origin_id"]: row for row in read_csv_rows(agent_types_path)}
    return rows, agent_by_origin


def not_arrived_by_origin_kind_closure(
    rows: list[dict[str, Any]],
    first_closure_times: dict[str, int],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        if read_bool(row.get("arrived")):
            continue
        origin_edge = row.get("from_sumo_edge_id", "")
        current_edge = row.get("current_edge", "")
        key = (
            str(row.get("origin_id", "")),
            str(row.get("KEY_CODE", "")),
            str(row.get("vehicle_kind", "")),
            origin_edge,
            str(first_closure_times.get(origin_edge, "")),
        )
        out = grouped.setdefault(
            key,
            {
                "origin_id": key[0],
                "KEY_CODE": key[1],
                "vehicle_kind": key[2],
                "origin_edge": key[3],
                "origin_edge_first_closure_sec": key[4],
                "not_arrived_count": 0,
                "type3_count": 0,
                "type4_count": 0,
                "current_edge_closed_count": 0,
                "current_edge_min_first_closure_sec": "",
            },
        )
        out["not_arrived_count"] += 1
        if row.get("person_type") == "type3":
            out["type3_count"] += 1
        if row.get("person_type") == "type4":
            out["type4_count"] += 1
        if read_bool(row.get("current_edge_closed")):
            out["current_edge_closed_count"] += 1
        current_closure = first_closure_times.get(current_edge)
        if current_closure is not None:
            previous = out["current_edge_min_first_closure_sec"]
            out["current_edge_min_first_closure_sec"] = (
                current_closure if previous == "" else min(int(previous), current_closure)
            )
    return sorted(
        grouped.values(),
        key=lambda item: (-int(item["not_arrived_count"]), item["origin_id"], item["vehicle_kind"]),
    )


def vehicle_kind_route_shelter(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("vehicle_kind", "")),
            str(row.get("shelter_id", "")),
            str(row.get("shelter_name", "")),
        )
        grouped[key].append(row)

    out_rows: list[dict[str, Any]] = []
    for (vehicle_kind, shelter_id, shelter_name), group_rows in grouped.items():
        lengths = [
            float(row["route_length_m"])
            for row in group_rows
            if row.get("route_length_m") not in {"", None}
        ]
        arrived_count = sum(1 for row in group_rows if read_bool(row.get("arrived")))
        out_rows.append(
            {
                "vehicle_kind": vehicle_kind,
                "shelter_id": shelter_id,
                "shelter_name": shelter_name,
                "vehicle_count": len(group_rows),
                "arrived_count": arrived_count,
                "not_arrived_count": len(group_rows) - arrived_count,
                "completion_rate": safe_rate(float(arrived_count), float(len(group_rows))),
                **route_length_stats(lengths),
            }
        )
    return sorted(out_rows, key=lambda item: (item["vehicle_kind"], item["shelter_id"]))


def allocation_shadow_by_origin(
    rows: list[dict[str, Any]],
    agent_by_origin: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("person_type") in {"type3", "type4"}:
            grouped[str(row.get("origin_id", ""))].append(row)

    out_rows: list[dict[str, Any]] = []
    type4_shares: list[float] = []
    completion_rates: list[float] = []
    gaps: list[float] = []
    for origin_id, group_rows in grouped.items():
        type3_rows = [row for row in group_rows if row.get("person_type") == "type3"]
        type4_rows = [row for row in group_rows if row.get("person_type") == "type4"]
        type3_arrived = sum(1 for row in type3_rows if read_bool(row.get("arrived")))
        type4_arrived = sum(1 for row in type4_rows if read_bool(row.get("arrived")))
        total_arrived = type3_arrived + type4_arrived
        type3_rate = safe_rate(float(type3_arrived), float(len(type3_rows)))
        type4_rate = safe_rate(float(type4_arrived), float(len(type4_rows)))
        completion_rate = safe_rate(float(total_arrived), float(len(group_rows)))
        assigned_type4_share = safe_rate(float(len(type4_rows)), float(len(group_rows)))

        agent_row = agent_by_origin.get(origin_id, {})
        type3_pop = parse_float(agent_row.get("type3_no_car_non_elderly_pop"))
        type4_pop = parse_float(agent_row.get("type4_no_car_elderly_pop"))
        pop_type4_share = safe_rate(type4_pop, type3_pop + type4_pop)
        gap = ""
        if type3_rate != "" and type4_rate != "":
            gap = round(float(type4_rate) - float(type3_rate), 6)

        if assigned_type4_share != "" and completion_rate != "":
            type4_shares.append(float(assigned_type4_share))
            completion_rates.append(float(completion_rate))
        if gap != "":
            gaps.append(float(gap))

        out_rows.append(
            {
                "origin_id": origin_id,
                "KEY_CODE": group_rows[0].get("KEY_CODE", ""),
                "type3_vehicle_count": len(type3_rows),
                "type3_arrived_count": type3_arrived,
                "type3_completion_rate": type3_rate,
                "type4_vehicle_count": len(type4_rows),
                "type4_arrived_count": type4_arrived,
                "type4_completion_rate": type4_rate,
                "type34_vehicle_count": len(group_rows),
                "type34_arrived_count": total_arrived,
                "type34_completion_rate": completion_rate,
                "assigned_type4_share": assigned_type4_share,
                "population_type4_share": pop_type4_share,
                "type4_minus_type3_completion_rate": gap,
            }
        )

    summary = {
        "origin_count": len(out_rows),
        "pearson_assigned_type4_share_vs_type34_completion_rate": pearson(type4_shares, completion_rates),
        "mean_type4_minus_type3_completion_rate_by_origin": round(sum(gaps) / len(gaps), 6) if gaps else "",
    }
    return sorted(out_rows, key=lambda item: item["origin_id"]), summary


def build_interpretation_diagnostics(
    *,
    vehicle_log_path: Path,
    assignments_path: Path,
    agent_types_path: Path,
    closure_timeline_path: Path,
    tripinfo_path: Path,
    stagnation_path: Path | None = None,
) -> dict[str, Any]:
    rows, agent_by_origin = build_vehicle_context(
        vehicle_log_path=vehicle_log_path,
        assignments_path=assignments_path,
        agent_types_path=agent_types_path,
        tripinfo_path=tripinfo_path,
        stagnation_path=stagnation_path,
    )
    first_closure_times = load_first_closure_times(closure_timeline_path)
    not_arrived_rows = not_arrived_by_origin_kind_closure(rows, first_closure_times)
    route_shelter_rows = vehicle_kind_route_shelter(rows)
    allocation_rows, allocation_summary = allocation_shadow_by_origin(rows, agent_by_origin)
    summary = {
        "vehicle_count": len(rows),
        "not_arrived_count": sum(1 for row in rows if not read_bool(row.get("arrived"))),
        "not_arrived_origin_kind_closure_row_count": len(not_arrived_rows),
        "route_shelter_row_count": len(route_shelter_rows),
        "allocation_shadow_row_count": len(allocation_rows),
        "allocation_shadow": allocation_summary,
    }
    return {
        "summary": summary,
        "not_arrived_rows": not_arrived_rows,
        "route_shelter_rows": route_shelter_rows,
        "allocation_shadow_rows": allocation_rows,
    }


def write_diagnostics(
    result: dict[str, Any],
    *,
    not_arrived_csv: Path,
    route_shelter_csv: Path,
    allocation_shadow_csv: Path,
    summary_json: Path,
) -> None:
    write_csv(
        not_arrived_csv,
        [
            "origin_id",
            "KEY_CODE",
            "vehicle_kind",
            "origin_edge",
            "origin_edge_first_closure_sec",
            "not_arrived_count",
            "type3_count",
            "type4_count",
            "current_edge_closed_count",
            "current_edge_min_first_closure_sec",
        ],
        result["not_arrived_rows"],
    )
    write_csv(
        route_shelter_csv,
        [
            "vehicle_kind",
            "shelter_id",
            "shelter_name",
            "vehicle_count",
            "arrived_count",
            "not_arrived_count",
            "completion_rate",
            "route_length_available_count",
            "route_length_mean_m",
            "route_length_median_m",
            "route_length_p90_m",
            "route_length_max_m",
        ],
        result["route_shelter_rows"],
    )
    write_csv(
        allocation_shadow_csv,
        [
            "origin_id",
            "KEY_CODE",
            "type3_vehicle_count",
            "type3_arrived_count",
            "type3_completion_rate",
            "type4_vehicle_count",
            "type4_arrived_count",
            "type4_completion_rate",
            "type34_vehicle_count",
            "type34_arrived_count",
            "type34_completion_rate",
            "assigned_type4_share",
            "population_type4_share",
            "type4_minus_type3_completion_rate",
        ],
        result["allocation_shadow_rows"],
    )
    summary = dict(result["summary"])
    summary["not_arrived_csv"] = str(not_arrived_csv)
    summary["route_shelter_csv"] = str(route_shelter_csv)
    summary["allocation_shadow_csv"] = str(allocation_shadow_csv)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def region_dir(city_code: str) -> Path:
    return SUMO_DIR / "regions" / city_code


def default_paths(city_code: str, scenario: str) -> dict[str, Path]:
    base = region_dir(city_code)
    return {
        "vehicle_log": base / "results" / f"{scenario}_vehicle_log.csv",
        "assignments": base / "derived" / f"{scenario}_vehicle_assignments.csv",
        "agent_types": base / "derived" / "agent_types.csv",
        "closure_timeline": base / "derived" / "closure_timeline_sumo.json",
        "tripinfo": base / "results" / f"{scenario}_tripinfo.xml",
        "stagnation": base / "results" / f"{scenario}_stagnation_decomposition.csv",
        "not_arrived_csv": base / "evaluation" / f"{scenario}_diag_not_arrived_origin_kind_closure.csv",
        "route_shelter_csv": base / "evaluation" / f"{scenario}_diag_vehicle_kind_route_shelter.csv",
        "allocation_shadow_csv": base / "evaluation" / f"{scenario}_diag_allocation_shadow_by_origin.csv",
        "summary_json": base / "evaluation" / f"{scenario}_diag_summary.json",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-code", default="08211")
    parser.add_argument("--scenario", default="scenario_a")
    parser.add_argument("--vehicle-log", type=Path)
    parser.add_argument("--assignments", type=Path)
    parser.add_argument("--agent-types", type=Path)
    parser.add_argument("--closure-timeline", type=Path)
    parser.add_argument("--tripinfo", type=Path)
    parser.add_argument("--stagnation", type=Path)
    parser.add_argument("--not-arrived-csv", type=Path)
    parser.add_argument("--route-shelter-csv", type=Path)
    parser.add_argument("--allocation-shadow-csv", type=Path)
    parser.add_argument("--summary-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = default_paths(args.city_code, args.scenario)
    result = build_interpretation_diagnostics(
        vehicle_log_path=args.vehicle_log or paths["vehicle_log"],
        assignments_path=args.assignments or paths["assignments"],
        agent_types_path=args.agent_types or paths["agent_types"],
        closure_timeline_path=args.closure_timeline or paths["closure_timeline"],
        tripinfo_path=args.tripinfo or paths["tripinfo"],
        stagnation_path=args.stagnation or paths["stagnation"],
    )
    write_diagnostics(
        result,
        not_arrived_csv=args.not_arrived_csv or paths["not_arrived_csv"],
        route_shelter_csv=args.route_shelter_csv or paths["route_shelter_csv"],
        allocation_shadow_csv=args.allocation_shadow_csv or paths["allocation_shadow_csv"],
        summary_json=args.summary_json or paths["summary_json"],
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
