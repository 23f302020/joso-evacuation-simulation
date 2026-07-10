"""Correct bus passenger accounting for terminated trips.

This is an offline reducer for existing B measurement logs.  It does not
overwrite the original run summary; it records a corrected derivative artifact
with source log hashes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROGRAM_DIR / "output"


def read_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def corrected_bus_accounting(
    *,
    passenger_log_path: Path,
    bus_log_path: Path,
    summary_path: Path | None = None,
    sim_end_sec: int = 21600,
) -> dict[str, Any]:
    passengers = read_csv_rows(passenger_log_path)
    bus_rows = read_csv_rows(bus_log_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path else {}
    if summary:
        sim_end_sec = int(float(summary.get("run_manifest", {}).get("sim_end_sec", sim_end_sec)))

    terminated_keys = {
        (row.get("bus_id", ""), row.get("trip_seq", ""))
        for row in bus_rows
        if read_bool(row.get("terminated")) and int(float(row.get("boarded_count") or 0)) > 0
    }
    corrected_rows: list[dict[str, Any]] = []
    for row in passengers:
        corrected = dict(row)
        key = (row.get("bus_id", ""), row.get("trip_seq", ""))
        terminal_arrival = str(row.get("arrival_time_s", "")).split(".")[0] == str(sim_end_sec)
        if key in terminated_keys or (read_bool(row.get("arrived")) and terminal_arrival):
            corrected["arrived"] = False
            corrected["arrival_time_s"] = ""
            corrected["accounting_correction_reason"] = "terminated_trip"
        else:
            corrected["arrived"] = read_bool(row.get("arrived"))
            corrected["accounting_correction_reason"] = ""
        corrected_rows.append(corrected)

    arrived = sum(1 for row in corrected_rows if row["arrived"])
    not_arrived = sum(1 for row in corrected_rows if not row["arrived"])
    residual = int(summary.get("two_layer_report", {}).get("residual_queue_total", 0)) if summary else 0
    candidates = int(summary.get("initial_bus_candidate_total", len(passengers) + residual)) if summary else len(passengers)
    return {
        "passenger_log": str(passenger_log_path),
        "passenger_log_sha256": sha256_file(passenger_log_path),
        "bus_log": str(bus_log_path),
        "bus_log_sha256": sha256_file(bus_log_path),
        "source_summary": str(summary_path) if summary_path else "",
        "source_summary_sha256": sha256_file(summary_path) if summary_path else "",
        "source_run_id": summary.get("run_manifest", {}).get("run_id", ""),
        "sim_end_sec": sim_end_sec,
        "terminated_trip_keys": [list(key) for key in sorted(terminated_keys)],
        "source_boarded_passengers": len(passengers),
        "corrected_bus_arrived_passengers": arrived,
        "corrected_bus_not_arrived_passengers": not_arrived,
        "residual_queue_total": residual,
        "initial_bus_candidate_total": candidates,
        "conservation_ok": candidates == arrived + not_arrived + residual,
        "corrected_rows": corrected_rows,
    }


def write_corrected_outputs(result: dict[str, Any], output_json: Path) -> None:
    output = {key: value for key, value in result.items() if key != "corrected_rows"}
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


def default_paths(city_code: str) -> dict[str, Path]:
    base = OUTPUT_DIR / "sumo" / "regions" / city_code / "results"
    return {
        "passenger_log": base / "scenario_b_passenger_log.csv",
        "bus_log": base / "scenario_b_bus_log.csv",
        "summary": base / "scenario_b_bus_summary.json",
        "output_json": base / "scenario_b_bus_corrected_accounting.json",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-code", default="08211")
    parser.add_argument("--passenger-log", type=Path)
    parser.add_argument("--bus-log", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = default_paths(args.city_code)
    result = corrected_bus_accounting(
        passenger_log_path=args.passenger_log or paths["passenger_log"],
        bus_log_path=args.bus_log or paths["bus_log"],
        summary_path=args.summary or paths["summary"],
    )
    write_corrected_outputs(result, args.output_json or paths["output_json"])
    print(json.dumps({key: value for key, value in result.items() if key != "corrected_rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
