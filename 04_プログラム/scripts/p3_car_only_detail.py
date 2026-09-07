"""Re-aggregate detailed car-only metrics from canonical Scenario A runs.

This is a read-only post-processing step.  It never launches SUMO and writes
only to a dedicated teacher-feedback evaluation directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from p3_stagnation_decomposition import decompose_stagnation, edge_from_lane


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
REGION_DIR = PROGRAM_DIR / "output" / "sumo" / "regions" / "08211"
DEFAULT_REPLICATES = REGION_DIR / "evaluation" / "phase3r_e1_replicate_metrics.csv"
DEFAULT_ASSIGNMENTS = REGION_DIR / "derived" / "scenario_a_vehicle_assignments.csv"
DEFAULT_AGENT_TYPES = REGION_DIR / "derived" / "agent_types.csv"
DEFAULT_NET = REGION_DIR / "network" / "08211.net.xml"
DEFAULT_CLOSURE = REGION_DIR / "derived" / "closure_timeline_sumo.json"
DEFAULT_OUTPUT = REGION_DIR / "evaluation" / "teacher_feedback_20260826" / "car_only_detail"
CANONICAL_RUNS = ("A#1", "A#2", "A#3")
FCD_PERIOD_SEC = 60.0
STOP_SPEED_MPS = 0.1


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if fields:
            writer.writeheader()
            writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def as_float(value: Any, default: float = 0.0) -> float:
    if value in {None, ""}:
        return default
    return float(value)


def rounded(value: float) -> float:
    return round(value, 6)


def safe_rate(numerator: float, denominator: float) -> float | str:
    return rounded(numerator / denominator) if denominator else ""


def mean(values: list[float]) -> float | str:
    return rounded(sum(values) / len(values)) if values else ""


def median(values: list[float]) -> float | str:
    return rounded(float(statistics.median(values))) if values else ""


def load_canonical_runs(path: Path) -> list[dict[str, Any]]:
    rows = [row for row in read_csv_rows(path) if row.get("scenario") == "A"]
    by_run = {row["run"]: row for row in rows if row.get("run") in CANONICAL_RUNS}
    if set(by_run) != set(CANONICAL_RUNS):
        missing = sorted(set(CANONICAL_RUNS) - set(by_run))
        raise ValueError(f"canonical A runs are incomplete: missing={missing}")
    if len(by_run) != len(CANONICAL_RUNS):
        raise ValueError("canonical A run labels are duplicated")
    result: list[dict[str, Any]] = []
    for run_label in CANONICAL_RUNS:
        row = by_run[run_label]
        artifact_dir = Path(row["artifact_dir"])
        result.append(
            {
                "run": run_label,
                "seed": int(row["seed"]),
                "run_id": row["run_id"],
                "artifact_dir": artifact_dir,
            }
        )
    return result


def parse_tripinfo(path: Path) -> dict[str, dict[str, float]]:
    fields = (
        "depart",
        "arrival",
        "duration",
        "routeLength",
        "waitingTime",
        "waitingCount",
        "stopTime",
        "timeLoss",
        "rerouteNo",
    )
    result: dict[str, dict[str, float]] = {}
    for _event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "tripinfo":
            continue
        vehicle_id = elem.attrib.get("id")
        if vehicle_id:
            result[vehicle_id] = {field: as_float(elem.attrib.get(field)) for field in fields}
        elem.clear()
    return result


def aggregate_fcd_edges(path: Path, period_sec: float = FCD_PERIOD_SEC) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for _event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "timestep":
            continue
        sim_time = as_float(elem.attrib.get("time"))
        for vehicle in elem.findall("vehicle"):
            lane_id = vehicle.attrib.get("lane", "")
            edge_id = edge_from_lane(lane_id)
            speed = as_float(vehicle.attrib.get("speed"))
            item = stats.setdefault(
                edge_id,
                {
                    "vehicle_ids": set(),
                    "observation_count": 0,
                    "speed_sum": 0.0,
                    "stopped_observation_count": 0,
                    "stopped_vehicle_ids": set(),
                    "first_observed_sec": sim_time,
                    "last_observed_sec": sim_time,
                },
            )
            vehicle_id = vehicle.attrib.get("id", "")
            item["vehicle_ids"].add(vehicle_id)
            item["observation_count"] += 1
            item["speed_sum"] += speed
            item["first_observed_sec"] = min(item["first_observed_sec"], sim_time)
            item["last_observed_sec"] = max(item["last_observed_sec"], sim_time)
            if speed <= STOP_SPEED_MPS:
                item["stopped_observation_count"] += 1
                item["stopped_vehicle_ids"].add(vehicle_id)
        elem.clear()

    rows: list[dict[str, Any]] = []
    for edge_id, item in stats.items():
        observations = int(item["observation_count"])
        stopped_observations = int(item["stopped_observation_count"])
        rows.append(
            {
                "edge_id": edge_id,
                "observed_vehicle_count": len(item["vehicle_ids"]),
                "observation_count": observations,
                "mean_speed_mps": rounded(item["speed_sum"] / observations),
                "stopped_observation_count": stopped_observations,
                "stopped_observed_vehicle_count": len(item["stopped_vehicle_ids"]),
                "stopped_observation_rate": safe_rate(stopped_observations, observations),
                "sampled_vehicle_seconds": rounded(observations * period_sec),
                "sampled_stopped_vehicle_seconds": rounded(stopped_observations * period_sec),
                "first_observed_sec": item["first_observed_sec"],
                "last_observed_sec": item["last_observed_sec"],
                "fcd_period_sec": period_sec,
            }
        )
    return sorted(rows, key=lambda row: str(row["edge_id"]))


def build_vehicle_details(
    vehicle_log: list[dict[str, str]],
    assignments: dict[str, dict[str, str]],
    tripinfo: dict[str, dict[str, float]],
    stagnation: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for log in vehicle_log:
        vehicle_id = log["vehicle_id"]
        assignment = assignments.get(vehicle_id)
        if assignment is None:
            raise ValueError(f"assignment is missing for vehicle: {vehicle_id}")
        trip = tripinfo.get(vehicle_id, {})
        stuck = stagnation.get(vehicle_id, {})
        rows.append(
            {
                "vehicle_id": vehicle_id,
                "vehicle_kind": assignment.get("vehicle_kind", ""),
                "origin_id": assignment.get("origin_id", log.get("origin_id", "")),
                "KEY_CODE": assignment.get("KEY_CODE", log.get("KEY_CODE", "")),
                "shelter_id": assignment.get("shelter_id", ""),
                "shelter_name": assignment.get("shelter_name", ""),
                "from_sumo_edge_id": assignment.get("from_sumo_edge_id", ""),
                "to_sumo_edge_id": assignment.get("to_sumo_edge_id", ""),
                "passenger_equivalent": as_float(assignment.get("passenger_equivalent")),
                "depart_sec": as_float(log.get("depart")),
                "arrival_sec": log.get("arrival", ""),
                "duration_sec": log.get("duration", ""),
                "arrived": read_bool(log.get("arrived")),
                "reroute_failed": read_bool(log.get("reroute_failed")),
                "long_stopped": read_bool(log.get("long_stopped")),
                "max_consecutive_stop_sec": as_float(log.get("max_consecutive_stop_sec")),
                "departure_blocked_by_closure": read_bool(log.get("departure_blocked_by_closure")),
                "departure_blocked_time_sec": log.get("departure_blocked_time_sec", ""),
                "stranded_main": read_bool(log.get("stranded_main")),
                "tripinfo_available": bool(trip),
                "route_length_m": trip.get("routeLength", ""),
                "waiting_time_sec": trip.get("waitingTime", ""),
                "waiting_count": trip.get("waitingCount", ""),
                "stop_time_sec": trip.get("stopTime", ""),
                "time_loss_sec": trip.get("timeLoss", ""),
                "reroute_count": trip.get("rerouteNo", ""),
                "stagnation_layer": stuck.get("layer", ""),
                "final_edge_id": stuck.get("current_edge", ""),
                "final_speed_mps": stuck.get("speed_mps", ""),
                "current_edge_closed": stuck.get("current_edge_closed", ""),
                "has_open_path_to_destination": stuck.get("has_open_path_to_destination", ""),
            }
        )
    if len({row["vehicle_id"] for row in rows}) != len(rows):
        raise ValueError("vehicle detail contains duplicate vehicle ids")
    return rows


def summarize_run(rows: list[dict[str, Any]]) -> dict[str, Any]:
    arrived_rows = [row for row in rows if row["arrived"]]
    durations = [as_float(row["duration_sec"]) for row in arrived_rows]
    return {
        "vehicle_count": len(rows),
        "arrived_count": len(arrived_rows),
        "not_arrived_count": len(rows) - len(arrived_rows),
        "completion_rate": safe_rate(len(arrived_rows), len(rows)),
        "reroute_failed_count": sum(bool(row["reroute_failed"]) for row in rows),
        "long_stopped_count": sum(bool(row["long_stopped"]) for row in rows),
        "departure_blocked_count": sum(bool(row["departure_blocked_by_closure"]) for row in rows),
        "stranded_main_count": sum(bool(row["stranded_main"]) for row in rows),
        "passenger_equivalent_total": rounded(sum(as_float(row["passenger_equivalent"]) for row in rows)),
        "passenger_equivalent_arrived": rounded(sum(as_float(row["passenger_equivalent"]) for row in arrived_rows)),
        "arrival_time_mean_sec": mean([as_float(row["arrival_sec"]) for row in arrived_rows]),
        "arrival_time_median_sec": median([as_float(row["arrival_sec"]) for row in arrived_rows]),
        "duration_mean_sec": mean(durations),
        "duration_median_sec": median(durations),
    }


def summarize_groups(
    rows: list[dict[str, Any]],
    keys: tuple[str, ...],
    population: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(row)
    result: list[dict[str, Any]] = []
    for key_values, group in grouped.items():
        arrived = [row for row in group if row["arrived"]]
        durations = [as_float(row["duration_sec"]) for row in arrived]
        out: dict[str, Any] = dict(zip(keys, key_values))
        out.update(
            {
                "vehicle_count": len(group),
                "arrived_count": len(arrived),
                "not_arrived_count": len(group) - len(arrived),
                "completion_rate": safe_rate(len(arrived), len(group)),
                "passenger_equivalent_total": rounded(sum(as_float(row["passenger_equivalent"]) for row in group)),
                "passenger_equivalent_arrived": rounded(sum(as_float(row["passenger_equivalent"]) for row in arrived)),
                "duration_mean_sec": mean(durations),
                "duration_median_sec": median(durations),
                "distinct_destination_count": len({row["shelter_id"] for row in group if row["shelter_id"]}),
            }
        )
        if population is not None and "origin_id" in out:
            agent = population.get(out["origin_id"], {})
            for field in (
                "total_pop",
                "elderly_pop",
                "type1_car_non_elderly_pop",
                "type2_car_elderly_pop",
                "type3_no_car_non_elderly_pop",
                "type4_no_car_elderly_pop",
            ):
                out[field] = agent.get(field, "")
        result.append(out)
    return sorted(result, key=lambda row: tuple(str(row.get(key, "")) for key in keys))


def prefix_run(rows: Iterable[dict[str, Any]], run: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"run": run["run"], "seed": run["seed"], "run_id": run["run_id"], **row}
        for row in rows
    ]


def aggregate_run_metrics(run_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    excluded = {"run", "seed", "run_id", "artifact_dir", "route_sha256"}
    fields = [field for field in run_rows[0] if field not in excluded]
    output: list[dict[str, Any]] = []
    for field in fields:
        values = [float(row[field]) for row in run_rows if isinstance(row.get(field), (int, float))]
        if len(values) != len(run_rows):
            continue
        output.append(
            {
                "metric": field,
                "run_count": len(values),
                "min": rounded(min(values)),
                "median": median(values),
                "max": rounded(max(values)),
            }
        )
    return output


def build_car_only_detail(
    *,
    replicate_metrics: Path = DEFAULT_REPLICATES,
    assignments_path: Path = DEFAULT_ASSIGNMENTS,
    agent_types_path: Path = DEFAULT_AGENT_TYPES,
    net_path: Path = DEFAULT_NET,
    closure_timeline_path: Path = DEFAULT_CLOSURE,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    runs = load_canonical_runs(replicate_metrics)
    assignment_rows = read_csv_rows(assignments_path)
    assignments = {row["vehicle_id"]: row for row in assignment_rows}
    if len(assignments) != len(assignment_rows):
        raise ValueError("assignment vehicle ids are duplicated")
    agent_rows = read_csv_rows(agent_types_path)
    population = {row["origin_id"]: row for row in agent_rows}

    run_output: list[dict[str, Any]] = []
    vehicle_output: list[dict[str, Any]] = []
    origin_output: list[dict[str, Any]] = []
    shelter_output: list[dict[str, Any]] = []
    time_output: list[dict[str, Any]] = []
    closure_output: list[dict[str, Any]] = []
    edge_output: list[dict[str, Any]] = []
    stagnation_output: list[dict[str, Any]] = []
    input_files: dict[str, str] = {
        str(replicate_metrics.resolve()): sha256(replicate_metrics),
        str(assignments_path.resolve()): sha256(assignments_path),
        str(agent_types_path.resolve()): sha256(agent_types_path),
        str(net_path.resolve()): sha256(net_path),
        str(closure_timeline_path.resolve()): sha256(closure_timeline_path),
    }
    route_shas: set[str] = set()
    validation_runs: list[dict[str, Any]] = []

    for run in runs:
        artifact = run["artifact_dir"]
        paths = {
            "vehicle_log": artifact / "scenario_a_vehicle_log.csv",
            "congestion_log": artifact / "scenario_a_congestion_log.csv",
            "closure_log": artifact / "scenario_a_closure_log.csv",
            "summary": artifact / "scenario_a_traci_summary.json",
            "fcd": artifact / "scenario_a_fcd.xml",
            "tripinfo": artifact / "scenario_a_tripinfo.xml",
        }
        missing = [str(path) for path in paths.values() if not path.exists()]
        if missing:
            raise FileNotFoundError(f"canonical run inputs are missing: {missing}")
        for path in paths.values():
            input_files[str(path.resolve())] = sha256(path)

        summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
        manifest = summary.get("run_manifest", {})
        if summary.get("run_id") != run["run_id"]:
            raise ValueError(f"run id mismatch: {run['run']}")
        if int(manifest.get("sumo_seed")) != run["seed"]:
            raise ValueError(f"seed mismatch: {run['run']}")
        if manifest.get("git_dirty_scripts") is not False:
            raise ValueError(f"dirty scripts are not allowed: {run['run']}")
        route_sha = str(manifest.get("route_sha256", ""))
        if not route_sha:
            raise ValueError(f"route sha is missing: {run['run']}")
        route_shas.add(route_sha)

        vehicle_log = read_csv_rows(paths["vehicle_log"])
        if len(vehicle_log) != len(assignment_rows):
            raise ValueError(f"vehicle/accounting row mismatch: {run['run']}")
        tripinfo = parse_tripinfo(paths["tripinfo"])
        decomposition = decompose_stagnation(
            vehicle_log_path=paths["vehicle_log"],
            fcd_path=paths["fcd"],
            net_xml_path=net_path,
            closure_timeline_path=closure_timeline_path,
        )
        stagnation = {row["vehicle_id"]: row for row in decomposition["detail_rows"]}
        details = build_vehicle_details(vehicle_log, assignments, tripinfo, stagnation)
        run_metrics = summarize_run(details)
        if run_metrics["arrived_count"] + run_metrics["not_arrived_count"] != len(assignment_rows):
            raise ValueError(f"arrival accounting mismatch: {run['run']}")
        if int(summary.get("vehicle_count")) != len(assignment_rows):
            raise ValueError(f"summary vehicle count mismatch: {run['run']}")
        if int(summary.get("arrived_count")) != run_metrics["arrived_count"]:
            raise ValueError(f"summary arrival count mismatch: {run['run']}")

        run_row = {
            "run": run["run"],
            "seed": run["seed"],
            "run_id": run["run_id"],
            "artifact_dir": str(artifact.resolve()),
            "route_sha256": route_sha,
            **run_metrics,
        }
        run_output.append(run_row)
        vehicle_output.extend(prefix_run(details, run))
        origin_output.extend(prefix_run(summarize_groups(details, ("origin_id", "KEY_CODE"), population), run))
        shelter_output.extend(prefix_run(summarize_groups(details, ("shelter_id", "shelter_name")), run))
        time_output.extend(prefix_run(read_csv_rows(paths["congestion_log"]), run))
        closure_output.extend(prefix_run(read_csv_rows(paths["closure_log"]), run))
        edge_output.extend(prefix_run(aggregate_fcd_edges(paths["fcd"]), run))

        decomp_summary = decomposition["summary"]
        classified = int(decomp_summary["classified_count"])
        missing_fcd = int(decomp_summary["missing_fcd_count"])
        if classified + missing_fcd != run_metrics["not_arrived_count"]:
            raise ValueError(f"stagnation accounting mismatch: {run['run']}")
        for layer, count in decomp_summary["layer_counts"].items():
            stagnation_output.append(
                {
                    "run": run["run"],
                    "seed": run["seed"],
                    "run_id": run["run_id"],
                    "layer": layer,
                    "vehicle_count": count,
                    "classified_count": classified,
                    "missing_fcd_count": missing_fcd,
                    "not_arrived_count": run_metrics["not_arrived_count"],
                }
            )
        validation_runs.append(
            {
                "run": run["run"],
                "run_id": run["run_id"],
                "seed": run["seed"],
                "vehicle_count": len(details),
                "arrived_count": run_metrics["arrived_count"],
                "not_arrived_count": run_metrics["not_arrived_count"],
                "origin_vehicle_count": sum(row["vehicle_count"] for row in summarize_groups(details, ("origin_id",))),
                "shelter_vehicle_count": sum(row["vehicle_count"] for row in summarize_groups(details, ("shelter_id",))),
                "stagnation_classified_count": classified,
                "stagnation_missing_fcd_count": missing_fcd,
            }
        )

    if len(route_shas) != 1:
        raise ValueError(f"canonical runs use different route SHA values: {sorted(route_shas)}")

    outputs = {
        "run_summary": output_dir / "run_summary.csv",
        "run_aggregate_summary": output_dir / "run_aggregate_summary.csv",
        "vehicle_detail": output_dir / "vehicle_detail.csv",
        "origin_summary": output_dir / "origin_summary.csv",
        "shelter_summary": output_dir / "shelter_summary.csv",
        "time_summary": output_dir / "time_summary.csv",
        "closure_summary": output_dir / "closure_summary.csv",
        "edge_summary": output_dir / "edge_summary.csv",
        "stagnation_summary": output_dir / "stagnation_summary.csv",
    }
    write_csv(outputs["run_summary"], run_output)
    write_csv(outputs["run_aggregate_summary"], aggregate_run_metrics(run_output))
    write_csv(outputs["vehicle_detail"], vehicle_output)
    write_csv(outputs["origin_summary"], origin_output)
    write_csv(outputs["shelter_summary"], shelter_output)
    write_csv(outputs["time_summary"], time_output)
    write_csv(outputs["closure_summary"], closure_output)
    write_csv(outputs["edge_summary"], edge_output)
    write_csv(outputs["stagnation_summary"], stagnation_output)

    manifest = {
        "status": "complete",
        "scope": "canonical_scenario_a_three_run_read_only_reaggregation",
        "new_sumo_run": False,
        "canonical_runs": validation_runs,
        "route_sha256": next(iter(route_shas)),
        "fcd_period_sec": FCD_PERIOD_SEC,
        "stop_speed_mps": STOP_SPEED_MPS,
        "edge_metric_note": "FCD sampled observations; observed_vehicle_count is not measured traffic volume",
        "inputs": input_files,
        "outputs": {
            name: {"path": str(path.resolve()), "sha256": sha256(path), "rows": len(read_csv_rows(path))}
            for name, path in outputs.items()
        },
        "validation": {
            "run_count": len(runs),
            "shared_route_sha": len(route_shas) == 1,
            "all_vehicle_accounting_ok": all(
                row["arrived_count"] + row["not_arrived_count"] == row["vehicle_count"]
                for row in validation_runs
            ),
            "all_origin_accounting_ok": all(
                row["origin_vehicle_count"] == row["vehicle_count"] for row in validation_runs
            ),
            "all_shelter_accounting_ok": all(
                row["shelter_vehicle_count"] == row["vehicle_count"] for row in validation_runs
            ),
            "all_stagnation_accounting_ok": all(
                row["stagnation_classified_count"] + row["stagnation_missing_fcd_count"]
                == row["not_arrived_count"]
                for row in validation_runs
            ),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicate-metrics", type=Path, default=DEFAULT_REPLICATES)
    parser.add_argument("--assignments", type=Path, default=DEFAULT_ASSIGNMENTS)
    parser.add_argument("--agent-types", type=Path, default=DEFAULT_AGENT_TYPES)
    parser.add_argument("--net", type=Path, default=DEFAULT_NET)
    parser.add_argument("--closure-timeline", type=Path, default=DEFAULT_CLOSURE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_car_only_detail(
        replicate_metrics=args.replicate_metrics,
        assignments_path=args.assignments,
        agent_types_path=args.agent_types,
        net_path=args.net,
        closure_timeline_path=args.closure_timeline,
        output_dir=args.output_dir,
    )
    print(json.dumps(result["validation"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
