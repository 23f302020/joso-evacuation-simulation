"""Aggregate the five 10-bus sensitivity runs and test sign consistency."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from p3_phase3r_e1_bands import (
    CONSERVATIVE_BUS_CAP,
    TYPE34_DENOMINATOR,
    PEOPLE_PER_RESCUE,
    build_metrics,
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
        bus_arrived_raw = validate_bus_arrivals(summary_path.parent, summary)
        bus_arrived_conservative = min(float(bus_arrived_raw), CONSERVATIVE_BUS_CAP)
        raw_rate = (
            rescue_arrived * PEOPLE_PER_RESCUE + bus_arrived_raw
        ) / TYPE34_DENOMINATOR
        conservative_rate = (
            rescue_arrived * PEOPLE_PER_RESCUE + bus_arrived_conservative
        ) / TYPE34_DENOMINATOR
        metrics.append(
            {
                "run": run,
                "seed": seed,
                "run_id": run_id,
                "bus_count": 10,
                "rescue_total": rescue_total,
                "rescue_arrived": rescue_arrived,
                "bus_arrived_raw": float(bus_arrived_raw),
                "bus_arrived_conservative": bus_arrived_conservative,
                "raw_completion_rate": round(raw_rate, 9),
                "conservative_completion_rate": round(conservative_rate, 9),
                "raw_completion_rate_percent": round(raw_rate * 100, 6),
                "conservative_completion_rate_percent": round(
                    conservative_rate * 100, 6
                ),
                "artifact_dir": str(summary_path.parent),
            }
        )

    phase3_metrics, _, _ = build_metrics(city_code)
    a_rates = {
        str(row["run"]): {
            "raw": float(row["raw_completion_rate"]),
            "conservative": float(row["conservative_completion_rate"]),
        }
        for row in phase3_metrics
        if row["scenario"] == "A"
    }
    if set(a_rates) != {"A#1", "A#2", "A#3"}:
        raise AssertionError(f"S10 A source set mismatch: {sorted(a_rates)}")

    signs: list[dict[str, Any]] = []
    for s_row in metrics:
        for a_run in ["A#1", "A#2", "A#3"]:
            raw_delta = float(s_row["raw_completion_rate"]) - a_rates[a_run]["raw"]
            conservative_delta = (
                float(s_row["conservative_completion_rate"])
                - a_rates[a_run]["conservative"]
            )
            signs.append(
                {
                    "s_run": s_row["run"],
                    "s_seed": s_row["seed"],
                    "a_run": a_run,
                    "raw_delta_rate": round(raw_delta, 9),
                    "raw_delta_percentage_points": round(raw_delta * 100, 6),
                    "raw_sign": sign(raw_delta),
                    "conservative_delta_rate": round(conservative_delta, 9),
                    "conservative_delta_percentage_points": round(
                        conservative_delta * 100, 6
                    ),
                    "conservative_sign": sign(conservative_delta),
                }
            )
    raw_counts = {
        value: sum(row["raw_sign"] == value for row in signs)
        for value in ["positive", "negative", "zero"]
    }
    conservative_counts = {
        value: sum(row["conservative_sign"] == value for row in signs)
        for value in ["positive", "negative", "zero"]
    }
    raw_rates = [float(row["raw_completion_rate"]) for row in metrics]
    conservative_rates = [float(row["conservative_completion_rate"]) for row in metrics]
    summary = {
        "bus_count": 10,
        "replicate_count": 5,
        "combination_count": 15,
        "raw_sign_counts": raw_counts,
        "conservative_sign_counts": conservative_counts,
        "raw_sign_consistent": max(raw_counts.values()) == 15,
        "conservative_sign_consistent": max(conservative_counts.values()) == 15,
        "raw_completion_rate_values": sorted(raw_rates),
        "conservative_completion_rate_values": sorted(conservative_rates),
        "raw_completion_rate_min_percent": min(raw_rates) * 100.0,
        "raw_completion_rate_max_percent": max(raw_rates) * 100.0,
        "conservative_completion_rate_min_percent": min(conservative_rates) * 100.0,
        "conservative_completion_rate_max_percent": max(conservative_rates) * 100.0,
        "decision109_stop_s_series": max(raw_counts.values()) != 15,
    }
    if len(summary["raw_completion_rate_values"]) != len(metrics):
        raise AssertionError("S10 raw series count mismatch")
    if len(summary["conservative_completion_rate_values"]) != len(metrics):
        raise AssertionError("S10 conservative series count mismatch")
    if len(signs) != 15 or any(
        "raw_sign" not in row or "conservative_sign" not in row for row in signs
    ):
        raise AssertionError("S10 raw/conservative sign parity mismatch")
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
