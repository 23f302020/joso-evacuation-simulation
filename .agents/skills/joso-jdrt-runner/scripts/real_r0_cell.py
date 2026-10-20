#!/usr/bin/env python3
"""Run, validate, and record one REAL-R0 no-bus cell through the JDRT skill."""

from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any


PARAMETERS_REL = Path("04_プログラム/config/jdrt_realistic_parameters_v1.json")
RUNS_REL = Path("04_プログラム/output/sumo/regions/08211/experiments/jdrt_realistic/runs")
DRIVER_LOGS_REL = Path("04_プログラム/output/sumo/regions/08211/experiments/jdrt_realistic/driver_logs")
LEDGER_REL = Path("05_タスク管理/jdrt/JDRT-REAL_セル検証台帳.jsonl")
FULL_RECORD_REL = Path("05_タスク管理/jdrt/JDRT-REAL-R0_full実験記録.md")


def find_root(explicit: str | None) -> Path:
    candidates = [Path(explicit).resolve()] if explicit else []
    candidates.extend([Path.cwd(), *Path(__file__).resolve().parents])
    for candidate in candidates:
        if (candidate / PARAMETERS_REL).is_file() and (candidate / "context.md").is_file():
            return candidate
    raise FileNotFoundError("project root was not found")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def manifests(root: Path, parameter_sha: str) -> list[dict[str, Any]]:
    result = []
    runs = root / RUNS_REL
    if not runs.is_dir():
        return result
    for directory in runs.iterdir():
        path = directory / "manifest.json"
        if path.is_file():
            try:
                item = read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if item.get("parameter_sha256") == parameter_sha:
                result.append(item)
    return result


def recorded_ids(root: Path) -> set[str]:
    path = root / LEDGER_REL
    if not path.is_file():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ids.add(str(json.loads(line)["run_id"]))
    return ids


def status(root: Path) -> dict[str, Any]:
    parameter_path = root / PARAMETERS_REL
    parameters = read_json(parameter_path)
    items = manifests(root, sha256(parameter_path))
    completed = {
        int(item["seed"]): item for item in items
        if item.get("status") == "COMPLETED" and item.get("summary", {}).get("valid") is True
    }
    recorded = recorded_ids(root)
    unrecorded = [item["run_id"] for item in completed.values() if item["run_id"] not in recorded]
    running = [item["run_id"] for item in items if item.get("status") == "RUNNING"]
    next_seed = next((seed for seed in parameters["experiment"]["paired_seeds"] if seed not in completed), None)
    return {
        "scenario": "REAL-R0",
        "completed_valid": len(completed),
        "recorded": sum(item["run_id"] in recorded for item in completed.values()),
        "completed_unrecorded": unrecorded,
        "running": running,
        "next_seed": next_seed,
    }


