"""Phase 3 Type3/Type4 individual ledger and deterministic accounting.

SUMO moves vehicles, not individual evacuees.  This module adds a separate,
reproducible person ledger that maps Type3/Type4 residents to either a rescue
vehicle, a bus passenger record, or an explicit unassigned state.  It never
overwrites the canonical Phase 3 runs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
DEFAULT_REGION_DIR = PROGRAM_DIR / "output" / "sumo" / "regions" / "08211"
DEFAULT_REPLICATES = DEFAULT_REGION_DIR / "evaluation" / "phase3r_e1_replicate_metrics.csv"
DEFAULT_OUTPUT_DIR = DEFAULT_REGION_DIR / "experiments" / "type34_split"
DEFAULT_FIGURE_DIR = PROGRAM_DIR.parent / "06_研究結果" / "phase3" / "figures"
PEOPLE_PER_RESCUE_VEHICLE = 2.3

LEDGER_FIELDS = [
    "person_id",
    "origin_id",
    "KEY_CODE",
    "person_type",
    "category",
    "scenario",
    "run",
    "seed",
    "assigned_mode",
    "assigned_vehicle_id",
    "assigned_bus_id",
    "source_passenger_id",
    "board_time_s",
    "arrival_time_s",
    "arrived",
    "final_status",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def read_int(value: Any) -> int:
    return max(0, int(round(float(value or 0))))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def proportional_counts(raw_values: list[float], target_total: int) -> list[int]:
    """Largest-remainder integer allocation with per-cell upper bounds."""
    values = [max(0.0, float(value)) for value in raw_values]
    target = min(max(0, int(target_total)), int(sum(values)))
    if target == 0:
        return [0] * len(values)
    total = sum(values)
    quotas = [value / total * target for value in values]
    counts = [min(int(value), math.floor(quota)) for value, quota in zip(values, quotas)]
    remainder = target - sum(counts)
    order = sorted(
        range(len(values)),
        key=lambda index: (quotas[index] - counts[index], values[index] - counts[index], -index),
        reverse=True,
    )
    while remainder:
        progressed = False
        for index in order:
            if counts[index] < int(values[index]):
                counts[index] += 1
                remainder -= 1
                progressed = True
                if remainder == 0:
                    break
        if not progressed:
            raise ValueError("integer allocation cannot satisfy target")
    return counts


def build_base_people(agent_types_path: Path) -> list[dict[str, Any]]:
    """Create stable Type3/Type4 IDs from the canonical origin table."""
    people: list[dict[str, Any]] = []
    for row in sorted(read_csv_rows(agent_types_path), key=lambda item: item["origin_id"]):
        origin_id = row["origin_id"]
        key_code = row.get("KEY_CODE", "")
        type3_count = read_int(row.get("type3_no_car_non_elderly_pop"))
        type4_count = read_int(row.get("type4_no_car_elderly_pop"))
        mobility_count = min(
            type3_count,
            read_int(row.get("type3_mobility_limited_candidate_pop")),
        )
        for index in range(1, type3_count + 1):
            people.append(
                {
                    "person_id": f"{origin_id}_type3_{index:04d}",
                    "origin_id": origin_id,
                    "KEY_CODE": key_code,
                    "person_type": "type3",
                    "category": "type3_mob" if index <= mobility_count else "type3",
                }
            )
        for index in range(1, type4_count + 1):
            people.append(
                {
                    "person_id": f"{origin_id}_type4_{index:04d}",
                    "origin_id": origin_id,
                    "KEY_CODE": key_code,
                    "person_type": "type4",
                    "category": "type4",
                }
            )
    return people


def _initialize_run_rows(
    people: list[dict[str, Any]], scenario: str, run: str, seed: str
) -> list[dict[str, Any]]:
    return [
        {
            **person,
            "scenario": scenario,
            "run": run,
            "seed": seed,
            "assigned_mode": "unassigned",
            "assigned_vehicle_id": "",
            "assigned_bus_id": "",
            "source_passenger_id": "",
            "board_time_s": "",
            "arrival_time_s": "",
            "arrived": False,
            "final_status": "unassigned",
        }
        for person in people
    ]


def _available_indices(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[int]]:
    available: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        if row["assigned_mode"] == "unassigned":
            available[(row["origin_id"], row["category"])].append(index)
    return available


def assign_bus_people(rows: list[dict[str, Any]], passenger_log_path: Path | None) -> None:
    if passenger_log_path is None:
        return
    available = _available_indices(rows)
    passengers = sorted(
        read_csv_rows(passenger_log_path),
        key=lambda row: (
            row.get("origin_id", ""),
            float(row.get("board_time_s") or 0),
            row.get("bus_id", ""),
            int(float(row.get("trip_seq") or 0)),
            row.get("passenger_id", ""),
        ),
    )
    for passenger in passengers:
        origin_id = passenger.get("origin_id", "")
        category = passenger.get("category", "")
        if category not in {"type3", "type3_mob", "type4"}:
            category = "type4" if str(passenger.get("person_type")) == "4" else "type3"
        key = (origin_id, category)
        if not available[key]:
            raise ValueError(f"bus passenger exceeds ledger population: {origin_id}/{category}")
        index = available[key].pop(0)
        arrived = read_bool(passenger.get("arrived"))
        rows[index].update(
            {
                "assigned_mode": "bus",
                "assigned_bus_id": passenger.get("bus_id", ""),
                "source_passenger_id": passenger.get("passenger_id", ""),
                "board_time_s": passenger.get("board_time_s", ""),
                "arrival_time_s": passenger.get("arrival_time_s", ""),
                "arrived": arrived,
                "final_status": "arrived" if arrived else "bus_not_arrived",
            }
        )


def assign_rescue_people(
    rows: list[dict[str, Any]],
    assignments_path: Path,
    vehicle_log_path: Path,
    people_per_vehicle: float = PEOPLE_PER_RESCUE_VEHICLE,
) -> None:
    assignments = [
        row
        for row in read_csv_rows(assignments_path)
        if row.get("vehicle_kind") == "rescue_car"
    ]
    vehicles_by_origin: dict[str, list[str]] = defaultdict(list)
    for row in assignments:
        vehicles_by_origin[row["origin_id"]].append(row["vehicle_id"])
    vehicle_log = {row["vehicle_id"]: row for row in read_csv_rows(vehicle_log_path)}

    available = _available_indices(rows)
    for origin_id, vehicle_ids in sorted(vehicles_by_origin.items()):
        vehicle_ids = sorted(vehicle_ids)
        type3_indices = sorted(
            available[(origin_id, "type3_mob")] + available[(origin_id, "type3")],
            key=lambda index: rows[index]["person_id"],
        )
        type4_indices = sorted(available[(origin_id, "type4")])
        capacity_total = min(
            len(type3_indices) + len(type4_indices),
            int(round(len(vehicle_ids) * people_per_vehicle)),
        )
        target3, target4 = proportional_counts(
            [len(type3_indices), len(type4_indices)], capacity_total
        )
        # Each rescue vehicle is homogeneous and holds at most three people.
        # If both type-specific remainders would require one vehicle too many,
        # reduce only the minimum number of assignments needed for feasibility.
        while math.ceil(target3 / 3) + math.ceil(target4 / 3) > len(vehicle_ids):
            if target3 >= target4 and target3 > 0:
                target3 -= 1
            elif target4 > 0:
                target4 -= 1
            else:
                raise AssertionError(f"rescue allocation infeasible at {origin_id}")
        groups: list[list[int]] = []
        for indices, target in ((type3_indices, target3), (type4_indices, target4)):
            selected = indices[:target]
            groups.extend(selected[start : start + 3] for start in range(0, len(selected), 3))

        for vehicle_id, occupants in zip(vehicle_ids, groups):
            log = vehicle_log.get(vehicle_id)
            arrived = bool(log and read_bool(log.get("arrived")))
            status = "arrived" if arrived else ("vehicle_not_arrived" if log else "vehicle_missing")
            for index in occupants:
                rows[index].update(
                    {
                        "assigned_mode": "rescue",
                        "assigned_vehicle_id": vehicle_id,
                        "arrival_time_s": log.get("arrival", "") if log else "",
                        "arrived": arrived,
                        "final_status": status,
                    }
                )


def validate_ledger(rows: list[dict[str, Any]]) -> dict[str, int]:
    ids = [row["person_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise AssertionError("duplicate person_id")
    invalid_modes = [row for row in rows if row["assigned_mode"] not in {"unassigned", "rescue", "bus"}]
    if invalid_modes:
        raise AssertionError("invalid assigned_mode")
    for row in rows:
        if row["assigned_mode"] == "bus" and row["assigned_vehicle_id"]:
            raise AssertionError("bus/rescue double assignment")
        if row["assigned_mode"] == "rescue" and row["assigned_bus_id"]:
            raise AssertionError("rescue/bus double assignment")
        if read_bool(row["arrived"]) and row["assigned_mode"] == "unassigned":
            raise AssertionError("unassigned person cannot arrive")
    return {
        "person_count": len(rows),
        "unique_person_count": len(set(ids)),
        "type3_count": sum(row["person_type"] == "type3" for row in rows),
        "type4_count": sum(row["person_type"] == "type4" for row in rows),
        "bus_rescue_overlap_count": 0,
    }


def compute_person_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for person_type in ("type3", "type4", "type34"):
        selected = rows if person_type == "type34" else [row for row in rows if row["person_type"] == person_type]
        denominator = len(selected)
        arrived = sum(read_bool(row["arrived"]) for row in selected)
        rescue = [row for row in selected if row["assigned_mode"] == "rescue"]
        bus = [row for row in selected if row["assigned_mode"] == "bus"]
        unassigned = [row for row in selected if row["assigned_mode"] == "unassigned"]
        metrics.append(
            {
                "person_type": person_type,
                "denominator_people": denominator,
                "arrived_people": arrived,
                "not_arrived_people": denominator - arrived,
                "completion_rate": round(arrived / denominator, 9) if denominator else "",
                "rescue_assigned_people": len(rescue),
                "rescue_arrived_people": sum(read_bool(row["arrived"]) for row in rescue),
                "bus_assigned_people": len(bus),
                "bus_arrived_people": sum(read_bool(row["arrived"]) for row in bus),
                "unassigned_people": len(unassigned),
            }
        )
    return metrics


def build_person_ledger(
    *,
    agent_types_path: Path,
    assignments_path: Path,
    vehicle_log_path: Path,
    scenario: str,
    run: str,
    seed: str,
    passenger_log_path: Path | None = None,
    people_per_vehicle: float = PEOPLE_PER_RESCUE_VEHICLE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows = _initialize_run_rows(build_base_people(agent_types_path), scenario, run, seed)
    assign_bus_people(rows, passenger_log_path)
    assign_rescue_people(rows, assignments_path, vehicle_log_path, people_per_vehicle)
    diagnostics = validate_ledger(rows)
    metrics = compute_person_metrics(rows)
    return rows, metrics, diagnostics


def write_run_outputs(
    output_dir: Path,
    rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    write_csv(output_dir / "person_ledger.csv", LEDGER_FIELDS, rows)
    write_csv(output_dir / "type34_person_metrics.csv", list(metrics[0].keys()), metrics)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def aggregate_metrics(
    replicate_rows: list[dict[str, Any]], paired_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    scenario_summary: dict[str, Any] = {}
    for scenario in ("A", "B"):
        scenario_summary[scenario] = {}
        for person_type in ("type3", "type4", "type34"):
            values = [
                float(row["completion_rate"])
                for row in replicate_rows
                if row["scenario"] == scenario and row["person_type"] == person_type
            ]
            scenario_summary[scenario][person_type] = {
                "run_count": len(values),
                "median_completion_rate": round(statistics.median(values), 9),
                "min_completion_rate": round(min(values), 9),
                "max_completion_rate": round(max(values), 9),
            }
    paired_summary: dict[str, Any] = {}
    for person_type in ("type3", "type4", "type34"):
        values = [
            float(row["b_minus_a_rate"])
            for row in paired_rows
            if row["person_type"] == person_type
        ]
        paired_summary[person_type] = {
            "pair_count": len(values),
            "median_b_minus_a_rate": round(statistics.median(values), 9),
            "min_b_minus_a_rate": round(min(values), 9),
            "max_b_minus_a_rate": round(max(values), 9),
            "positive_count": sum(value > 0 for value in values),
            "negative_count": sum(value < 0 for value in values),
            "zero_count": sum(value == 0 for value in values),
            "direction_consistent": all(value > 0 for value in values)
            or all(value < 0 for value in values),
        }
    return {
        "scenario_completion_rates": scenario_summary,
        "paired_differences": paired_summary,
    }


def write_type34_figure(
    replicate_rows: list[dict[str, Any]], paired_rows: list[dict[str, Any]], figure_dir: Path
) -> list[Path]:
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Yu Gothic", "Meiryo", "Noto Sans CJK JP", "DejaVu Sans"],
            "svg.fonttype": "none",
            "axes.unicode_minus": False,
        }
    )
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    positions = {("A", "type3"): 0, ("B", "type3"): 1, ("A", "type4"): 3, ("B", "type4"): 4}
    colors = {"A": "#4C78A8", "B": "#F58518"}
    for row in replicate_rows:
        if row["person_type"] not in {"type3", "type4"}:
            continue
        x = positions[(row["scenario"], row["person_type"])]
        ax.scatter(x, float(row["completion_rate"]) * 100, color=colors[row["scenario"]], s=44, zorder=3)
    paired_index = {
        (str(row["seed"]), row["person_type"]): row for row in paired_rows
    }
    for seed in sorted({str(row["seed"]) for row in paired_rows}, key=int):
        for person_type in ("type3", "type4"):
            pair = paired_index[(seed, person_type)]
            x1 = positions[("A", person_type)]
            x2 = positions[("B", person_type)]
            ax.plot(
                [x1, x2],
                [float(pair["a_completion_rate"]) * 100, float(pair["b_completion_rate"]) * 100],
                color="#9CA3AF",
                linewidth=1,
                alpha=0.7,
                zorder=1,
            )
    ax.set_xticks([0, 1, 3, 4], ["Type3\nA", "Type3\nB", "Type4\nA", "Type4\nB"])
    ax.set_ylabel("避難完了率（%）")
    ax.set_title("図5-5-1  個人台帳によるType3・Type4分離完了率")
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(
        0.01,
        -0.18,
        "点はrun、線は同一seedのA/B。個人台帳仮定に基づく別実験であり、現行正式結果へ混在させない。",
        transform=ax.transAxes,
        fontsize=9,
    )
    fig.tight_layout()
    svg = figure_dir / "fig5-5-1_type34_split_completion_rates.svg"
    png = figure_dir / "fig5-5-1_type34_split_completion_rates.png"
    fig.savefig(svg, bbox_inches="tight")
    fig.savefig(png, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return [svg, png]


def run_batch(replicates_path: Path, region_dir: Path, output_dir: Path) -> dict[str, Any]:
    agent_types = region_dir / "derived" / "agent_types.csv"
    replicate_rows: list[dict[str, Any]] = []
    manifest_runs: list[dict[str, Any]] = []
    for replicate in read_csv_rows(replicates_path):
        scenario = replicate["scenario"].lower()
        run = replicate["run"]
        seed = replicate["seed"]
        artifact = Path(replicate["artifact_dir"])
        assignments = region_dir / "derived" / f"scenario_{scenario}_vehicle_assignments.csv"
        vehicle_log = artifact / f"scenario_{scenario}_vehicle_log.csv"
        passenger_log = artifact / "scenario_b_passenger_log.csv" if scenario == "b" else None
        if passenger_log is not None and not passenger_log.exists():
            raise FileNotFoundError(passenger_log)
        rows, metrics, diagnostics = build_person_ledger(
            agent_types_path=agent_types,
            assignments_path=assignments,
            vehicle_log_path=vehicle_log,
            passenger_log_path=passenger_log,
            scenario=scenario.upper(),
            run=run,
            seed=seed,
        )
        run_dir = output_dir / "runs" / run.replace("#", "_")
        source_paths = [agent_types, assignments, vehicle_log]
        if passenger_log is not None:
            source_paths.append(passenger_log)
        summary = {
            "scenario": scenario.upper(),
            "run": run,
            "seed": int(seed),
            "method": "deterministic_person_ledger_postprocessing",
            "people_per_rescue_vehicle": PEOPLE_PER_RESCUE_VEHICLE,
            "diagnostics": diagnostics,
            "metrics": {row["person_type"]: row for row in metrics},
            "sources": {str(path): sha256(path) for path in source_paths},
        }
        write_run_outputs(run_dir, rows, metrics, summary)
        for metric in metrics:
            replicate_rows.append(
                {
                    "scenario": scenario.upper(),
                    "run": run,
                    "seed": int(seed),
                    **metric,
                    "artifact_dir": str(artifact),
                    "ledger_dir": str(run_dir),
                }
            )
        manifest_runs.append(summary)

    fields = list(replicate_rows[0].keys())
    write_csv(output_dir / "type34_split_replicate_metrics.csv", fields, replicate_rows)
    paired_rows: list[dict[str, Any]] = []
    indexed = {
        (row["scenario"], str(row["seed"]), row["person_type"]): row
        for row in replicate_rows
    }
    common_seeds = sorted(
        {str(row["seed"]) for row in replicate_rows if row["scenario"] == "A"}
        & {str(row["seed"]) for row in replicate_rows if row["scenario"] == "B"},
        key=int,
    )
    for seed in common_seeds:
        for person_type in ("type3", "type4", "type34"):
            a = indexed[("A", seed, person_type)]
            b = indexed[("B", seed, person_type)]
            paired_rows.append(
                {
                    "seed": int(seed),
                    "person_type": person_type,
                    "a_run": a["run"],
                    "b_run": b["run"],
                    "a_completion_rate": a["completion_rate"],
                    "b_completion_rate": b["completion_rate"],
                    "b_minus_a_rate": round(float(b["completion_rate"]) - float(a["completion_rate"]), 9),
                    "b_minus_a_percentage_points": round(
                        (float(b["completion_rate"]) - float(a["completion_rate"])) * 100, 6
                    ),
                }
            )
    write_csv(output_dir / "type34_split_paired_differences.csv", list(paired_rows[0].keys()), paired_rows)
    aggregate = aggregate_metrics(replicate_rows, paired_rows)
    (output_dir / "type34_split_summary.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    figures = write_type34_figure(replicate_rows, paired_rows, DEFAULT_FIGURE_DIR)
    manifest = {
        "method": "deterministic_person_ledger_postprocessing",
        "formal_result_status": "separate_experiment_do_not_merge_with_canonical_phase3",
        "replicate_source": str(replicates_path),
        "replicate_source_sha256": sha256(replicates_path),
        "run_count": len(manifest_runs),
        "paired_seed_count": len(common_seeds),
        "aggregate": aggregate,
        "figures": [str(path) for path in figures],
        "runs": manifest_runs,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    batch = subparsers.add_parser("batch", help="build ledgers for the canonical 8-run table")
    batch.add_argument("--replicates", type=Path, default=DEFAULT_REPLICATES)
    batch.add_argument("--region-dir", type=Path, default=DEFAULT_REGION_DIR)
    batch.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "batch":
        manifest = run_batch(args.replicates, args.region_dir, args.output_dir)
        print(f"[INFO] generated Type3/Type4 ledgers: {manifest['run_count']} runs")
        print(f"[INFO] output: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
