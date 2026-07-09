"""Shared TraCI helpers for Phase 2/3 vehicle accounting.

Keep this module limited to behavior that must be identical between scenario A
and scenario B: closure application, passenger-car rerouting, departure blocking,
and vehicle log / summary accounting. Bus state-machine logic stays in
``p2_traci_bus.py``.
"""

from __future__ import annotations

import csv
import hashlib
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import traci


VEHICLE_LOG_FIELDS = [
    "vehicle_id",
    "origin_id",
    "KEY_CODE",
    "from_sumo_edge_id",
    "to_sumo_edge_id",
    "depart",
    "arrival",
    "duration",
    "arrived",
    "reroute_failed",
    "long_stopped",
    "max_consecutive_stop_sec",
    "departure_blocked_by_closure",
    "departure_blocked_time_sec",
    "stranded_main",
]


def parse_int(value: Any, default: int = 0) -> int:
    if pd.isna(value):
        return default
    text = str(value).strip()
    if not text:
        return default
    return int(float(text))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state(repo_dir: Path) -> dict[str, Any]:
    def run_git(args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=repo_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""

    commit = run_git(["rev-parse", "HEAD"])
    status = run_git(["status", "--porcelain"])
    return {
        "git_commit": commit,
        "git_dirty": bool(status),
    }


def file_manifest(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for label, path in paths.items():
        if path.exists():
            manifest[label] = {
                "path": str(path),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        else:
            manifest[label] = {
                "path": str(path),
                "sha256": "",
                "size_bytes": "",
                "missing": True,
            }
    return manifest


def count_route_vehicles(route_path: Path) -> dict[str, Any]:
    counts = {"total": 0, "private_car": 0, "rescue_car": 0, "bus": 0, "other": 0}
    for _event, elem in ET.iterparse(route_path, events=("end",)):
        if elem.tag not in {"vehicle", "trip"}:
            elem.clear()
            continue
        vehicle_id = elem.attrib.get("id", "")
        counts["total"] += 1
        if vehicle_id.startswith("private_"):
            counts["private_car"] += 1
        elif vehicle_id.startswith("rescue_"):
            counts["rescue_car"] += 1
        elif vehicle_id.startswith("bus_"):
            counts["bus"] += 1
        else:
            counts["other"] += 1
        elem.clear()
    return counts


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


def group_planned_by_source_edge(
    planned_vehicles: dict[str, dict[str, Any]]
) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for vehicle_id, planned in planned_vehicles.items():
        grouped[str(planned["from_sumo_edge_id"])].append(vehicle_id)
    return grouped


def close_edges(edge_ids: Iterable[str], disallowed_classes: list[str]) -> int:
    closed = 0
    for edge_id in edge_ids:
        try:
            traci.edge.setDisallowed(edge_id, disallowed_classes)
            closed += 1
        except traci.TraCIException:
            continue
    return closed


def reroute_active_vehicles(exclude_prefixes: tuple[str, ...] = ()) -> tuple[int, int, list[str]]:
    success = 0
    failed = 0
    failed_ids: list[str] = []
    for vehicle_id in traci.vehicle.getIDList():
        if exclude_prefixes and vehicle_id.startswith(exclude_prefixes):
            continue
        try:
            traci.vehicle.rerouteTraveltime(vehicle_id)
            success += 1
        except traci.TraCIException:
            failed += 1
            failed_ids.append(vehicle_id)
    return success, failed, failed_ids


def apply_closure_to_simulation(
    item: dict[str, Any],
    new_edges: list[str],
    applied_edges: set[str],
    planned_by_source_edge: dict[str, list[str]],
    departed_vehicle_ids: set[str],
    blocked_before_depart: dict[str, int],
    sim_time: int,
    disallowed_classes: list[str],
    reroute_exclude_prefixes: tuple[str, ...] = (),
) -> tuple[dict[str, Any], list[str]]:
    closed_count = close_edges(new_edges, disallowed_classes)
    applied_edges.update(new_edges)
    departure_blocked_count = 0
    for edge_id in new_edges:
        for vehicle_id in planned_by_source_edge.get(edge_id, []):
            if vehicle_id not in departed_vehicle_ids and vehicle_id not in blocked_before_depart:
                blocked_before_depart[vehicle_id] = sim_time
                departure_blocked_count += 1
                try:
                    traci.vehicle.remove(vehicle_id)
                except traci.TraCIException:
                    pass
    reroute_success, reroute_failed, failed_ids = reroute_active_vehicles(
        exclude_prefixes=reroute_exclude_prefixes
    )
    closure_row = {
        "time_id": item["time_id"],
        "source_timestamp": item["source_timestamp"],
        "sim_time_sec": item["sim_time_sec"],
        "phase1_edge_count": item["phase1_edge_count"],
        "excluded_unmapped_phase1_edge_count": item.get(
            "excluded_unmapped_phase1_edge_count", 0
        ),
        "new_sumo_edge_count": len(new_edges),
        "closed_sumo_edge_count": closed_count,
        "cumulative_closed_sumo_edge_count": len(applied_edges),
        "active_vehicle_count": len(traci.vehicle.getIDList()),
        "reroute_success_count": reroute_success,
        "reroute_failed_count": reroute_failed,
        "departure_blocked_count": departure_blocked_count,
    }
    return closure_row, failed_ids


def record_departed(
    sim_time: int,
    departed_vehicle_ids: set[str],
    vehicle_state: dict[str, dict[str, Any]],
) -> None:
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


def record_arrived(sim_time: int, vehicle_state: dict[str, dict[str, Any]]) -> None:
    for vehicle_id in traci.simulation.getArrivedIDList():
        state = vehicle_state.setdefault(vehicle_id, {"vehicle_id": vehicle_id})
        state["arrival"] = sim_time
        state["arrived"] = True
        depart = parse_int(state.get("depart", 0))
        state["duration"] = sim_time - depart


def update_stop_states(
    sim_time: int,
    vehicle_state: dict[str, dict[str, Any]],
    stop_speed_threshold: float,
    long_stop_threshold_sec: int,
    exclude_prefixes: tuple[str, ...] = (),
) -> None:
    for vehicle_id in traci.vehicle.getIDList():
        if exclude_prefixes and vehicle_id.startswith(exclude_prefixes):
            continue
        state = vehicle_state.setdefault(
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
        speed = traci.vehicle.getSpeed(vehicle_id)
        if speed <= stop_speed_threshold:
            state["current_stop_sec"] = int(state.get("current_stop_sec", 0)) + 1
        else:
            state["current_stop_sec"] = 0
        state["max_consecutive_stop_sec"] = max(
            int(state.get("max_consecutive_stop_sec", 0)),
            int(state.get("current_stop_sec", 0)),
        )
        state["long_stopped"] = state["max_consecutive_stop_sec"] >= long_stop_threshold_sec


def build_vehicle_log_rows(
    planned_vehicles: dict[str, dict[str, Any]],
    vehicle_state: dict[str, dict[str, Any]],
    reroute_failed_vehicle_ids: set[str],
    blocked_before_depart: dict[str, int],
) -> list[dict[str, Any]]:
    for vehicle_id in reroute_failed_vehicle_ids:
        vehicle_state.setdefault(vehicle_id, {"vehicle_id": vehicle_id})["reroute_failed"] = True

    rows: list[dict[str, Any]] = []
    for vehicle_id, planned in planned_vehicles.items():
        state = vehicle_state.get(vehicle_id, {})
        blocked_time = blocked_before_depart.get(vehicle_id, "")
        arrived = bool(state.get("arrived", False))
        long_stopped = bool(state.get("long_stopped", False))
        reroute_failed = bool(state.get("reroute_failed", False))
        departure_blocked = blocked_time != ""
        stranded_main = (not arrived) and (reroute_failed or long_stopped or departure_blocked)
        rows.append(
            {
                "vehicle_id": vehicle_id,
                "origin_id": planned.get("origin_id", ""),
                "KEY_CODE": planned.get("KEY_CODE", ""),
                "from_sumo_edge_id": planned.get("from_sumo_edge_id", ""),
                "to_sumo_edge_id": planned.get("to_sumo_edge_id", ""),
                "depart": state.get("depart", planned.get("planned_depart", "")),
                "arrival": state.get("arrival", ""),
                "duration": state.get("duration", ""),
                "arrived": arrived,
                "reroute_failed": reroute_failed,
                "long_stopped": long_stopped,
                "max_consecutive_stop_sec": state.get("max_consecutive_stop_sec", 0),
                "departure_blocked_by_closure": departure_blocked,
                "departure_blocked_time_sec": blocked_time,
                "stranded_main": stranded_main,
            }
        )
    return rows


def write_vehicle_log(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=VEHICLE_LOG_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_traci_summary(
    *,
    city_code: str,
    city_name: str,
    scenario: str,
    rows: list[dict[str, Any]],
    closure_logs: list[dict[str, Any]],
    applied_edges: set[str],
    vehicle_log_rel: str,
    closure_log_rel: str,
    congestion_log_rel: str,
    summary_rel: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    arrived_count = sum(1 for row in rows if bool(row["arrived"]))
    stranded_count = sum(1 for row in rows if bool(row["stranded_main"]))
    summary = {
        "city_code": city_code,
        "city_name": city_name,
        "scenario": scenario,
        "vehicle_count": len(rows),
        "arrived_count": arrived_count,
        "not_arrived_count": len(rows) - arrived_count,
        "reroute_failed_count": sum(1 for row in rows if bool(row["reroute_failed"])),
        "long_stopped_count": sum(1 for row in rows if bool(row["long_stopped"])),
        "departure_blocked_count": sum(
            1 for row in rows if bool(row["departure_blocked_by_closure"])
        ),
        "stranded_main_count": stranded_count,
        "closure_event_count": len(closure_logs),
        "final_closed_sumo_edge_count": len(applied_edges),
        "vehicle_log": vehicle_log_rel,
        "closure_log": closure_log_rel,
        "congestion_log": congestion_log_rel,
        "summary": summary_rel,
    }
    if extra:
        summary.update(extra)
    return summary
