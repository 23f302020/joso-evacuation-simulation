"""Phase 3 rerun preparation guards.

This script performs the non-destructive file moves required before rerunning
R4'/B runs:

- archive surviving old R4 summary/log files,
- move retracted B artifacts out of active output directories,
- verify current scenario_a.rou.xml vehicle ids match archived old R4 vehicle_log.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
REGION_ROOT = PROGRAM_DIR / "output" / "sumo" / "regions" / "08211"
RESULTS_DIR = REGION_ROOT / "results"
SCENARIOS_DIR = REGION_ROOT / "scenarios"
DERIVED_DIR = REGION_ROOT / "derived"
EVALUATION_DIR = REGION_ROOT / "evaluation"
R4_ARCHIVE_DIR = RESULTS_DIR / "archive_R4_20260705"
RETRACTED_DIR = REGION_ROOT / "_retracted_20260709"


R4_FILES = [
    RESULTS_DIR / "scenario_a_traci_summary.json",
    RESULTS_DIR / "scenario_a_vehicle_log.csv",
    RESULTS_DIR / "scenario_a_closure_log.csv",
    RESULTS_DIR / "scenario_a_congestion_log.csv",
]

RETRACTED_FILES = [
    RESULTS_DIR / "scenario_b_bus_log.csv",
    RESULTS_DIR / "scenario_b_passenger_log.csv",
    RESULTS_DIR / "scenario_b_bus_summary.json",
    RESULTS_DIR / "scenario_b_fcd.xml",
    RESULTS_DIR / "scenario_b_tripinfo.xml",
    EVALUATION_DIR / "phase3_ab_comparison.csv",
    SCENARIOS_DIR / "scenario_b.rou.xml",
    SCENARIOS_DIR / "scenario_b.sumocfg",
    DERIVED_DIR / "scenario_b_vehicle_assignments.csv",
    RESULTS_DIR / "scenario_a_fcd.partial_20260709_teleport_minus1.xml",
    RESULTS_DIR / "scenario_a_tripinfo.partial_20260709_teleport_minus1.xml",
]


def move_preserving_relative(path: Path, root: Path, destination_root: Path) -> Path | None:
    if not path.exists():
        return None
    rel = path.relative_to(root)
    destination = destination_root / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    shutil.move(str(path), str(destination))
    return destination


def archive_r4() -> list[Path]:
    moved: list[Path] = []
    R4_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for path in R4_FILES:
        if not path.exists():
            continue
        destination = R4_ARCHIVE_DIR / path.name
        if destination.exists():
            continue
        shutil.move(str(path), str(destination))
        moved.append(destination)
    return moved


def retract_outputs() -> list[Path]:
    moved: list[Path] = []
    for path in RETRACTED_FILES:
        destination = move_preserving_relative(path, REGION_ROOT, RETRACTED_DIR)
        if destination is not None:
            moved.append(destination)
    return moved


def route_vehicle_ids(route_path: Path) -> set[str]:
    ids: set[str] = set()
    for _event, elem in ET.iterparse(route_path, events=("end",)):
        if elem.tag in {"vehicle", "trip"}:
            vehicle_id = elem.attrib.get("id", "")
            if vehicle_id:
                ids.add(vehicle_id)
        elem.clear()
    return ids


def vehicle_log_ids(vehicle_log_path: Path) -> set[str]:
    with vehicle_log_path.open(newline="", encoding="utf-8") as f:
        return {row["vehicle_id"] for row in csv.DictReader(f)}


def verify_scenario_a_ids() -> None:
    route_path = SCENARIOS_DIR / "scenario_a.rou.xml"
    old_log = R4_ARCHIVE_DIR / "scenario_a_vehicle_log.csv"
    if not route_path.exists():
        raise FileNotFoundError(route_path)
    if not old_log.exists():
        raise FileNotFoundError(old_log)
    route_ids = route_vehicle_ids(route_path)
    log_ids = vehicle_log_ids(old_log)
    if route_ids != log_ids:
        missing_in_route = sorted(log_ids - route_ids)[:20]
        missing_in_log = sorted(route_ids - log_ids)[:20]
        raise ValueError(
            "scenario_a vehicle id set mismatch: "
            f"route={len(route_ids)} old_log={len(log_ids)} "
            f"missing_in_route={missing_in_route} missing_in_log={missing_in_log}"
        )
    if len(route_ids) != 9569:
        raise ValueError(f"unexpected scenario_a vehicle id count: {len(route_ids)}")


def print_moved(label: str, paths: Iterable[Path]) -> None:
    paths = list(paths)
    print(f"{label}: {len(paths)}")
    for path in paths:
        print(f"  {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-r4", action="store_true")
    parser.add_argument("--retract", action="store_true")
    parser.add_argument("--verify-a-ids", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all or args.archive_r4:
        print_moved("archived_r4", archive_r4())
    if args.all or args.retract:
        print_moved("retracted", retract_outputs())
    if args.all or args.verify_a_ids:
        verify_scenario_a_ids()
        print("scenario_a_id_check: ok")


if __name__ == "__main__":
    main()
