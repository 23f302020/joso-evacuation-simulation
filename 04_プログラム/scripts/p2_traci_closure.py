"""Phase 2: TraCIによる動的道路閉鎖の小規模実行。"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


if os.environ.get("SUMO_HOME"):
    sys.path.append(str(Path(os.environ["SUMO_HOME"]) / "tools"))

import sumolib  # noqa: E402
import traci  # noqa: E402


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent

SUMO_DIR = PROGRAM_DIR / "output" / "sumo"
SUMO_DERIVED_DIR = SUMO_DIR / "derived"
SUMO_SCENARIOS_DIR = SUMO_DIR / "scenarios"
SUMO_RESULTS_DIR = SUMO_DIR / "results"

ROAD_CLOSURE_TIMELINE_JSON = PROGRAM_DIR / "output" / "closure" / "road_closure_timeline.json"
TIME_MAPPING_CSV = SUMO_DERIVED_DIR / "time_mapping_sumo.csv"
EDGE_ID_MAPPING_CSV = SUMO_DERIVED_DIR / "edge_id_mapping.csv"
CLOSURE_TIMELINE_SUMO_JSON = SUMO_DERIVED_DIR / "closure_timeline_sumo.json"

SCENARIOS = {
    "small": {
        "sumocfg": SUMO_SCENARIOS_DIR / "scenario_a_small.sumocfg",
        "assignments": SUMO_DERIVED_DIR / "scenario_a_small_vehicle_assignments.csv",
        "vehicle_log": SUMO_RESULTS_DIR / "scenario_a_small_vehicle_log.csv",
        "closure_log": SUMO_RESULTS_DIR / "scenario_a_small_closure_log.csv",
        "congestion_log": SUMO_RESULTS_DIR / "scenario_a_small_congestion_log.csv",
        "summary": SUMO_RESULTS_DIR / "scenario_a_small_traci_summary.json",
    },
    "10pct": {
        "sumocfg": SUMO_SCENARIOS_DIR / "scenario_a_10pct.sumocfg",
        "assignments": SUMO_DERIVED_DIR / "scenario_a_10pct_vehicle_assignments.csv",
        "vehicle_log": SUMO_RESULTS_DIR / "scenario_a_10pct_vehicle_log.csv",
        "closure_log": SUMO_RESULTS_DIR / "scenario_a_10pct_closure_log.csv",
        "congestion_log": SUMO_RESULTS_DIR / "scenario_a_10pct_congestion_log.csv",
        "summary": SUMO_RESULTS_DIR / "scenario_a_10pct_traci_summary.json",
    },
    "full": {
        "sumocfg": SUMO_SCENARIOS_DIR / "scenario_a.sumocfg",
        "assignments": SUMO_DERIVED_DIR / "scenario_a_vehicle_assignments.csv",
        "vehicle_log": SUMO_RESULTS_DIR / "scenario_a_vehicle_log.csv",
        "closure_log": SUMO_RESULTS_DIR / "scenario_a_closure_log.csv",
        "congestion_log": SUMO_RESULTS_DIR / "scenario_a_congestion_log.csv",
        "summary": SUMO_RESULTS_DIR / "scenario_a_traci_summary.json",
    },
}

STOP_SPEED_THRESHOLD = 0.1
LONG_STOP_THRESHOLD_SEC = 600
CONGESTION_LOG_INTERVAL_SEC = 60


def ensure_dirs() -> None:
    SUMO_DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    SUMO_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def split_sumo_edge_ids(value: Any) -> list[str]:
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [item for item in text.split(";") if item]


def generate_closure_timeline_sumo() -> None:
    ensure_dirs()
    source_closure = json.loads(ROAD_CLOSURE_TIMELINE_JSON.read_text(encoding="utf-8"))
    time_mapping = pd.read_csv(TIME_MAPPING_CSV)
    edge_mapping = pd.read_csv(EDGE_ID_MAPPING_CSV)
    mapping_by_phase1 = {
        row["phase1_edge_id"]: split_sumo_edge_ids(row["sumo_edge_id"])
        for _, row in edge_mapping.iterrows()
    }

    closures = []
    for _, time_row in time_mapping.iterrows():
        timestamp = time_row["source_timestamp"]
        phase1_ids = source_closure.get(timestamp, [])
        closed_sumo_ids: set[str] = set()
        unmapped: list[str] = []
        for phase1_edge_id in phase1_ids:
            sumo_ids = mapping_by_phase1.get(phase1_edge_id, [])
            if not sumo_ids:
                unmapped.append(phase1_edge_id)
                continue
            closed_sumo_ids.update(sumo_ids)
        closures.append(
            {
                "time_id": time_row["time_id"],
                "source_timestamp": timestamp,
                "sim_time_sec": int(time_row["sim_time_sec"]),
                "phase1_edge_count": len(phase1_ids),
                "closed_sumo_edge_ids": sorted(closed_sumo_ids),
                "closed_sumo_edge_count": len(closed_sumo_ids),
                "unmapped_phase1_edge_ids": sorted(unmapped),
            }
        )

    output = {
        "metadata": {
            "source": str(ROAD_CLOSURE_TIMELINE_JSON),
            "edge_mapping": str(EDGE_ID_MAPPING_CSV),
            "time_mapping": str(TIME_MAPPING_CSV),
            "closure_rule": "A31a waterDepth >= 2",
            "sim_duration_sec": 21600,
        },
        "closures": closures,
    }
    CLOSURE_TIMELINE_SUMO_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] saved: {CLOSURE_TIMELINE_SUMO_JSON} ({len(closures)} time steps)")


def load_closure_timeline() -> list[dict[str, Any]]:
    if not CLOSURE_TIMELINE_SUMO_JSON.exists():
        generate_closure_timeline_sumo()
    data = json.loads(CLOSURE_TIMELINE_SUMO_JSON.read_text(encoding="utf-8"))
    return sorted(data["closures"], key=lambda item: int(item["sim_time_sec"]))


def parse_int(value: Any, default: int = 0) -> int:
    if pd.isna(value):
        return default
    text = str(value).strip()
    if not text:
        return default
    return int(float(text))


def load_planned_vehicles(assignments_path: Path) -> dict[str, dict[str, Any]]:
    if not assignments_path.exists():
        return {}
    assignments = pd.read_csv(assignments_path, dtype=str)
    planned: dict[str, dict[str, Any]] = {}
    for _, row in assignments.iterrows():
        vehicle_id = str(row["vehicle_id"])
        planned[vehicle_id] = {
            "vehicle_id": vehicle_id,
            "origin_id": row.get("origin_id", ""),
            "KEY_CODE": row.get("KEY_CODE", ""),
            "from_sumo_edge_id": row.get("from_sumo_edge_id", ""),
            "to_sumo_edge_id": row.get("to_sumo_edge_id", ""),
            "planned_depart": parse_int(row.get("depart", 0)),
        }
    return planned


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def close_edges(edge_ids: list[str]) -> int:
    closed = 0
    for edge_id in edge_ids:
        try:
            traci.edge.setDisallowed(edge_id, ["passenger"])
            closed += 1
        except traci.TraCIException:
            continue
    return closed


def reroute_active_vehicles() -> tuple[int, int, list[str]]:
    success = 0
    failed = 0
    failed_ids: list[str] = []
    for vehicle_id in traci.vehicle.getIDList():
        try:
            traci.vehicle.rerouteTraveltime(vehicle_id)
            success += 1
        except traci.TraCIException:
            failed += 1
            failed_ids.append(vehicle_id)
    return success, failed, failed_ids


def run_traci_scenario(scenario_name: str = "small") -> None:
    ensure_dirs()
    scenario = SCENARIOS[scenario_name]
    closures = load_closure_timeline()
    planned_vehicles = load_planned_vehicles(scenario["assignments"])
    planned_by_source_edge: dict[str, list[str]] = defaultdict(list)
    for vehicle_id, planned in planned_vehicles.items():
        planned_by_source_edge[str(planned["from_sumo_edge_id"])].append(vehicle_id)
    if any(item["unmapped_phase1_edge_ids"] for item in closures):
        raise ValueError("closure_timeline_sumo.json contains unmapped phase1 edges")

    sumo_binary = sumolib.checkBinary("sumo")
    command = [
        sumo_binary,
        "-c",
        str(scenario["sumocfg"]),
        "--no-step-log",
        "true",
        "--duration-log.disable",
        "true",
        "--ignore-route-errors",
        "true",
    ]
    traci.start(command)

    closure_index = 0
    applied_edges: set[str] = set()
    closure_logs: list[dict[str, Any]] = []
    congestion_logs: list[dict[str, Any]] = []
    vehicle_state: dict[str, dict[str, Any]] = {}
    reroute_failed_vehicle_ids: set[str] = set()
    departed_vehicle_ids: set[str] = set()
    blocked_before_depart: dict[str, int] = {}

    try:
        while traci.simulation.getTime() <= 21600 and (
            traci.simulation.getMinExpectedNumber() > 0 or closure_index < len(closures)
        ):
            traci.simulationStep()
            sim_time = int(traci.simulation.getTime())

            for vehicle_id in traci.simulation.getDepartedIDList():
                departed_vehicle_ids.add(vehicle_id)
                vehicle_state.setdefault(
                    vehicle_id,
                    {
                        "vehicle_id": vehicle_id,
                        "depart": sim_time,
                        "arrival": "",
                        "duration": "",
                        "arrived": False,
                        "reroute_failed": False,
                        "long_stopped": False,
                        "max_consecutive_stop_sec": 0,
                        "current_stop_sec": 0,
                    },
                )

            while closure_index < len(closures) and sim_time >= int(closures[closure_index]["sim_time_sec"]):
                item = closures[closure_index]
                edge_ids = item["closed_sumo_edge_ids"]
                new_edge_ids = [edge_id for edge_id in edge_ids if edge_id not in applied_edges]
                closed_count = close_edges(new_edge_ids)
                applied_edges.update(new_edge_ids)
                new_blocked_vehicle_ids: list[str] = []
                for edge_id in new_edge_ids:
                    for vehicle_id in planned_by_source_edge.get(edge_id, []):
                        if vehicle_id in departed_vehicle_ids or vehicle_id in blocked_before_depart:
                            continue
                        blocked_before_depart[vehicle_id] = sim_time
                        new_blocked_vehicle_ids.append(vehicle_id)
                reroute_success, reroute_failed, failed_ids = reroute_active_vehicles()
                reroute_failed_vehicle_ids.update(failed_ids)
                closure_logs.append(
                    {
                        "sim_time_sec": sim_time,
                        "time_id": item["time_id"],
                        "source_timestamp": item["source_timestamp"],
                        "phase1_edge_count": item["phase1_edge_count"],
                        "new_sumo_edge_count": len(new_edge_ids),
                        "closed_sumo_edge_count": closed_count,
                        "cumulative_closed_sumo_edge_count": len(applied_edges),
                        "active_vehicle_count": len(traci.vehicle.getIDList()),
                        "reroute_success_count": reroute_success,
                        "reroute_failed_count": reroute_failed,
                        "new_departure_blocked_by_closure_count": len(new_blocked_vehicle_ids),
                        "cumulative_departure_blocked_by_closure_count": len(blocked_before_depart),
                    }
                )
                closure_index += 1

            active_ids = list(traci.vehicle.getIDList())
            stopped_count = 0
            speed_sum = 0.0
            for vehicle_id in active_ids:
                state = vehicle_state.setdefault(
                    vehicle_id,
                    {
                        "vehicle_id": vehicle_id,
                        "depart": "",
                        "arrival": "",
                        "duration": "",
                        "arrived": False,
                        "reroute_failed": False,
                        "long_stopped": False,
                        "max_consecutive_stop_sec": 0,
                        "current_stop_sec": 0,
                    },
                )
                speed = float(traci.vehicle.getSpeed(vehicle_id))
                speed_sum += speed
                if speed <= STOP_SPEED_THRESHOLD:
                    state["current_stop_sec"] += 1
                    stopped_count += 1
                else:
                    state["current_stop_sec"] = 0
                state["max_consecutive_stop_sec"] = max(
                    state["max_consecutive_stop_sec"], state["current_stop_sec"]
                )
                if state["max_consecutive_stop_sec"] >= LONG_STOP_THRESHOLD_SEC:
                    state["long_stopped"] = True
                if vehicle_id in reroute_failed_vehicle_ids:
                    state["reroute_failed"] = True

            for vehicle_id in traci.simulation.getArrivedIDList():
                state = vehicle_state.setdefault(vehicle_id, {"vehicle_id": vehicle_id})
                state["arrival"] = sim_time
                depart = state.get("depart")
                state["duration"] = sim_time - int(depart) if depart != "" else ""
                state["arrived"] = True

            if sim_time % CONGESTION_LOG_INTERVAL_SEC == 0:
                congestion_logs.append(
                    {
                        "sim_time_sec": sim_time,
                        "active_vehicle_count": len(active_ids),
                        "mean_speed_mps": round(speed_sum / len(active_ids), 6) if active_ids else 0,
                        "stopped_vehicle_count": stopped_count,
                    }
                )
    finally:
        traci.close(False)

    vehicle_rows = []
    all_vehicle_ids = sorted(set(planned_vehicles) | set(vehicle_state))
    for vehicle_id in all_vehicle_ids:
        state = vehicle_state.get(vehicle_id, {"vehicle_id": vehicle_id})
        planned = planned_vehicles.get(vehicle_id, {})
        arrived = bool(state.get("arrived", False))
        reroute_failed = bool(state.get("reroute_failed", False))
        long_stopped = bool(state.get("long_stopped", False))
        departed = vehicle_id in departed_vehicle_ids or state.get("depart", "") != ""
        departure_blocked = vehicle_id in blocked_before_depart and not departed
        vehicle_rows.append(
            {
                "vehicle_id": vehicle_id,
                "origin_id": planned.get("origin_id", ""),
                "KEY_CODE": planned.get("KEY_CODE", ""),
                "from_sumo_edge_id": planned.get("from_sumo_edge_id", ""),
                "to_sumo_edge_id": planned.get("to_sumo_edge_id", ""),
                "planned_depart": planned.get("planned_depart", ""),
                "departed": departed,
                "depart": state.get("depart", ""),
                "arrival": state.get("arrival", ""),
                "duration": state.get("duration", ""),
                "arrived": arrived,
                "reroute_failed": reroute_failed,
                "long_stopped": long_stopped,
                "max_consecutive_stop_sec": state.get("max_consecutive_stop_sec", 0),
                "departure_blocked_by_closure": departure_blocked,
                "departure_blocked_time": blocked_before_depart.get(vehicle_id, ""),
                "stranded_main": (not arrived) and (reroute_failed or long_stopped or departure_blocked),
            }
        )

    write_csv(
        scenario["closure_log"],
        [
            "sim_time_sec",
            "time_id",
            "source_timestamp",
            "phase1_edge_count",
            "new_sumo_edge_count",
            "closed_sumo_edge_count",
            "cumulative_closed_sumo_edge_count",
            "active_vehicle_count",
            "reroute_success_count",
            "reroute_failed_count",
            "new_departure_blocked_by_closure_count",
            "cumulative_departure_blocked_by_closure_count",
        ],
        closure_logs,
    )
    write_csv(
        scenario["congestion_log"],
        ["sim_time_sec", "active_vehicle_count", "mean_speed_mps", "stopped_vehicle_count"],
        congestion_logs,
    )
    write_csv(
        scenario["vehicle_log"],
        [
            "vehicle_id",
            "origin_id",
            "KEY_CODE",
            "from_sumo_edge_id",
            "to_sumo_edge_id",
            "planned_depart",
            "departed",
            "depart",
            "arrival",
            "duration",
            "arrived",
            "reroute_failed",
            "long_stopped",
            "max_consecutive_stop_sec",
            "departure_blocked_by_closure",
            "departure_blocked_time",
            "stranded_main",
        ],
        vehicle_rows,
    )

    summary = {
        "vehicle_count": len(vehicle_rows),
        "departed_count": sum(1 for row in vehicle_rows if row["departed"]),
        "arrived_count": sum(1 for row in vehicle_rows if row["arrived"]),
        "not_arrived_count": sum(1 for row in vehicle_rows if not row["arrived"]),
        "reroute_failed_count": sum(1 for row in vehicle_rows if row["reroute_failed"]),
        "long_stopped_count": sum(1 for row in vehicle_rows if row["long_stopped"]),
        "departure_blocked_by_closure_count": sum(
            1 for row in vehicle_rows if row["departure_blocked_by_closure"]
        ),
        "stranded_main_count": sum(1 for row in vehicle_rows if row["stranded_main"]),
        "closure_event_count": len(closure_logs),
        "final_cumulative_closed_sumo_edge_count": len(applied_edges),
    }
    scenario["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[INFO] saved: {scenario['vehicle_log']}")
    print(f"[INFO] saved: {scenario['closure_log']}")
    print(f"[INFO] saved: {scenario['congestion_log']}")
    print(f"[INFO] saved: {scenario['summary']}")


def run_traci_small() -> None:
    run_traci_scenario("small")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["closure-json", "run-small", "run-10pct", "run-full", "all"],
        help="実行する処理",
    )
    args = parser.parse_args()

    if args.command == "closure-json":
        generate_closure_timeline_sumo()
    elif args.command == "run-small":
        run_traci_scenario("small")
    elif args.command == "run-10pct":
        run_traci_scenario("10pct")
    elif args.command == "run-full":
        run_traci_scenario("full")
    elif args.command == "all":
        generate_closure_timeline_sumo()
        for scenario_name in SCENARIOS:
            run_traci_scenario(scenario_name)


if __name__ == "__main__":
    main()
