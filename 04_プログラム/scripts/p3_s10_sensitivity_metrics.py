"""Aggregate the five 10-bus sensitivity runs and test sign consistency."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from p3_phase3r_e1_bands import (
    TYPE34_DENOMINATOR,
    PEOPLE_PER_RESCUE,
    VERIFIED_COMPLETION_RATES,
    find_summary,
    sign,
    validate_bus_arrivals,
    write_csv,
)


S10_RUNS = [
    ("S10#1", 23423, "final_20260712T101244_e84e6dba"),
    ("S10#2", 42, "final_20260712T112108_21310280"),
    ("S10#3", 1, "final_20260712T125643_fabbf682"),
    ("S10#4", 7, "final_20260712T134233_406586a0"),
    ("S10#5", 101, "final_20260712T145337_6cbdfcff"),
]


def count_rescue_arrived(vehicle_log: Path) -> tuple[int, int]:
    with vehicle_log.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rescue = [row for row in rows if row["vehicle_id"].startswith("rescue_")]
    if len(rescue) != 1351:
        raise AssertionError(f"rescue total mismatch: {len(rescue)}")
    return len(rescue), sum(row["arrived"].lower() == "true" for row in rescue)


def build_s10_metrics(city_code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    program = Path(__file__).resolve().parent.parent
    results = program / "output" / "sumo" / "regions" / city_code / "results"
    metrics: list[dict[str, Any]] = []
    for run, seed, run_id in S10_RUNS:
        summary_path = find_summary(results, "scenario_b_bus_summary.json", run_id)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if int(summary["bus_count"]) != 10:
            raise AssertionError(f"{run}: expected 10 buses")
        rescue_total, rescue_arrived = count_rescue_arrived(
            summary_path.parent / "scenario_b_vehicle_log.csv"
        )
        bus_arrived = validate_bus_arrivals(summary_path.parent, summary)
        rate = (rescue_arrived * PEOPLE_PER_RESCUE + bus_arrived) / TYPE34_DENOMINATOR
        metrics.append(
            {
                "run": run,
                "seed": seed,
                "run_id": run_id,
                "bus_count": 10,
                "rescue_total": rescue_total,
                "rescue_arrived": rescue_arrived,
                "bus_arrived": bus_arrived,
                "completion_rate": round(rate, 9),
                "completion_rate_percent": round(rate * 100, 6),
                "artifact_dir": str(summary_path.parent),
            }
        )

    signs: list[dict[str, Any]] = []
    for s_row in metrics:
        for a_run in ["A#1", "A#2", "A#3"]:
            a_rate = VERIFIED_COMPLETION_RATES[a_run]["raw"]
            delta = float(s_row["completion_rate"]) - a_rate
            signs.append(
                {
                    "s_run": s_row["run"],
                    "s_seed": s_row["seed"],
                    "a_run": a_run,
                    "delta_rate": round(delta, 9),
                    "delta_percentage_points": round(delta * 100, 6),
                    "sign": sign(delta),
                }
            )
    counts = {value: sum(row["sign"] == value for row in signs) for value in ["positive", "negative", "zero"]}
    summary = {
        "bus_count": 10,
        "replicate_count": 5,
        "combination_count": 15,
        "sign_counts": counts,
        "sign_consistent": max(counts.values()) == 15,
        "completion_rate_min_percent": min(row["completion_rate_percent"] for row in metrics),
        "completion_rate_max_percent": max(row["completion_rate_percent"] for row in metrics),
        "decision109_stop_s_series": max(counts.values()) != 15,
    }
    return metrics, signs, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-code", default="08211")
    args = parser.parse_args()
    metrics, signs, summary = build_s10_metrics(args.city_code)
    output = (
        Path(__file__).resolve().parent.parent
        / "output"
        / "sumo"
        / "regions"
        / args.city_code
        / "evaluation"
    )
    write_csv(output / "phase3_s10_replicate_metrics.csv", metrics)
    write_csv(output / "phase3_s10_15_combination_signs.csv", signs)
    (output / "phase3_s10_band_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
