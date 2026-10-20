"""Run one immutable REAL-R0 (no-bus) Joso simulation cell."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import traceback
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROGRAM_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PROGRAM_DIR.parent
PARAMETERS = PROJECT_ROOT / "04_プログラム/config/jdrt_realistic_parameters_v1.json"
DEFAULT_RUNS = PROJECT_ROOT / "04_プログラム/output/sumo/regions/08211/experiments/jdrt_realistic/runs"
VEHICLE_CLOSURES = PROJECT_ROOT / "04_プログラム/output/sumo/regions/08211/derived/closure_timeline_sumo.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_parameters() -> dict[str, Any]:
    return json.loads(PARAMETERS.read_text(encoding="utf-8"))


def read_csv_count(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def preflight(seed: int) -> dict[str, Any]:
    parameters = load_parameters()
    if seed not in parameters["experiment"]["paired_seeds"]:
        raise ValueError(f"seed {seed} is not registered")
    checked = {}
    for item in parameters["inputs"]:
        path = PROJECT_ROOT / item["path"]
        actual = sha256(path)
        if actual != item["sha256"]:
            raise ValueError(f"input SHA mismatch: {item['path']}")
        checked[item["path"]] = actual
    population = parameters["population"]
    base = PROJECT_ROOT / "04_プログラム/output/sumo/regions/08211/experiments/scenario_c"
    counts = {
        "mode_ledger": read_csv_count(base / "inputs/ownership_sensitivity_20260826/non_car_15pct/scenario_c_mode_ledger.csv"),
        "walk_ledger": read_csv_count(base / "inputs/routes_20260826/non_car_15pct/walk_person_ledger.csv"),
        "car_assignment": read_csv_count(base / "preflight_20260810/non_car_15pct/car_assignment.csv"),
        "car_occupancy": read_csv_count(base / "preflight_20260810/non_car_15pct/car_occupancy_ledger.csv"),
    }
    expected = {
        "mode_ledger": population["total_people"],
        "walk_ledger": population["walk_people"],
        "car_assignment": population["private_vehicle_count"],
        "car_occupancy": population["car_people"],
    }
    if counts != expected:
        raise ValueError(f"population input counts differ: actual={counts}, expected={expected}")
    return {
        "status": "READY",
        "scenario": parameters["scenario"]["id"],
        "seed": seed,
        "parameter_sha256": sha256(PARAMETERS),
        "input_count": len(checked),
        "population_counts": counts,
    }


def edge_from_lane(lane_id: str) -> str:
    return lane_id.rsplit("_", 1)[0]


def write_edge_congestion(fcd_path: Path, output_path: Path) -> int:
    closure_data = json.loads(VEHICLE_CLOSURES.read_text(encoding="utf-8"))
    events = sorted(
        (int(item["sim_time_sec"]), set(item["closed_sumo_edge_ids"]))
        for item in closure_data["closures"]
    )
    closed: set[str] = set()
    event_index = 0
    row_count = 0
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "sim_time_sec", "edge_id", "vehicle_count", "mean_speed_mps",
            "halting_vehicle_count", "closed",
        ])
        writer.writeheader()
        for _, element in ET.iterparse(fcd_path, events=("end",)):
            if element.tag != "timestep":
                continue
            sim_time = int(float(element.attrib["time"]))
            while event_index < len(events) and events[event_index][0] <= sim_time:
                closed.update(events[event_index][1])
                event_index += 1
            by_edge: dict[str, list[float]] = defaultdict(list)
            for vehicle in element.findall("vehicle"):
                lane = vehicle.attrib.get("lane", "")
                if not lane or lane.startswith(":"):
                    continue
                by_edge[edge_from_lane(lane)].append(float(vehicle.attrib["speed"]))
            for edge_id in sorted(by_edge):
                speeds = by_edge[edge_id]
                writer.writerow({
                    "sim_time_sec": sim_time,
                    "edge_id": edge_id,
                    "vehicle_count": len(speeds),
                    "mean_speed_mps": f"{sum(speeds) / len(speeds):.6f}",
                    "halting_vehicle_count": sum(speed <= 0.1 for speed in speeds),
                    "closed": str(edge_id in closed).lower(),
                })
                row_count += 1
            element.clear()
    return row_count


def output_hashes(run_dir: Path) -> dict[str, str]:
    return {
        path.relative_to(run_dir).as_posix(): sha256(path)
        for path in sorted(run_dir.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }


def write_manifest(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(seed: int, run_id: str, runs_root: Path) -> dict[str, Any]:
    ready = preflight(seed)
    parameters = load_parameters()
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = run_dir / "manifest.json"
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "status": "RUNNING",
        "scenario_id": "REAL-R0",
        "protocol_version": "realistic_v1",
        "purpose": "realistic_core_baseline",
        "seed": seed,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "parameter_sha256": ready["parameter_sha256"],
        "input_sha256": {item["path"]: item["sha256"] for item in parameters["inputs"]},
    }
    write_manifest(manifest_path, manifest)
    try:
        sys.path.insert(0, str(PROGRAM_DIR))
        from scripts import scenario_c_integrated as engine

        condition = parameters["scenario"]["scenario_c_condition"]
        engine.CONDITIONS["real_r0"] = {
            "cohort": condition["cohort"],
            "scenario_id": condition["scenario_id"],
            "policy": condition["policy"],
            "elderly_speed": condition["elderly_speed_mps"],
        }
        result = engine.run_integrated(
            "real_r0",
            seed,
            end_sec=int(parameters["experiment"]["end_sec"]),
            runs_root=run_dir / "engine",
        )
        engine_dir = run_dir / "engine" / result["manifest"]["run_id"]
        edge_rows = write_edge_congestion(engine_dir / "fcd.xml", run_dir / "edge_congestion.csv")
        summary = {
            "valid": bool(result["manifest"]["technical_valid"]),
            "scenario_id": "REAL-R0",
            "protocol_version": "realistic_v1",
            "purpose": "realistic_core_baseline",
            "seed": seed,
            "bus_vehicle_count": 0,
            "rescue_vehicle_count": 0,
            "population": parameters["population"],
            "engine_run_id": result["manifest"]["run_id"],
            "engine_summary": result["summary"],
            "engine_accounting": result["accounting"],
            "edge_congestion_row_count": edge_rows,
        }
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        manifest.update({
            "status": "COMPLETED",
            "ended_at": datetime.now().isoformat(timespec="seconds"),
            "summary": summary,
            "output_sha256": output_hashes(run_dir),
        })
        write_manifest(manifest_path, manifest)
        return manifest
    except BaseException as exc:
        manifest.update({
            "status": "FAILED",
            "ended_at": datetime.now().isoformat(timespec="seconds"),
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "output_sha256": output_hashes(run_dir),
        })
        write_manifest(manifest_path, manifest)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.preflight_only:
        result = preflight(args.seed)
    else:
        if not args.run_id:
            raise ValueError("--run-id is required for an execution")
        result = run(args.seed, args.run_id, args.runs_root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
