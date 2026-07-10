"""Reweight Type3/Type4 completion gaps by origin allocation mix."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROGRAM_DIR / "output"
SUMO_DIR = OUTPUT_DIR / "sumo"


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


def safe_rate(numerator: float, denominator: float) -> float | str:
    if denominator == 0:
        return ""
    return round(numerator / denominator, 6)


def allocation_shadow_reweighting(vehicle_type_map_path: Path) -> dict[str, Any]:
    grouped: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: {
            "type3": {"total": 0, "arrived": 0},
            "type4": {"total": 0, "arrived": 0},
        }
    )
    for row in read_csv_rows(vehicle_type_map_path):
        person_type = row.get("person_type")
        if person_type not in {"type3", "type4"}:
            continue
        bucket = grouped[row.get("origin_id", "")][person_type]
        bucket["total"] += 1
        if read_bool(row.get("arrived")):
            bucket["arrived"] += 1

    by_origin_rows: list[dict[str, Any]] = []
    type3_total = type3_arrived = type4_total = type4_arrived = 0
    type3_reweighted_numerator = 0.0
    type4_weight_total = 0
    paired_equal_completion = 0
    paired_origin_count = 0
    for origin_id, values in sorted(grouped.items()):
        t3 = values["type3"]
        t4 = values["type4"]
        t3_rate = safe_rate(float(t3["arrived"]), float(t3["total"]))
        t4_rate = safe_rate(float(t4["arrived"]), float(t4["total"]))
        gap = ""
        if t3_rate != "" and t4_rate != "":
            gap = round(float(t4_rate) - float(t3_rate), 6)
            paired_origin_count += 1
            if gap == 0:
                paired_equal_completion += 1
        if t3_rate != "" and t4["total"] > 0:
            type3_reweighted_numerator += float(t3_rate) * t4["total"]
            type4_weight_total += t4["total"]
        type3_total += t3["total"]
        type3_arrived += t3["arrived"]
        type4_total += t4["total"]
        type4_arrived += t4["arrived"]
        by_origin_rows.append(
            {
                "origin_id": origin_id,
                "type3_total": t3["total"],
                "type3_arrived": t3["arrived"],
                "type3_completion_rate": t3_rate,
                "type4_total": t4["total"],
                "type4_arrived": t4["arrived"],
                "type4_completion_rate": t4_rate,
                "type4_minus_type3_completion_rate": gap,
            }
        )

    type3_rate = safe_rate(float(type3_arrived), float(type3_total))
    type4_rate = safe_rate(float(type4_arrived), float(type4_total))
    type3_reweighted = safe_rate(type3_reweighted_numerator, float(type4_weight_total))
    observed_gap = (
        round(float(type4_rate) - float(type3_rate), 6)
        if type3_rate != "" and type4_rate != ""
        else ""
    )
    composition_effect = (
        round(float(type3_reweighted) - float(type3_rate), 6)
        if type3_reweighted != "" and type3_rate != ""
        else ""
    )
    within_origin_residual = (
        round(float(type4_rate) - float(type3_reweighted), 6)
        if type3_reweighted != "" and type4_rate != ""
        else ""
    )
    composition_share_of_gap = (
        safe_rate(float(composition_effect), float(observed_gap))
        if composition_effect != "" and observed_gap not in {"", 0}
        else ""
    )
    return {
        "summary": {
            "vehicle_type_map": str(vehicle_type_map_path),
            "type3_total": type3_total,
            "type3_arrived": type3_arrived,
            "type3_completion_rate": type3_rate,
            "type4_total": type4_total,
            "type4_arrived": type4_arrived,
            "type4_completion_rate": type4_rate,
            "observed_type4_minus_type3_gap": observed_gap,
            "type3_reweighted_to_type4_origin_mix": type3_reweighted,
            "composition_effect": composition_effect,
            "within_origin_residual": within_origin_residual,
            "composition_share_of_observed_gap": composition_share_of_gap,
            "paired_origin_count": paired_origin_count,
            "paired_equal_completion_origin_count": paired_equal_completion,
            "paired_equal_completion_origin_share": safe_rate(
                float(paired_equal_completion),
                float(paired_origin_count),
            ),
        },
        "by_origin_rows": by_origin_rows,
    }


def write_outputs(result: dict[str, Any], summary_json: Path, by_origin_csv: Path) -> None:
    summary = dict(result["summary"])
    summary["by_origin_csv"] = str(by_origin_csv)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(
        by_origin_csv,
        [
            "origin_id",
            "type3_total",
            "type3_arrived",
            "type3_completion_rate",
            "type4_total",
            "type4_arrived",
            "type4_completion_rate",
            "type4_minus_type3_completion_rate",
        ],
        result["by_origin_rows"],
    )


def default_paths(city_code: str, scenario: str) -> dict[str, Path]:
    base = SUMO_DIR / "regions" / city_code
    return {
        "vehicle_type_map": base / "evaluation" / f"{scenario}_e1_vehicle_type_map.csv",
        "summary_json": base / "evaluation" / f"{scenario}_diag_allocation_reweighting.json",
        "by_origin_csv": base / "evaluation" / f"{scenario}_diag_allocation_reweighting_by_origin.csv",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-code", default="08211")
    parser.add_argument("--scenario", default="scenario_a")
    parser.add_argument("--vehicle-type-map", type=Path)
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--by-origin-csv", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = default_paths(args.city_code, args.scenario)
    result = allocation_shadow_reweighting(args.vehicle_type_map or paths["vehicle_type_map"])
    write_outputs(
        result,
        args.summary_json or paths["summary_json"],
        args.by_origin_csv or paths["by_origin_csv"],
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
