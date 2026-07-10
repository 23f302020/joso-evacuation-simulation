"""Validate Phase 3 B measurement run gates before proceeding.

Checks implemented here:

- AC2: vehicle accounting for the B measurement route.
- AC5: manifest provenance, sha256 consistency, FCD/tripinfo XML completeness,
  and passenger/bus log times not exceeding the FCD final timestep.
- AC6: bus passenger conservation.
- New precondition: if B-side not_arrived differs from A' 479 by more than 2x
  or less than half, generate/compare A/B stagnation decompositions and stop.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

from p3_stagnation_decomposition import (
    decompose_stagnation,
    scenario_paths,
    write_decomposition_outputs,
)


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROGRAM_DIR / "output"

DEFAULT_A_NOT_ARRIVED = 479
DEFAULT_A_LAYER1 = 68
DEFAULT_EXPECTED_VEHICLES = 9569


def read_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def latest_fcd_timestep(path: Path) -> float:
    latest = -1.0
    for _event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag == "timestep":
            latest = max(latest, float(elem.attrib["time"]))
            elem.clear()
    if latest < 0:
        raise ValueError(f"no timestep found in fcd: {path}")
    return latest


def max_log_time(path: Path, fields: tuple[str, ...]) -> float:
    latest = 0.0
    for row in load_csv_rows(path):
        for field in fields:
            value = row.get(field, "")
            if value != "":
                latest = max(latest, float(value))
    return latest


def validate_ac2(vehicle_log_path: Path, expected_vehicles: int) -> dict[str, Any]:
    rows = load_csv_rows(vehicle_log_path)
    arrived = sum(1 for row in rows if read_bool(row.get("arrived")))
    blocked = sum(1 for row in rows if read_bool(row.get("departure_blocked_by_closure")))
    not_arrived_unblocked = sum(
        1
        for row in rows
        if not read_bool(row.get("arrived")) and not read_bool(row.get("departure_blocked_by_closure"))
    )
    return {
        "name": "AC2",
        "ok": len(rows) == expected_vehicles
        and arrived + not_arrived_unblocked + blocked == expected_vehicles,
        "vehicle_log_rows": len(rows),
        "expected_vehicles": expected_vehicles,
        "arrived": arrived,
        "not_arrived_unblocked": not_arrived_unblocked,
        "departure_blocked": blocked,
        "accounting_total": arrived + not_arrived_unblocked + blocked,
        "not_arrived_total": len(rows) - arrived,
    }


def validate_ac5(
    summary: dict[str, Any],
    expected_scope_path: Path,
) -> dict[str, Any]:
    manifest = summary.get("run_manifest", {})
    outputs = manifest.get("outputs", {})
    output_checks: dict[str, dict[str, Any]] = {}
    ok = True

    started_at = manifest.get("started_at", "")
    ended_at = manifest.get("ended_at", "")
    try:
        started_dt = datetime.fromisoformat(started_at)
        ended_dt = datetime.fromisoformat(ended_at)
        time_order_ok = started_dt < ended_dt
    except ValueError:
        time_order_ok = False
    ok = ok and time_order_ok

    commit_ok = bool(re.fullmatch(r"[0-9a-f]{40}", manifest.get("git_commit", "")))
    scripts_ok = manifest.get("git_dirty_scripts") is False
    scope_ok = manifest.get("git_scope_path") == str(expected_scope_path.resolve())
    ok = ok and commit_ok and scripts_ok and scope_ok

    for label, item in outputs.items():
        path = Path(item.get("path", ""))
        missing = bool(item.get("missing")) or not path.exists()
        sha_match = False
        if not missing:
            sha_match = sha256_file(path) == item.get("sha256")
        output_checks[label] = {
            "path": str(path),
            "missing": missing,
            "sha256_match": sha_match,
        }
        ok = ok and (not missing) and sha_match

    xml_checks: dict[str, bool] = {}
    for label in ("fcd", "tripinfo"):
        path = Path(outputs.get(label, {}).get("path", ""))
        try:
            ET.parse(path)
            xml_checks[label] = True
        except (OSError, ET.ParseError):
            xml_checks[label] = False
        ok = ok and xml_checks[label]

    fcd_last = latest_fcd_timestep(Path(outputs["fcd"]["path"])) if outputs.get("fcd") else -1.0
    passenger_latest = (
        max_log_time(Path(outputs["passenger_log"]["path"]), ("board_time_s", "arrival_time_s"))
        if outputs.get("passenger_log")
        else 0.0
    )
    bus_latest = (
        max_log_time(Path(outputs["bus_log"]["path"]), ("board_time_s", "arrive_shelter_time_s"))
        if outputs.get("bus_log")
        else 0.0
    )
    log_time_ok = passenger_latest <= fcd_last and bus_latest <= fcd_last
    ok = ok and log_time_ok

    return {
        "name": "AC5",
        "ok": ok,
        "time_order_ok": time_order_ok,
        "git_commit_40hex": commit_ok,
        "git_dirty_scripts_false": scripts_ok,
        "git_scope_path_match": scope_ok,
        "output_checks": output_checks,
        "xml_checks": xml_checks,
        "fcd_last_timestep": fcd_last,
        "passenger_log_max_time": passenger_latest,
        "bus_log_max_time": bus_latest,
        "log_time_le_fcd": log_time_ok,
    }


def validate_ac6(summary: dict[str, Any]) -> dict[str, Any]:
    boarded = int(summary.get("bus_boarded_passengers", 0))
    arrived = int(summary.get("bus_arrived_passengers", 0))
    not_arrived = int(summary.get("bus_not_arrived_passengers", 0))
    candidates = int(summary.get("initial_bus_candidate_total", 0))
    residual = int(summary.get("two_layer_report", {}).get("residual_queue_total", 0))
    return {
        "name": "AC6",
        "ok": boarded == arrived + not_arrived and candidates == boarded + residual,
        "boarded": boarded,
        "arrived": arrived,
        "not_arrived": not_arrived,
        "candidates": candidates,
        "residual_queue": residual,
    }


def ensure_decomposition(city_code: str, scenario: str) -> dict[str, Any]:
    paths = scenario_paths(city_code, scenario)
    result = decompose_stagnation(
        vehicle_log_path=paths["vehicle_log"],
        fcd_path=paths["fcd"],
        net_xml_path=paths["net"],
        closure_timeline_path=paths["closure"],
    )
    write_decomposition_outputs(result, paths["detail_csv"], paths["summary_json"])
    return result["summary"]


def compare_stagnation_layers(
    city_code: str,
    a_scenario: str,
    b_scenario: str,
) -> dict[str, Any]:
    a_summary = ensure_decomposition(city_code, a_scenario)
    b_summary = ensure_decomposition(city_code, b_scenario)
    return {
        "a_summary": a_summary,
        "b_summary": b_summary,
        "layer_counts_match_exactly": a_summary.get("layer_counts") == b_summary.get("layer_counts"),
    }


def validate_b_measure(
    *,
    city_code: str,
    bus_summary_path: Path,
    expected_vehicles: int = DEFAULT_EXPECTED_VEHICLES,
    a_not_arrived: int = DEFAULT_A_NOT_ARRIVED,
    a_layer1: int = DEFAULT_A_LAYER1,
) -> dict[str, Any]:
    summary = json.loads(bus_summary_path.read_text(encoding="utf-8"))
    manifest = summary["run_manifest"]
    outputs = manifest["outputs"]
    vehicle_log_path = Path(outputs["vehicle_log"]["path"])

    ac2 = validate_ac2(vehicle_log_path, expected_vehicles)
    ac5 = validate_ac5(summary, SCRIPT_DIR)
    ac6 = validate_ac6(summary)
    b_not_arrived = int(ac2["not_arrived_total"])
    total_lower = a_not_arrived / 2
    total_upper = a_not_arrived * 2
    total_divergence = b_not_arrived < total_lower or b_not_arrived > total_upper
    layer_comparison = (
        compare_stagnation_layers(city_code, "scenario_a", "scenario_b")
        if b_not_arrived > 0
        else None
    )
    layer1_lower = a_layer1 / 2
    layer1_upper = a_layer1 * 2
    layer1_divergence = False
    layer2_ge_layer3 = False
    if layer_comparison:
        b_layers = layer_comparison["b_summary"].get("layer_counts", {})
        b_layer1 = int(b_layers.get("physical_isolation", 0))
        b_layer2 = int(b_layers.get("intersection_blockage", 0))
        b_layer3 = int(b_layers.get("queue_behind_blockage", 0))
        layer1_divergence = b_layer1 < layer1_lower or b_layer1 > layer1_upper
        layer2_ge_layer3 = b_layer2 >= b_layer3
    halt_reasons = []
    if total_divergence:
        halt_reasons.append("B not_arrived is outside the accepted half-to-double range of A' baseline")
    if layer1_divergence:
        halt_reasons.append("B physical_isolation layer is outside the accepted half-to-double range of A' layer 1")
    if layer2_ge_layer3:
        halt_reasons.append("B intersection_blockage layer is greater than or equal to queue_behind_blockage layer")
    gates_ok = bool(ac2["ok"] and ac5["ok"] and ac6["ok"])
    return {
        "city_code": city_code,
        "bus_summary": str(bus_summary_path),
        "gates_ok": gates_ok,
        "halt_required": bool(gates_ok and halt_reasons),
        "halt_reason": "; ".join(halt_reasons),
        "halt_reasons": halt_reasons,
        "a_not_arrived_baseline": a_not_arrived,
        "a_layer1_baseline": a_layer1,
        "b_not_arrived": b_not_arrived,
        "accepted_not_arrived_range": {"min_exclusive": total_lower, "max_exclusive": total_upper},
        "accepted_layer1_range": {"min_exclusive": layer1_lower, "max_exclusive": layer1_upper},
        "ac2": ac2,
        "ac5": ac5,
        "ac6": ac6,
        "layer_comparison": layer_comparison,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-code", default="08211")
    parser.add_argument("--bus-summary", type=Path)
    parser.add_argument("--expected-vehicles", type=int, default=DEFAULT_EXPECTED_VEHICLES)
    parser.add_argument("--a-not-arrived", type=int, default=DEFAULT_A_NOT_ARRIVED)
    parser.add_argument("--a-layer1", type=int, default=DEFAULT_A_LAYER1)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bus_summary = args.bus_summary or (
        OUTPUT_DIR / "sumo" / "regions" / args.city_code / "results" / "scenario_b_bus_summary.json"
    )
    result = validate_b_measure(
        city_code=args.city_code,
        bus_summary_path=bus_summary,
        expected_vehicles=args.expected_vehicles,
        a_not_arrived=args.a_not_arrived,
        a_layer1=args.a_layer1,
    )
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["gates_ok"]:
        return 1
    if result["halt_required"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
