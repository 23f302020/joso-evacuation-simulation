"""Build Phase 3R E1 replicate metrics and the 15-combination sign table."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

from p3_e1_type_metrics import assign_vehicle_types, read_bool, read_csv_rows


TYPE34_DENOMINATOR = 3231.5
PEOPLE_PER_RESCUE = 2.3
CONSERVATIVE_BUS_CAP = 124.2
A_RUNS = [
    ("A#1", 23423, "full_20260711T191419_ef66e154"),
    ("A#2", 42, "full_20260711T235922_9ba013a4"),
    ("A#3", 1, "full_20260712T012902_eb2450fd"),
]
B_RUNS = [
    ("B#1", 23423, "final_20260711T150850_e1acce90"),
    ("B#2", 42, "final_20260711T160622_13c0993f"),
    ("B#3", 1, "final_20260711T165523_571d8235"),
    ("B#4", 7, "final_20260711T174226_7deb9824"),
    ("B#5", 101, "final_20260711T182726_a69a01dd"),
]


def find_summary(results_dir: Path, filename: str, run_id: str) -> Path:
    candidates = list(results_dir.glob(f"archive_runs/*/{filename}")) + [results_dir / filename]
    for path in candidates:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        manifest = data.get("run_manifest", {})
        if manifest.get("run_id") == run_id:
            return path
    raise FileNotFoundError(f"run artifact not found: {run_id} ({filename})")


def count_rescue_arrivals(
    vehicle_log: Path,
    type_map: dict[str, dict[str, Any]],
    expected_total: int,
) -> dict[str, int]:
    rows = read_csv_rows(vehicle_log)
    rescue = [row for row in rows if row["vehicle_id"].startswith("rescue_")]
    if len(rescue) != expected_total:
        raise AssertionError(f"rescue total mismatch: expected={expected_total}, actual={len(rescue)}")
    counts = {"type3_total": 0, "type4_total": 0, "type3_arrived": 0, "type4_arrived": 0}
    for row in rescue:
        mapped = type_map.get(row["vehicle_id"])
        if mapped is None or mapped["person_type"] not in {"type3", "type4"}:
            raise AssertionError(f"rescue Type3/4 mapping missing: {row['vehicle_id']}")
        type_code = str(mapped["person_type"])
        counts[f"{type_code}_total"] += 1
        if read_bool(row.get("arrived")):
            counts[f"{type_code}_arrived"] += 1
    return counts


def validate_bus_arrivals(run_dir: Path, summary: dict[str, Any]) -> int:
    passengers = read_csv_rows(run_dir / "scenario_b_passenger_log.csv")
    buses = read_csv_rows(run_dir / "scenario_b_bus_log.csv")
    terminated = {
        (row["bus_id"], row["trip_seq"])
        for row in buses
        if read_bool(row.get("terminated")) and float(row.get("boarded_count") or 0) > 0
    }
    sim_end = str(int(float(summary["run_manifest"].get("sim_end_sec", 21600))))
    arrived = []
    for row in passengers:
        if not read_bool(row.get("arrived")):
            continue
        key = (row["bus_id"], row["trip_seq"])
        terminal_time = str(row.get("arrival_time_s", "")).split(".", 1)[0]
        if key in terminated or terminal_time == sim_end:
            raise AssertionError(f"F8 bus arrival violation: {key}")
        arrived.append(row)
    expected = int(summary["bus_arrived_passengers"])
    if len(arrived) != expected:
        raise AssertionError(f"bus arrival mismatch: summary={expected}, log={len(arrived)}")
    return len(arrived)


def completion_rate(rescue_arrived: int, bus_arrived: float = 0.0) -> float:
    return (rescue_arrived * PEOPLE_PER_RESCUE + bus_arrived) / TYPE34_DENOMINATOR


def sign(value: float, tolerance: float = 1e-12) -> str:
    if value > tolerance:
        return "positive"
    if value < -tolerance:
        return "negative"
    return "zero"


def build_sign_rows(a_rows: list[dict[str, Any]], b_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for b in b_rows:
        for a in a_rows:
            raw_delta = float(b["raw_completion_rate"]) - float(a["raw_completion_rate"])
            conservative_delta = float(b["conservative_completion_rate"]) - float(
                a["conservative_completion_rate"]
            )
            rows.append(
                {
                    "b_run": b["run"],
                    "b_seed": b["seed"],
                    "a_run": a["run"],
                    "a_seed": a["seed"],
                    "raw_delta": round(raw_delta, 9),
                    "raw_sign": sign(raw_delta),
                    "conservative_delta": round(conservative_delta, 9),
                    "conservative_sign": sign(conservative_delta),
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_metrics(city_code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    program_dir = Path(__file__).resolve().parent.parent
    region = program_dir / "output" / "sumo" / "regions" / city_code
    results = region / "results"
    derived = region / "derived"
    agent_types = derived / "agent_types.csv"
    a_assignments = derived / "scenario_a_vehicle_assignments.csv"
    b_assignments = derived / "scenario_b_vehicle_assignments.csv"
    a_type_map, a_diag = assign_vehicle_types(a_assignments, agent_types)
    b_type_map, b_diag = assign_vehicle_types(b_assignments, agent_types)
    if a_diag["unmatched_origin_count"] or b_diag["unmatched_origin_count"]:
        raise AssertionError("unmatched origin in Type3/4 mapping")

    metric_rows: list[dict[str, Any]] = []
    a_metric_rows: list[dict[str, Any]] = []
    b_metric_rows: list[dict[str, Any]] = []
    for run, seed, run_id in A_RUNS:
        summary_path = find_summary(results, "scenario_a_traci_summary.json", run_id)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        counts = count_rescue_arrivals(summary_path.parent / "scenario_a_vehicle_log.csv", a_type_map, 1405)
        rescue_arrived = counts["type3_arrived"] + counts["type4_arrived"]
        rate = completion_rate(rescue_arrived)
        row = {
            "scenario": "A",
            "run": run,
            "seed": seed,
            "run_id": run_id,
            **counts,
            "rescue_arrived_total": rescue_arrived,
            "bus_arrived_raw": 0.0,
            "bus_arrived_conservative": 0.0,
            "raw_completion_rate": round(rate, 9),
            "conservative_completion_rate": round(rate, 9),
            "artifact_dir": str(summary_path.parent),
        }
        metric_rows.append(row)
        a_metric_rows.append(row)

    for run, seed, run_id in B_RUNS:
        summary_path = find_summary(results, "scenario_b_bus_summary.json", run_id)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        counts = count_rescue_arrivals(summary_path.parent / "scenario_b_vehicle_log.csv", b_type_map, 1351)
        rescue_arrived = counts["type3_arrived"] + counts["type4_arrived"]
        bus_raw = validate_bus_arrivals(summary_path.parent, summary)
        bus_conservative = min(float(bus_raw), CONSERVATIVE_BUS_CAP)
        row = {
            "scenario": "B",
            "run": run,
            "seed": seed,
            "run_id": run_id,
            **counts,
            "rescue_arrived_total": rescue_arrived,
            "bus_arrived_raw": float(bus_raw),
            "bus_arrived_conservative": bus_conservative,
            "raw_completion_rate": round(completion_rate(rescue_arrived, bus_raw), 9),
            "conservative_completion_rate": round(
                completion_rate(rescue_arrived, bus_conservative), 9
            ),
            "artifact_dir": str(summary_path.parent),
        }
        metric_rows.append(row)
        b_metric_rows.append(row)

    sign_rows = build_sign_rows(a_metric_rows, b_metric_rows)
    a_raw_rates = [float(row["raw_completion_rate"]) for row in a_metric_rows]
    b_raw_rates = [float(row["raw_completion_rate"]) for row in b_metric_rows]
    b_conservative_rates = [
        float(row["conservative_completion_rate"]) for row in b_metric_rows
    ]
    a_median = statistics.median(a_raw_rates)
    b_raw_median = statistics.median(b_raw_rates)
    b_conservative_median = statistics.median(b_conservative_rates)
    summary = {
        "type34_denominator_people": TYPE34_DENOMINATOR,
        "people_per_rescue_vehicle": PEOPLE_PER_RESCUE,
        "conservative_bus_cap_people": CONSERVATIVE_BUS_CAP,
        "replicate_count": len(metric_rows),
        "combination_count": len(sign_rows),
        "raw_sign_counts": {value: sum(row["raw_sign"] == value for row in sign_rows) for value in ["positive", "negative", "zero"]},
        "conservative_sign_counts": {value: sum(row["conservative_sign"] == value for row in sign_rows) for value in ["positive", "negative", "zero"]},
        "a_completion_rate_values": sorted(a_raw_rates),
        "a_completion_rate_median": a_median,
        "a_completion_rate_min": min(a_raw_rates),
        "a_completion_rate_max": max(a_raw_rates),
        "b_raw_completion_rate_values": sorted(b_raw_rates),
        "b_raw_completion_rate_median": b_raw_median,
        "b_raw_completion_rate_min": min(b_raw_rates),
        "b_raw_completion_rate_max": max(b_raw_rates),
        "b_conservative_completion_rate_values": sorted(b_conservative_rates),
        "b_conservative_completion_rate_median": b_conservative_median,
        "b_conservative_completion_rate_min": min(b_conservative_rates),
        "b_conservative_completion_rate_max": max(b_conservative_rates),
        "raw_point_delta": b_raw_median - a_median,
        "conservative_point_delta": b_conservative_median - a_median,
        "raw_delta_min": min(row["raw_delta"] for row in sign_rows),
        "raw_delta_max": max(row["raw_delta"] for row in sign_rows),
        "conservative_delta_min": min(row["conservative_delta"] for row in sign_rows),
        "conservative_delta_max": max(row["conservative_delta"] for row in sign_rows),
    }
    return metric_rows, sign_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-code", default="08211")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    metrics, signs, summary = build_metrics(args.city_code)
    program_dir = Path(__file__).resolve().parent.parent
    output_dir = args.output_dir or (
        program_dir / "output" / "sumo" / "regions" / args.city_code / "evaluation"
    )
    write_csv(output_dir / "phase3r_e1_replicate_metrics.csv", metrics)
    write_csv(output_dir / "phase3r_e1_15_combination_signs.csv", signs)
    (output_dir / "phase3r_e1_band_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