def start_next(root: Path, *, foreground: bool = False) -> dict[str, Any]:
    current = status(root)
    if current["completed_unrecorded"]:
        raise RuntimeError(f"record completed cell first: {current['completed_unrecorded'][0]}")
    if current["running"]:
        raise RuntimeError(f"a REAL-R0 run is already RUNNING: {current['running']}")
    if current["next_seed"] is None:
        raise RuntimeError("all REAL-R0 cells are completed")
    seed = int(current["next_seed"])
    stem = f"real_r0_seed{seed}_{date.today().strftime('%Y%m%d')}_skill"
    counter = 1
    while (root / RUNS_REL / f"{stem}{counter:02d}").exists():
        counter += 1
    run_id = f"{stem}{counter:02d}"
    python = root / "04_プログラム/venv/Scripts/python.exe"
    program = root / "04_プログラム/scripts/jdrt_realistic_r0.py"
    common = [str(python), str(program), "--seed", str(seed)]
    preflight = subprocess.run([*common, "--preflight-only"], cwd=root, text=True, capture_output=True, check=True)
    ready = json.loads(preflight.stdout)
    if ready.get("status") != "READY":
        raise RuntimeError(f"preflight was not READY: {ready}")
    log_dir = root / DRIVER_LOGS_REL
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{run_id}.stdout.log"
    stderr_path = log_dir / f"{run_id}.stderr.log"
    command = [*common, "--run-id", run_id, "--runs-root", str(root / RUNS_REL)]
    kwargs: dict[str, Any] = {"cwd": root, "close_fds": True}
    if os.name == "nt" and not foreground:
        kwargs["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000
    elif os.name != "nt" and not foreground:
        kwargs["start_new_session"] = True
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, **kwargs)
    state = {
        "run_id": run_id,
        "pid": process.pid,
        "scenario": "REAL-R0",
        "seed": seed,
        "started_on": date.today().isoformat(),
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "preflight": ready,
    }
    atomic_write(log_dir / f"{run_id}.state.json", json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    if foreground:
        return_code = process.wait()
        return {"start_status": "FINISHED", "return_code": return_code, **state, **check(root, run_id)}
    return {"start_status": "STARTED", **state}


def check(root: Path, run_id: str) -> dict[str, Any]:
    state_path = root / DRIVER_LOGS_REL / f"{run_id}.state.json"
    state = read_json(state_path) if state_path.is_file() else {"pid": -1}
    manifest_path = root / RUNS_REL / run_id / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    pid = int(state.get("pid", -1))
    return {
        "run_id": run_id,
        "pid": None if pid <= 0 else pid,
        "process_alive": process_alive(pid),
        "manifest_status": manifest.get("status", "MISSING"),
        "ready_to_record": manifest.get("status") == "COMPLETED" and manifest.get("summary", {}).get("valid") is True,
    }


def recover(root: Path, run_id: str) -> dict[str, Any]:
    state = check(root, run_id)
    if state["manifest_status"] != "RUNNING":
        raise RuntimeError("only a RUNNING manifest can be recovered")
    if state["pid"] is None:
        raise RuntimeError("no skill-recorded PID exists")
    if state["process_alive"]:
        raise RuntimeError("recorded process is still alive")
    manifest_path = root / RUNS_REL / run_id / "manifest.json"
    manifest = read_json(manifest_path)
    manifest.update({
        "status": "FAILED",
        "ended_at": date.today().isoformat(),
        "error": "Skill-recorded process ended before manifest finalization; PID confirmed absent.",
    })
    atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {"recovery_status": "FAILED_PRESERVED", "run_id": run_id, "manifest": str(manifest_path)}


def csv_count(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def validate(root: Path, run_id: str) -> dict[str, Any]:
    run_dir = root / RUNS_REL / run_id
    manifest = read_json(run_dir / "manifest.json")
    parameters_path = root / PARAMETERS_REL
    parameters = read_json(parameters_path)
    issues: list[str] = []
    if manifest.get("status") != "COMPLETED":
        issues.append("manifest status is not COMPLETED")
    if manifest.get("parameter_sha256") != sha256(parameters_path):
        issues.append("parameter SHA mismatch")
    for item in parameters["inputs"]:
        path = root / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            issues.append(f"registered input mismatch: {item['path']}")
        if manifest.get("input_sha256", {}).get(item["path"]) != item["sha256"]:
            issues.append(f"manifest input mismatch: {item['path']}")
    for relative, expected in manifest.get("output_sha256", {}).items():
        path = run_dir / relative
        if not path.is_file() or sha256(path) != expected:
            issues.append(f"output SHA mismatch: {relative}")
    summary = manifest.get("summary", {})
    engine_dir = run_dir / "engine" / str(summary.get("engine_run_id", ""))
    accounting_path = engine_dir / "accounting_validation.json"
    engine_manifest_path = engine_dir / "run_manifest.json"
    if not accounting_path.is_file() or not engine_manifest_path.is_file():
        issues.append("engine validation artifacts are missing")
        accounting = {}
        engine_manifest = {}
    else:
        accounting = read_json(accounting_path)
        engine_manifest = read_json(engine_manifest_path)
    if accounting.get("technical_valid") is not True:
        issues.append("engine technical_valid is not true")
    if engine_manifest.get("technical_valid") is not True:
        issues.append("engine manifest technical_valid is not true")
    population = parameters["population"]
    expected_counts = {
        "vehicle_log.csv": population["private_vehicle_count"],
        "person_log.csv": population["walk_people"],
    }
    for name, expected in expected_counts.items():
        path = engine_dir / name
        if not path.is_file() or csv_count(path) != expected:
            issues.append(f"{name} row count is not {expected}")
    edge_path = run_dir / "edge_congestion.csv"
    edge_rows = csv_count(edge_path) if edge_path.is_file() else 0
    if edge_rows <= 0 or edge_rows != int(summary.get("edge_congestion_row_count", -1)):
        issues.append("edge congestion accounting mismatch")
    if int(summary.get("bus_vehicle_count", -1)) != 0 or int(summary.get("rescue_vehicle_count", -1)) != 0:
        issues.append("REAL-R0 contains a bus or rescue vehicle")
    sumo_log = (engine_dir / "sumo.log").read_text(encoding="utf-8", errors="replace") if (engine_dir / "sumo.log").is_file() else ""
    lower = sumo_log.lower()
    for token in ("teleport", "collision"):
        if token in lower:
            issues.append(f"SUMO log contains {token}")
    return {
        "validation": "PASS" if not issues else "FAIL",
        "issues": issues,
        "run_id": run_id,
        "scenario": "REAL-R0",
        "seed": int(manifest.get("seed", -1)),
        "summary": summary,
        "edge_congestion_row_count": edge_rows,
    }


def record(root: Path, run_id: str) -> dict[str, Any]:
    result = validate(root, run_id)
    if result["validation"] != "PASS":
        raise RuntimeError(f"validation failed: {result['issues']}")
    if run_id in recorded_ids(root):
        return {**result, "record_status": "ALREADY_RECORDED"}
    ledger_path = root / LEDGER_REL
    record_path = root / FULL_RECORD_REL
    old_ledger = ledger_path.read_text(encoding="utf-8") if ledger_path.is_file() else ""
    old_record = record_path.read_text(encoding="utf-8")
    entry = {
        "recorded_on": date.today().isoformat(),
        "run_id": run_id,
        "scenario": "REAL-R0",
        "seed": result["seed"],
        "validation": "PASS",
        "edge_congestion_row_count": result["edge_congestion_row_count"],
        "summary": result["summary"],
    }
    new_ledger = old_ledger + json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
    line = (
        f"| {result['seed']} | `{run_id}` | ✅ PASS | "
        f"{result['summary']['engine_summary']['completion_rate']:.6f} | "
        f"{result['edge_congestion_row_count']:,} |\n"
    )
    marker = "<!-- REAL-R0-RUNS -->"
    if marker not in old_record:
        raise ValueError("record insertion marker is missing")
    new_record = old_record.replace(marker, line + marker, 1)
    try:
        atomic_write(record_path, new_record)
        atomic_write(ledger_path, new_ledger)
    except Exception:
        atomic_write(record_path, old_record)
        atomic_write(ledger_path, old_ledger)
        raise
    return {**result, "record_status": "RECORDED", "files": [str(FULL_RECORD_REL), str(LEDGER_REL)]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    start_parser = subparsers.add_parser("start-next")
    start_parser.add_argument("--foreground", action="store_true")
    for name in ("check", "recover", "validate", "record"):
        child = subparsers.add_parser(name)
        child.add_argument("--run-id", required=True)
    args = parser.parse_args()
    root = find_root(args.project_root)
    try:
        if args.command == "status":
            result = status(root)
        elif args.command == "start-next":
            result = start_next(root, foreground=args.foreground)
        elif args.command == "check":
            result = check(root, args.run_id)
        elif args.command == "recover":
            result = recover(root, args.run_id)
        elif args.command == "validate":
            result = validate(root, args.run_id)
        else:
            result = record(root, args.run_id)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    except Exception as exc:
        print(json.dumps({"command": args.command, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
