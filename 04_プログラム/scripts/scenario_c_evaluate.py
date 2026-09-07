"""Scenario C の事前登録済み15 runを一次ログから統合評価する。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


PROGRAM_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_ROOT = (
    PROGRAM_ROOT
    / "output"
    / "sumo"
    / "regions"
    / "08211"
    / "experiments"
    / "scenario_c"
)

EXPECTED_RUNS = {
    "c1_15_strict": (23423, 42, 1),
    "c2_10_strict": (23423, 42, 1),
    "c2_20_strict": (23423, 42, 1),
    "c3_15_wade": (23423, 42, 1),
    "c4_15_strict_slow": (23423, 42, 1),
}
BASELINE_CONDITION = "c1_15_strict"
POPULATION = 21_539


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def as_float(value: object) -> float | None:
    text = str(value).strip()
    return float(text) if text else None


def percentile(values: list[float], probability: float) -> float | None:
    """Sorted samples上の線形補間percentile。"""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] + (ordered[high] - ordered[low]) * fraction


def discover_runs(runs_root: Path) -> tuple[dict[tuple[str, int], Path], list[str]]:
    """各事前登録セルについて技術的に有効なfull runを一意に選ぶ。"""
    candidates: defaultdict[tuple[str, int], list[Path]] = defaultdict(list)
    invalid_run_ids: list[str] = []
    for manifest_path in sorted(runs_root.glob("*/run_manifest.json")):
        manifest = read_json(manifest_path)
        condition_id = manifest.get("condition", {}).get("condition_id")
        seed = manifest.get("seed")
        key = (condition_id, seed)
        if condition_id not in EXPECTED_RUNS or seed not in EXPECTED_RUNS[condition_id]:
            continue
        if manifest.get("technical_valid") and manifest.get("full_sumo_run_executed"):
            candidates[key].append(manifest_path.parent)
        else:
            invalid_run_ids.append(str(manifest.get("run_id", manifest_path.parent.name)))

    selected: dict[tuple[str, int], Path] = {}
    missing: list[str] = []
    duplicates: list[str] = []
    for condition_id, seeds in EXPECTED_RUNS.items():
        for seed in seeds:
            key = (condition_id, seed)
            paths = candidates.get(key, [])
            if not paths:
                missing.append(f"{condition_id}/seed={seed}")
            elif len(paths) > 1:
                duplicates.append(
                    f"{condition_id}/seed={seed}: "
                    + ", ".join(path.name for path in paths)
                )
            else:
                selected[key] = paths[0]
    if missing or duplicates:
        details = []
        if missing:
            details.append("missing valid full runs: " + "; ".join(missing))
        if duplicates:
            details.append("duplicate valid full runs: " + "; ".join(duplicates))
        raise RuntimeError(" | ".join(details))
    return selected, invalid_run_ids


def validate_run(run_dir: Path) -> tuple[dict, dict, dict]:
    manifest = read_json(run_dir / "run_manifest.json")
    summary = read_json(run_dir / "run_summary.json")
    accounting = read_json(run_dir / "accounting_validation.json")
    checks = {
        "technical_valid": manifest.get("technical_valid") is True,
        "full_sumo_run_executed": manifest.get("full_sumo_run_executed") is True,
        "last_sim_time": manifest.get("last_sim_time", 0) >= 21_600,
        "population": summary.get("population") == POPULATION,
        "population_closes": accounting.get("population_closes") is True,
        "completion_accounting_closes": accounting.get("completion_accounting_closes") is True,
        "closures": (
            accounting.get("processed_closure_event_count")
            == accounting.get("expected_closure_event_count")
            == 8
        ),
        "closed_edge_entry_violations": (
            accounting.get("closed_edge_entry_violation_count") == 0
        ),
        "pending_reroutes": (
            accounting.get("pending_person_reroute_count", 0)
            + accounting.get("pending_vehicle_reroute_count", 0)
            == 0
        ),
        "run_error": not accounting.get("run_error") and not manifest.get("run_error"),
        "sumo_error": not any(
            line.startswith("Error:")
            for line in (run_dir / "sumo.log").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        ),
        "existing_outputs_unchanged": manifest.get("existing_outputs_modified") is False,
        "a_b_sentinels": manifest.get("sentinel_before") == manifest.get("sentinel_after"),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"{run_dir.name}: validation failed: {', '.join(failed)}")
    if summary["completed_people"] + accounting["unfinished_people"] != POPULATION:
        raise RuntimeError(f"{run_dir.name}: completion population does not close")
    evaluation_inputs = (
        "run_summary.json",
        "accounting_validation.json",
        "vehicle_log.csv",
        "person_log.csv",
        "car_occupancy_ledger.csv",
        "walk_person_ledger.csv",
    )
    recorded_sha = manifest.get("output_sha256", {})
    for filename in evaluation_inputs:
        path = run_dir / filename
        if filename not in recorded_sha or sha256(path) != recorded_sha[filename]:
            raise RuntimeError(f"{run_dir.name}: output SHA mismatch: {filename}")
    return manifest, summary, accounting


def build_people(run_dir: Path) -> list[dict]:
    vehicle_by_id = {row["vehicle_id"]: row for row in read_csv(run_dir / "vehicle_log.csv")}
    walk_log_by_id = {row["person_id"]: row for row in read_csv(run_dir / "person_log.csv")}
    walk_ledger_by_id = {
        row["person_id"]: row for row in read_csv(run_dir / "walk_person_ledger.csv")
    }
    people: list[dict] = []

    for row in read_csv(run_dir / "car_occupancy_ledger.csv"):
        vehicle = vehicle_by_id[row["vehicle_id"]]
        people.append(
            {
                "person_id": row["person_id"],
                "mode": "car",
                "age_group": row["age_group"],
                "origin_id": row["origin_id"],
                "destination_id": vehicle["to_sumo_edge_id"],
                "completed": as_bool(vehicle["arrived"]),
                "arrival": as_float(vehicle["arrival"]),
                "duration": as_float(vehicle["duration"]),
                "final_status": vehicle["final_status"],
            }
        )

    for person_id, person in walk_log_by_id.items():
        ledger = walk_ledger_by_id[person_id]
        people.append(
            {
                "person_id": person_id,
                "mode": "walk",
                "age_group": person["age_group"],
                "origin_id": person["origin_id"],
                "destination_id": ledger["shelter_id"],
                "completed": as_bool(person["arrived"]),
                "arrival": as_float(person["arrival"]),
                "duration": as_float(person["duration"]),
                "final_status": person["final_status"],
            }
        )
    if len(people) != POPULATION or len({row["person_id"] for row in people}) != POPULATION:
        raise RuntimeError(f"{run_dir.name}: person-level evaluation ledger does not close")
    return people


def summarize_event_logs(
    vehicle_rows: list[dict[str, str]], person_rows: list[dict[str, str]]
) -> dict:
    return {
        "vehicle_count": len(vehicle_rows),
        "vehicle_reroute_count": sum(int(row["reroute_count"]) for row in vehicle_rows),
        "vehicle_reroute_failed_count": sum(
            as_bool(row["reroute_failed"]) for row in vehicle_rows
        ),
        "vehicle_long_stopped_count": sum(
            as_bool(row["long_stopped"]) for row in vehicle_rows
        ),
        "vehicle_max_consecutive_stop_s": max(
            (float(row["max_consecutive_stop_sec"]) for row in vehicle_rows),
            default=0,
        ),
        "walk_person_count": len(person_rows),
        "walk_xml_emitted_count": sum(
            as_bool(row["person_xml_emitted"]) for row in person_rows
        ),
        "walk_reroute_count": sum(int(row["reroute_count"]) for row in person_rows),
        "walk_reroute_failed_count": sum(
            as_bool(row["reroute_failed"]) for row in person_rows
        ),
        "walk_shallow_exposed_people": sum(
            int(row["shallow_entry_count"]) > 0 for row in person_rows
        ),
        "walk_shallow_entry_count": sum(
            int(row["shallow_entry_count"]) for row in person_rows
        ),
        "walk_shallow_person_seconds": sum(
            int(row["shallow_time_sec"]) for row in person_rows
        ),
        "walk_dry_speed_restore_count": sum(
            int(row["dry_speed_restore_count"]) for row in person_rows
        ),
        "walk_max_consecutive_stop_s": max(
            (float(row["max_consecutive_stop_sec"]) for row in person_rows),
            default=0,
        ),
    }


def grouped_person_metrics(
    people: list[dict], keys: tuple[str, ...]
) -> list[dict]:
    groups: defaultdict[tuple, list[dict]] = defaultdict(list)
    for person in people:
        groups[tuple(person[key] for key in keys)].append(person)
    rows = []
    for values, members in sorted(groups.items()):
        completed = [member for member in members if member["completed"]]
        arrivals = [member["arrival"] for member in completed if member["arrival"] is not None]
        durations = [member["duration"] for member in completed if member["duration"] is not None]
        row = dict(zip(keys, values))
        row.update(
            {
                "population": len(members),
                "completed_people": len(completed),
                "completion_rate_percent": 100 * len(completed) / len(members),
                "arrival_time_median_s": statistics.median(arrivals) if arrivals else "",
                "arrival_time_p90_s": percentile(arrivals, 0.90) or "",
                "duration_median_s": statistics.median(durations) if durations else "",
                "duration_p90_s": percentile(durations, 0.90) or "",
            }
        )
        rows.append(row)
    return rows


def load_static_statuses(path: Path) -> dict[tuple[str, str, str, str], str]:
    statuses = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["time_id"] not in {"t0", "t7"}:
                continue
            key = (row["mode"], row["policy"], row["time_id"], row["origin_id"])
            if key in statuses:
                raise RuntimeError(f"duplicate static status: {key}")
            statuses[key] = row["route_status"]
    return statuses


def evaluate_runs(runs_root: Path, static_path: Path, output_dir: Path) -> dict:
    selected, invalid_run_ids = discover_runs(runs_root)
    static_statuses = load_static_statuses(static_path)
    run_metrics: list[dict] = []
    age_metrics: list[dict] = []
    mode_metrics: list[dict] = []
    origin_metrics: list[dict] = []
    destination_metrics: list[dict] = []
    final_status_counts: list[dict] = []
    run_event_metrics: list[dict] = []
    static_cross_counts: Counter = Counter()
    static_summary_counts: Counter = Counter()
    input_sha: dict[str, str] = {"static_route_snapshots.csv": sha256(static_path)}

    for condition_id, seeds in EXPECTED_RUNS.items():
        for seed in seeds:
            run_dir = selected[(condition_id, seed)]
            manifest, summary, accounting = validate_run(run_dir)
            input_sha[f"{run_dir.name}/run_manifest.json"] = sha256(
                run_dir / "run_manifest.json"
            )
            people = build_people(run_dir)
            car_population = sum(person["mode"] == "car" for person in people)
            walk_population = POPULATION - car_population
            completed_car = sum(
                person["mode"] == "car" and person["completed"] for person in people
            )
            completed_walk = sum(
                person["mode"] == "walk" and person["completed"] for person in people
            )
            if completed_car != summary["arrived_car_people"] or completed_walk != summary["arrived_walk_people"]:
                raise RuntimeError(f"{run_dir.name}: person join disagrees with run_summary")
            run_base = {
                "run_id": manifest["run_id"],
                "condition_id": condition_id,
                "cohort": summary["cohort"],
                "scenario_id": summary["scenario_id"],
                "policy": summary["policy"],
                "elderly_speed_mps": summary["elderly_speed_mps"],
                "seed": seed,
            }
            run_metrics.append(
                {
                    **run_base,
                    "population": POPULATION,
                    "completed_people": summary["completed_people"],
                    "completion_rate_percent": 100 * summary["completion_rate"],
                    "unfinished_people": accounting["unfinished_people"],
                    "car_population": car_population,
                    "car_completed_people": completed_car,
                    "car_completion_rate_percent": 100 * completed_car / car_population,
                    "walk_population": walk_population,
                    "walk_completed_people": completed_walk,
                    "walk_completion_rate_percent": 100 * completed_walk / walk_population,
                }
            )
            run_event_metrics.append(
                {
                    **run_base,
                    **summarize_event_logs(
                        read_csv(run_dir / "vehicle_log.csv"),
                        read_csv(run_dir / "person_log.csv"),
                    ),
                }
            )

            for row in grouped_person_metrics(people, ("age_group",)):
                age_metrics.append({**run_base, **row})
            for row in grouped_person_metrics(people, ("mode",)):
                mode_metrics.append({**run_base, **row})
            for row in grouped_person_metrics(people, ("mode", "origin_id")):
                origin_metrics.append({**run_base, **row})
            for row in grouped_person_metrics(people, ("mode", "destination_id")):
                destination_metrics.append({**run_base, **row})
            statuses = Counter((person["mode"], person["final_status"]) for person in people)
            for (mode, final_status), count in sorted(statuses.items()):
                final_status_counts.append(
                    {**run_base, "mode": mode, "final_status": final_status, "people": count}
                )

            walk_policy = summary["policy"]
            for person in people:
                static_mode = "car" if person["mode"] == "car" else "walk"
                static_policy = "vehicle" if person["mode"] == "car" else walk_policy
                dynamic_status = "completed" if person["completed"] else "unfinished"
                for time_id in ("t0", "t7"):
                    key = (static_mode, static_policy, time_id, person["origin_id"])
                    if key not in static_statuses:
                        raise RuntimeError(f"missing static status: {key}")
                    route_status = static_statuses[key]
                    static_cross_counts[
                        (manifest["run_id"], condition_id, seed, person["mode"], time_id, route_status, dynamic_status)
                    ] += 1
                    bucket = "static_reachable" if route_status == "reachable" else "static_unreachable"
                    static_summary_counts[
                        (manifest["run_id"], condition_id, seed, person["mode"], time_id, bucket, dynamic_status)
                    ] += 1

    condition_summary = []
    summary_metrics = (
        "completed_people",
        "completion_rate_percent",
        "car_completed_people",
        "car_completion_rate_percent",
        "walk_completed_people",
        "walk_completion_rate_percent",
    )
    by_condition: defaultdict[str, list[dict]] = defaultdict(list)
    for row in run_metrics:
        by_condition[row["condition_id"]].append(row)
    for condition_id in EXPECTED_RUNS:
        rows = by_condition[condition_id]
        for metric in summary_metrics:
            values = [float(row[metric]) for row in rows]
            condition_summary.append(
                {
                    "condition_id": condition_id,
                    "metric": metric,
                    "run_count": len(values),
                    "median": statistics.median(values),
                    "minimum": min(values),
                    "maximum": max(values),
                }
            )

    run_by_key = {(row["condition_id"], row["seed"]): row for row in run_metrics}
    paired_sensitivity = []
    for condition_id in EXPECTED_RUNS:
        if condition_id == BASELINE_CONDITION:
            continue
        for seed in EXPECTED_RUNS[condition_id]:
            baseline = run_by_key[(BASELINE_CONDITION, seed)]
            comparison = run_by_key[(condition_id, seed)]
            paired_sensitivity.append(
                {
                    "baseline_condition_id": BASELINE_CONDITION,
                    "comparison_condition_id": condition_id,
                    "seed": seed,
                    "completed_people_difference": comparison["completed_people"] - baseline["completed_people"],
                    "completion_rate_percentage_point_difference": comparison["completion_rate_percent"] - baseline["completion_rate_percent"],
                    "car_completed_people_difference": comparison["car_completed_people"] - baseline["car_completed_people"],
                    "walk_completed_people_difference": comparison["walk_completed_people"] - baseline["walk_completed_people"],
                }
            )

    static_cross = [
        {
            "run_id": key[0],
            "condition_id": key[1],
            "seed": key[2],
            "mode": key[3],
            "time_id": key[4],
            "static_route_status": key[5],
            "dynamic_status": key[6],
            "people": count,
        }
        for key, count in sorted(static_cross_counts.items())
    ]
    static_dynamic_summary = []
    summary_keys = sorted({key[:5] for key in static_summary_counts})
    for key in summary_keys:
        sr_dc = static_summary_counts[key + ("static_reachable", "completed")]
        sr_du = static_summary_counts[key + ("static_reachable", "unfinished")]
        su_dc = static_summary_counts[key + ("static_unreachable", "completed")]
        su_du = static_summary_counts[key + ("static_unreachable", "unfinished")]
        static_reachable = sr_dc + sr_du
        dynamic_completed = sr_dc + su_dc
        static_dynamic_summary.append(
            {
                "run_id": key[0],
                "condition_id": key[1],
                "seed": key[2],
                "mode": key[3],
                "time_id": key[4],
                "unit": "people",
                "static_reachable_people": static_reachable,
                "dynamic_completed_people": dynamic_completed,
                "dynamic_minus_static_people": dynamic_completed - static_reachable,
                "both_people": sr_dc,
                "static_only_people": sr_du,
                "dynamic_only_people": su_dc,
                "neither_people": su_du,
            }
        )

    outputs = {
        "run_metrics.csv": run_metrics,
        "condition_summary.csv": condition_summary,
        "paired_sensitivity.csv": paired_sensitivity,
        "age_group_metrics.csv": age_metrics,
        "mode_metrics.csv": mode_metrics,
        "final_status_counts.csv": final_status_counts,
        "run_event_metrics.csv": run_event_metrics,
        "origin_metrics.csv": origin_metrics,
        "destination_metrics.csv": destination_metrics,
        "static_dynamic_cross.csv": static_cross,
        "static_dynamic_summary.csv": static_dynamic_summary,
    }
    for filename, rows in outputs.items():
        if not rows:
            raise RuntimeError(f"no rows generated for {filename}")
        write_csv(output_dir / filename, list(rows[0]), rows)

    manifest = {
        "evaluation_id": "scenario_c_15run_evaluation_20260810",
        "population_denominator": POPULATION,
        "baseline_condition_id": BASELINE_CONDITION,
        "expected_condition_seed_count": 15,
        "selected_run_count": len(selected),
        "selected_run_ids": [selected[key].name for key in sorted(selected)],
        "preserved_invalid_run_ids": sorted(invalid_run_ids),
        "percentile_method": "linear interpolation at (n-1)*p",
        "input_sha256": input_sha,
        "output_sha256": {
            filename: sha256(output_dir / filename) for filename in sorted(outputs)
        },
        "script_sha256": sha256(Path(__file__)),
    }
    with (output_dir / "manifest.json").open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=SCENARIO_ROOT / "runs")
    parser.add_argument(
        "--static-snapshots",
        type=Path,
        default=SCENARIO_ROOT / "static_alignment_20260826" / "static_route_snapshots.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SCENARIO_ROOT / "evaluation_20260810",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = evaluate_runs(args.runs_root, args.static_snapshots, args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
