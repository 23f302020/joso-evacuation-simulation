"""Phase 3 E1: type-based completion and equity metrics.

This script maps every vehicle in a SUMO vehicle_log to Type1-4 using the
origin-level agent type table and route assignment table, then computes:

- Type3/4 completion rates.
- Conditional completion-time distributions for arrived vehicles.
- Type-level equity diagnostics including worst-off completion time.

The mapping is vehicle-level.  For scenario A, private cars are allocated
between Type1/Type2, and rescue cars between Type3/Type4, within each origin by
largest-remainder proportional allocation from the population counts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROGRAM_DIR / "output"
SUMO_DIR = OUTPUT_DIR / "sumo"
WORST_OFF_FRACTION = 0.10
TYPE_LABELS = {
    "type1": "car_non_elderly",
    "type2": "car_elderly",
    "type3": "no_car_non_elderly",
    "type4": "no_car_elderly",
}


def region_dir(city_code: str) -> Path:
    return SUMO_DIR / "regions" / city_code


def read_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def proportional_counts(raw_values: list[float], target_total: int) -> list[int]:
    if target_total <= 0:
        return [0 for _ in raw_values]
    total = sum(max(0.0, value) for value in raw_values)
    if total <= 0:
        counts = [0 for _ in raw_values]
        counts[0] = target_total
        return counts
    quotas = [max(0.0, value) / total * target_total for value in raw_values]
    floors = [math.floor(value) for value in quotas]
    remainder = target_total - sum(floors)
    order = sorted(
        range(len(quotas)),
        key=lambda index: (quotas[index] - floors[index], -index),
        reverse=True,
    )
    counts = floors[:]
    for index in order[:remainder]:
        counts[index] += 1
    return counts


def type_targets_for_origin(agent_row: dict[str, str], vehicle_kind: str) -> list[tuple[str, float]]:
    if vehicle_kind == "rescue_car":
        return [
            ("type3", parse_float(agent_row.get("type3_no_car_non_elderly_pop"))),
            ("type4", parse_float(agent_row.get("type4_no_car_elderly_pop"))),
        ]
    return [
        ("type1", parse_float(agent_row.get("type1_car_non_elderly_pop"))),
        ("type2", parse_float(agent_row.get("type2_car_elderly_pop"))),
    ]


def assign_vehicle_types(
    assignments_path: Path,
    agent_types_path: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    assignments = read_csv_rows(assignments_path)
    agent_by_origin = {row["origin_id"]: row for row in read_csv_rows(agent_types_path)}
    by_origin_kind: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in assignments:
        by_origin_kind[(row["origin_id"], row.get("vehicle_kind", "private_car"))].append(row)

    typed: dict[str, dict[str, Any]] = {}
    unmatched_origin_ids: set[str] = set()
    for (origin_id, vehicle_kind), rows in sorted(by_origin_kind.items()):
        agent_row = agent_by_origin.get(origin_id)
        if agent_row is None:
            unmatched_origin_ids.add(origin_id)
            targets = [("unknown", 1.0)]
        else:
            targets = type_targets_for_origin(agent_row, vehicle_kind)
        counts = proportional_counts([value for _label, value in targets], len(rows))
        labels: list[str] = []
        for (label, _value), count in zip(targets, counts):
            labels.extend([label] * count)
        labels.extend([targets[-1][0]] * (len(rows) - len(labels)))
        for row, type_code in zip(sorted(rows, key=lambda item: item["vehicle_id"]), labels):
            typed[row["vehicle_id"]] = {
                "vehicle_id": row["vehicle_id"],
                "origin_id": origin_id,
                "KEY_CODE": row.get("KEY_CODE", ""),
                "vehicle_kind": vehicle_kind,
                "person_type": type_code,
                "type_label": TYPE_LABELS.get(type_code, "unknown"),
                "passenger_equivalent": parse_float(row.get("passenger_equivalent"), 1.0),
            }

    diagnostics = {
        "assignment_count": len(assignments),
        "typed_vehicle_count": len(typed),
        "unmatched_origin_count": len(unmatched_origin_ids),
        "unmatched_origin_ids": sorted(unmatched_origin_ids),
    }
    return typed, diagnostics


def percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return sorted_values[lower]
    weight = pos - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def duration_stats(durations: list[float]) -> dict[str, Any]:
    if not durations:
        return {
            "conditional_mean_duration_sec": "",
            "conditional_median_duration_sec": "",
            "conditional_p90_duration_sec": "",
            "conditional_max_duration_sec": "",
            "worst_off_fraction": WORST_OFF_FRACTION,
            "worst_off_count": 0,
            "worst_off_mean_duration_sec": "",
        }
    values = sorted(durations)
    worst_n = max(1, int(round(len(values) * WORST_OFF_FRACTION)))
    worst = values[-worst_n:]
    return {
        "conditional_mean_duration_sec": round(sum(values) / len(values), 3),
        "conditional_median_duration_sec": round(percentile(values, 0.50), 3),
        "conditional_p90_duration_sec": round(percentile(values, 0.90), 3),
        "conditional_max_duration_sec": round(max(values), 3),
        "worst_off_fraction": WORST_OFF_FRACTION,
        "worst_off_count": worst_n,
        "worst_off_mean_duration_sec": round(sum(worst) / len(worst), 3),
    }


def compute_e1_metrics(
    *,
    vehicle_log_path: Path,
    assignments_path: Path,
    agent_types_path: Path,
) -> dict[str, Any]:
    type_map, diagnostics = assign_vehicle_types(assignments_path, agent_types_path)
    vehicle_rows = read_csv_rows(vehicle_log_path)
    detail_rows: list[dict[str, Any]] = []
    unmatched_vehicle_ids: list[str] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in vehicle_rows:
        mapped = type_map.get(row["vehicle_id"])
        if mapped is None:
            unmatched_vehicle_ids.append(row["vehicle_id"])
            person_type = "unknown"
            mapped = {
                "origin_id": row.get("origin_id", ""),
                "KEY_CODE": row.get("KEY_CODE", ""),
                "vehicle_kind": "",
                "person_type": person_type,
                "type_label": "unknown",
                "passenger_equivalent": 1.0,
            }
        person_type = str(mapped["person_type"])
        arrived = read_bool(row.get("arrived"))
        duration = parse_float(row.get("duration")) if arrived else ""
        out = {
            "vehicle_id": row["vehicle_id"],
            "origin_id": mapped.get("origin_id", row.get("origin_id", "")),
            "KEY_CODE": mapped.get("KEY_CODE", row.get("KEY_CODE", "")),
            "vehicle_kind": mapped.get("vehicle_kind", ""),
            "person_type": person_type,
            "type_label": mapped.get("type_label", "unknown"),
            "passenger_equivalent": mapped.get("passenger_equivalent", 1.0),
            "arrived": arrived,
            "duration": duration,
            "stranded_main": read_bool(row.get("stranded_main")),
            "long_stopped": read_bool(row.get("long_stopped")),
        }
        detail_rows.append(out)
        grouped[person_type].append(out)
        grouped["all"].append(out)

    metric_rows: list[dict[str, Any]] = []
    for type_code in ["all", "type1", "type2", "type3", "type4", "unknown"]:
        rows = grouped.get(type_code, [])
        if not rows and type_code == "unknown":
            continue
        total = len(rows)
        arrived_rows = [row for row in rows if row["arrived"]]
        not_arrived = total - len(arrived_rows)
        people_total = sum(float(row["passenger_equivalent"]) for row in rows)
        people_arrived = sum(float(row["passenger_equivalent"]) for row in arrived_rows)
        durations = [float(row["duration"]) for row in arrived_rows if row["duration"] != ""]
        stats = duration_stats(durations)
        metric_rows.append(
            {
                "person_type": type_code,
                "type_label": TYPE_LABELS.get(type_code, "all" if type_code == "all" else "unknown"),
                "vehicle_count": total,
                "arrived_count": len(arrived_rows),
                "not_arrived_count": not_arrived,
                "completion_rate": round(len(arrived_rows) / total, 6) if total else "",
                "people_equivalent_total": round(people_total, 3),
                "people_equivalent_arrived": round(people_arrived, 3),
                "people_equivalent_completion_rate": round(people_arrived / people_total, 6)
                if people_total
                else "",
                **stats,
            }
        )

    type34_rows = grouped.get("type3", []) + grouped.get("type4", [])
    type34_arrived = [row for row in type34_rows if row["arrived"]]
    type34_durations = [
        float(row["duration"]) for row in type34_arrived if row["duration"] != ""
    ]
    summary = {
        "vehicle_log": str(vehicle_log_path),
        "assignments": str(assignments_path),
        "agent_types": str(agent_types_path),
        "vehicle_count": len(vehicle_rows),
        "typed_vehicle_count": len(detail_rows) - len(unmatched_vehicle_ids),
        "unmatched_vehicle_count": len(unmatched_vehicle_ids),
        "unmatched_vehicle_ids": unmatched_vehicle_ids,
        **diagnostics,
        "type34_vehicle_count": len(type34_rows),
        "type34_arrived_count": len(type34_arrived),
        "type34_completion_rate": round(len(type34_arrived) / len(type34_rows), 6)
        if type34_rows
        else "",
        "type34_conditional_duration": duration_stats(type34_durations),
    }
    return {
        "summary": summary,
        "vehicle_type_rows": detail_rows,
        "metric_rows": metric_rows,
    }


def write_e1_outputs(
    result: dict[str, Any],
    *,
    vehicle_type_map_csv: Path,
    type_metrics_csv: Path,
    summary_json: Path,
) -> None:
    write_csv(
        vehicle_type_map_csv,
        [
            "vehicle_id",
            "origin_id",
            "KEY_CODE",
            "vehicle_kind",
            "person_type",
            "type_label",
            "passenger_equivalent",
            "arrived",
            "duration",
            "stranded_main",
            "long_stopped",
        ],
        result["vehicle_type_rows"],
    )
    write_csv(
        type_metrics_csv,
        [
            "person_type",
            "type_label",
            "vehicle_count",
            "arrived_count",
            "not_arrived_count",
            "completion_rate",
            "people_equivalent_total",
            "people_equivalent_arrived",
            "people_equivalent_completion_rate",
            "conditional_mean_duration_sec",
            "conditional_median_duration_sec",
            "conditional_p90_duration_sec",
            "conditional_max_duration_sec",
            "worst_off_fraction",
            "worst_off_count",
            "worst_off_mean_duration_sec",
        ],
        result["metric_rows"],
    )
    summary = dict(result["summary"])
    summary["vehicle_type_map_csv"] = str(vehicle_type_map_csv)
    summary["type_metrics_csv"] = str(type_metrics_csv)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def default_paths(city_code: str, scenario: str) -> dict[str, Path]:
    base = region_dir(city_code)
    prefix = "scenario_a" if scenario == "scenario_a" else scenario
    return {
        "vehicle_log": base / "results" / f"{prefix}_vehicle_log.csv",
        "assignments": base / "derived" / f"{prefix}_vehicle_assignments.csv",
        "agent_types": base / "derived" / "agent_types.csv",
        "vehicle_type_map_csv": base / "evaluation" / f"{prefix}_e1_vehicle_type_map.csv",
        "type_metrics_csv": base / "evaluation" / f"{prefix}_e1_type_metrics.csv",
        "summary_json": base / "evaluation" / f"{prefix}_e1_summary.json",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-code", default="08211")
    parser.add_argument("--scenario", default="scenario_a", choices=["scenario_a"])
    parser.add_argument("--vehicle-log", type=Path)
    parser.add_argument("--assignments", type=Path)
    parser.add_argument("--agent-types", type=Path)
    parser.add_argument("--vehicle-type-map-csv", type=Path)
    parser.add_argument("--type-metrics-csv", type=Path)
    parser.add_argument("--summary-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = default_paths(args.city_code, args.scenario)
    result = compute_e1_metrics(
        vehicle_log_path=args.vehicle_log or paths["vehicle_log"],
        assignments_path=args.assignments or paths["assignments"],
        agent_types_path=args.agent_types or paths["agent_types"],
    )
    write_e1_outputs(
        result,
        vehicle_type_map_csv=args.vehicle_type_map_csv or paths["vehicle_type_map_csv"],
        type_metrics_csv=args.type_metrics_csv or paths["type_metrics_csv"],
        summary_json=args.summary_json or paths["summary_json"],
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
