#!/usr/bin/env python3
"""Run, validate, and record one Joso City JDRT v2 core cell."""

from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any


PARAMETERS_REL = Path("04_プログラム/config/jdrt_parameters_v2.json")
INPUT_REGISTRY_REL = Path("04_プログラム/config/jdrt_input_sources_v1.json")
RUNS_REL = Path("04_プログラム/output/sumo/regions/08211/experiments/jdrt/runs")
DRIVER_LOGS_REL = Path("04_プログラム/output/sumo/regions/08211/experiments/jdrt/driver_logs")
LEDGER_REL = Path("05_タスク管理/jdrt/JDRT-v2_セル検証台帳.jsonl")
FULL_RECORD_REL = Path("05_タスク管理/jdrt/JDRT-v2_full実験記録.md")
TASKS_REL = Path("05_タスク管理/jdrt/JDRT_実装タスク管理.md")
CONTEXT_REL = Path("context.md")
DECISIONS_REL = Path("00_全体整理/決定ログ.md")
PROGRESS_REL = Path("01_経過報告/経過報告2026年08月/経過報告20260826.md")
HANDLED_ERROR_PREFIX = "Error: Answered with error to command 0xc4: Route replacement failed"


def _find_project_root(explicit: str | None) -> Path:
    candidates = [Path(explicit).resolve()] if explicit else []
    candidates.extend([Path.cwd(), *Path(__file__).resolve().parents])
    for candidate in candidates:
        if (candidate / PARAMETERS_REL).is_file() and (candidate / "context.md").is_file():
            return candidate
    raise FileNotFoundError("project root containing context.md and JDRT v2 parameters was not found")


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cells(parameters: dict[str, Any]) -> list[tuple[str, int]]:
    dispatchers = parameters["dispatchers"]
    scenarios = [
        str(dispatchers["primary_baseline"]),
        *(str(value) for value in dispatchers["supporting"]),
        str(dispatchers["primary_proposal"]),
    ]
    declared = set(str(value) for value in parameters["experiment"]["core_scenarios"])
    if len(scenarios) != len(set(scenarios)) or set(scenarios) != declared:
        raise ValueError("dispatcher roles do not define each core scenario exactly once")
    return [
        (scenario, int(seed))
        for seed in parameters["experiment"]["paired_seeds"]
        for scenario in scenarios
    ]


def _matching_manifests(root: Path, parameter_sha: str) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    runs_dir = root / RUNS_REL
    if not runs_dir.is_dir():
        return manifests
    for run_dir in runs_dir.iterdir():
        path = run_dir / "manifest.json"
        if not path.is_file():
            continue
        try:
            manifest = _json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("parameter_sha256") == parameter_sha:
            manifests.append(manifest)
    return manifests


def _completed_by_cell(
    manifests: list[dict[str, Any]],
) -> dict[tuple[str, int], dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for manifest in manifests:
        summary = manifest.get("summary", {})
        if (
            manifest.get("status") == "COMPLETED"
            and summary.get("valid") is True
            and summary.get("purpose") == "core_experiment"
            and summary.get("protocol_version") == "v2"
        ):
            key = (str(manifest["scenario_id"]), int(manifest["seed"]))
            grouped.setdefault(key, []).append(manifest)
    duplicates = [key for key, values in grouped.items() if len(values) != 1]
    if duplicates:
        raise ValueError(f"multiple valid completed runs exist for cells: {duplicates}")
    return {key: values[0] for key, values in grouped.items()}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=0.0, abs_tol=1e-9)


def validate_run(root: Path, run_id: str) -> dict[str, Any]:
    run_dir = root / RUNS_REL / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = _json(manifest_path)
    parameters_path = root / PARAMETERS_REL
    parameters = _json(parameters_path)
    metrics_path = run_dir / "metrics.json"
    issues: list[str] = []

    if manifest.get("run_id") != run_id:
        issues.append("run_id mismatch")
    if manifest.get("city_code") != "08211":
        issues.append("city_code is not 08211")
    if manifest.get("status") != "COMPLETED":
        issues.append("manifest status is not COMPLETED")
    if manifest.get("summary", {}).get("valid") is not True:
        issues.append("summary.valid is not true")
    if manifest.get("summary", {}).get("protocol_version") != "v2":
        issues.append("protocol is not v2")
    if manifest.get("summary", {}).get("purpose") != "core_experiment":
        issues.append("purpose is not core_experiment")
    if (str(manifest.get("scenario_id")), int(manifest.get("seed", -1))) not in _cells(parameters):
        issues.append("scenario/seed is outside the fixed core cells")

    parameter_sha = _sha256(parameters_path)
    parameter_ok = parameter_sha == manifest.get("parameter_sha256")
    if not parameter_ok:
        issues.append("parameter SHA mismatch")

    registry = _json(root / INPUT_REGISTRY_REL)
    input_ok = 0
    for item in registry["files"]:
        role = str(item["role"])
        actual = _sha256(root / str(item["path"]))
        manifest_value = manifest.get("input_sha256_by_role", {}).get(role)
        if actual == item.get("sha256") == manifest_value:
            input_ok += 1
        else:
            issues.append(f"input SHA mismatch: {role}")

    output_hashes = manifest.get("summary", {}).get("output_sha256_by_file", {})
    output_ok = 0
    for filename, expected in output_hashes.items():
        path = run_dir / filename
        if path.is_file() and _sha256(path) == expected:
            output_ok += 1
        else:
            issues.append(f"output SHA mismatch: {filename}")

    event_path = run_dir / str(manifest.get("event_log", "events.jsonl"))
    event_count = 0
    if event_path.is_file():
        with event_path.open(encoding="utf-8") as handle:
            event_count = sum(1 for line in handle if line.strip())
    event_sha_ok = event_path.is_file() and _sha256(event_path) == manifest.get("event_log_sha256")
    if event_count != int(manifest.get("event_count", -1)):
        issues.append("event count mismatch")
    if not event_sha_ok:
        issues.append("event SHA mismatch")

    if not metrics_path.is_file():
        raise FileNotFoundError(metrics_path)
    metrics = _json(metrics_path)
    people = _read_csv(run_dir / "person_results.csv")
    requests = _read_csv(run_dir / "request_results.csv")
    vehicles = _read_csv(run_dir / "drt_vehicle_metrics.csv")
    evacuated = sum(row["status"] == "EVACUATED" for row in people)
    stranded = sum(row["status"] == "STRANDED" for row in people)
    type3 = sum(row["person_type"] == "3" and row["status"] == "EVACUATED" for row in people)
    type4 = sum(row["person_type"] == "4" and row["status"] == "EVACUATED" for row in people)
    request_completed = sum(row["status"] == "COMPLETED" for row in requests)
    request_stranded = sum(row["status"] == "STRANDED" for row in requests)
    total_vkt = sum(float(row["total_m"]) for row in vehicles) / 1000.0
    empty_vkt = sum(float(row["empty_m"]) for row in vehicles) / 1000.0

    expected_people = int(parameters["population"]["drt_eligible"])
    expected_requests = int(parameters["population"]["request_grouping"]["expected_request_count"])
    expected_vehicles = int(parameters["fleet"]["total"])
    comparisons = [
        (len(people) == expected_people, "person row count mismatch"),
        (evacuated + stranded == expected_people, "person conservation mismatch"),
        (evacuated == metrics.get("all_drt_evacuated"), "evacuated count mismatch"),
        (stranded == metrics.get("conservation", {}).get("stranded"), "stranded count mismatch"),
        (type3 == metrics.get("type3_evacuated"), "Type3 count mismatch"),
        (type4 == metrics.get("type4_evacuated"), "Type4 count mismatch"),
        (len(requests) == expected_requests, "request row count mismatch"),
        (request_completed + request_stranded == expected_requests, "request conservation mismatch"),
        (request_completed == metrics.get("request_status_counts", {}).get("COMPLETED"), "completed request mismatch"),
        (request_stranded == metrics.get("request_status_counts", {}).get("STRANDED"), "stranded request mismatch"),
        (len(vehicles) == expected_vehicles, "DRT vehicle row count mismatch"),
        (_close(total_vkt, float(metrics.get("drt_total_vkt_km", -1))), "total VKT mismatch"),
        (_close(empty_vkt, float(metrics.get("drt_empty_vkt_km", -1))), "empty VKT mismatch"),
    ]
    for passed, message in comparisons:
        if not passed:
            issues.append(message)

    log_lines = (run_dir / "sumo_error.log").read_text(encoding="utf-8", errors="replace").splitlines()
    warning_count = sum(line.startswith("Warning:") for line in log_lines)
    error_count = sum(line.startswith("Error:") for line in log_lines)
    handled_count = sum(line.startswith(HANDLED_ERROR_PREFIX) for line in log_lines)
    log_summary = manifest.get("summary", {}).get("sumo_error_log", {})
    for actual, expected, label in [
        (warning_count, log_summary.get("warning_count"), "warning count"),
        (error_count, log_summary.get("error_count"), "error count"),
        (handled_count, log_summary.get("handled_route_rejection_count"), "handled error count"),
    ]:
        if actual != expected:
            issues.append(f"{label} mismatch")

    simulation = parameters["simulation"]
    expected_controller = int(parameters["simulation_end_sec"] / simulation["controller_step_interval_sec"])
    expected_observations = int(parameters["simulation_end_sec"] / simulation["step_length_sec"])
    summary = manifest.get("summary", {})
    if summary.get("controller_step_count") != expected_controller:
        issues.append("controller step count mismatch")
    if summary.get("technical_observation_count") != expected_observations:
        issues.append("technical observation count mismatch")
    zero_gates = {
        "teleport": metrics.get("teleport_count"),
        "collision": metrics.get("collision_teleport_count"),
        "gridlock": log_summary.get("gridlock_teleport_count"),
        "unhandled_error": log_summary.get("unhandled_error_count"),
    }
    for label, value in zero_gates.items():
        if value != 0:
            issues.append(f"{label} gate is not zero")

    return {
        "validation": "PASS" if not issues else "FAIL",
        "issues": issues,
        "run_id": run_id,
        "scenario": manifest.get("scenario_id"),
        "seed": int(manifest.get("seed")),
        "status": manifest.get("status"),
        "parameter_sha": f"{int(parameter_ok)}/1",
        "input_sha": f"{input_ok}/{len(registry['files'])}",
        "output_sha": f"{output_ok}/{len(output_hashes)}",
        "event_sha": bool(event_sha_ok),
        "event_count": event_count,
        "controller_steps": summary.get("controller_step_count"),
        "observations": summary.get("technical_observation_count"),
        "evacuated": evacuated,
        "stranded": stranded,
        "type4_evacuated": type4,
        "type3_evacuated": type3,
        "request_completed": request_completed,
        "request_stranded": request_stranded,
        "total_vkt_km": total_vkt,
        "empty_vkt_km": empty_vkt,
        "arrival_p95_sec": metrics.get("arrival_time_p95_sec_nearest_rank"),
        "warnings": warning_count,
        "errors": error_count,
        "handled_errors": handled_count,
        "unhandled_errors": log_summary.get("unhandled_error_count"),
        "teleport": metrics.get("teleport_count"),
        "collision": metrics.get("collision_teleport_count"),
        "gridlock": log_summary.get("gridlock_teleport_count"),
    }


def _nl(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _read_preserved(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".jdrt-skill.tmp")
    temporary.write_bytes(text.encode("utf-8"))
    os.replace(temporary, path)


def _recorded_ids(root: Path) -> set[str]:
    path = root / LEDGER_REL
    if not path.is_file():
        return set()
    return {str(json.loads(line)["run_id"]) for line in _read_preserved(path).splitlines() if line.strip()}


def _log_operation(root: Path, command: str, run_id: str | None, started: float, result: dict[str, Any]) -> None:
    path = root / DRIVER_LOGS_REL / "operations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": command,
        "run_id": run_id or result.get("run_id"),
        "elapsed_sec": round(time.monotonic() - started, 3),
        "result": result,
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _seed_status(cells: list[tuple[str, int]], count: int) -> str:
    seeds: list[int] = []
    for _, seed in cells:
        if seed not in seeds:
            seeds.append(seed)
    per_seed = len(cells) // len(seeds)
    full_count, partial = divmod(count, per_seed)
    parts: list[str] = []
    if full_count:
        parts.append("seed " + "・".join(str(seed) for seed in seeds[:full_count]) + "完了")
    if partial:
        parts.append(f"seed {seeds[full_count]}は{partial}/{per_seed}")
    return "、".join(parts) if parts else "未開始"


def _short_scenario(scenario: str) -> str:
    return scenario.removeprefix("JDRT-")


def _next_text(next_cell: tuple[str, int] | None) -> str:
    if next_cell is None:
        return "中核20セルの集計・評価"
    return f"{_short_scenario(next_cell[0])} seed{next_cell[1]}"


def _detail_table(result: dict[str, Any], nl: str) -> str:
    p95 = "NA" if result["arrival_p95_sec"] is None else f"{int(result['arrival_p95_sec']):,} sec"
    rows = [
        ("controller / observation", f"{result['controller_steps']:,} / {result['observations']:,}"),
        ("避難完了 / 立ち往生", f"{result['evacuated']:,} / {result['stranded']:,}"),
        ("Type4 / Type3避難完了", f"{result['type4_evacuated']:,} / {result['type3_evacuated']:,}"),
        ("完了 / 立ち往生request", f"{result['request_completed']:,} / {result['request_stranded']:,}"),
        ("DRT総VKT", f"{result['total_vkt_km']:.6f} km"),
        ("空車VKT", f"{result['empty_vkt_km']:.6f} km"),
        ("到着時刻P95", p95),
        ("event", f"{result['event_count']:,}"),
        ("Warning / Error", f"{result['warnings']:,} / {result['errors']:,}"),
        ("捕捉済み / 未処理Error", f"{result['handled_errors']:,} / {result['unhandled_errors']:,}"),
        ("teleport / collision", f"{result['teleport']:,} / {result['collision']:,}"),
    ]
    lines = ["| 項目 | 実測 |", "|---|---:|", *(f"| {name} | {value} |" for name, value in rows)]
    return nl.join(lines)


def _update_full_record(
    text: str,
    result: dict[str, Any],
    count: int,
    total: int,
    seed_status: str,
    next_cell: tuple[str, int] | None,
) -> str:
    nl = _nl(text)
    text = re.sub(r"^> 状態：.*$", f"> 状態：中核{count}/{total}セル完了（{seed_status}）", text, count=1, flags=re.M)
    if result["run_id"] not in text:
        row = (
            f"| {count} | {result['scenario']} | {result['seed']} | `{result['run_id']}` | "
            "COMPLETED | true | 0 | 0 | 0 | 全会計・SHA PASS |"
        )
        marker = nl + nl + re.search(r"残り\d+セル。", text).group(0)
        text = text.replace(marker, nl + row + marker, 1)
    text = re.sub(r"残り\d+セル。", f"残り{total - count}セル。", text, count=1)
    match = re.search(r"(?ms)^## (\d+)\. 次のセル\r?\n.*\Z", text)
    if not match:
        raise ValueError("full experiment record has no terminal next-cell section")
    section_no = int(match.group(1))
    next_section = (
        f"## {section_no + 1}. 次のセル{nl}{nl}"
        f"`{next_cell[0]}` seed {next_cell[1]}を1セルだけ実行する。完了・検証・記録後にのみ次セルへ進む。"
        if next_cell
        else f"## {section_no + 1}. 中核20セル完了{nl}{nl}全セルの集計・頑健性評価へ進む。"
    )
    detail = (
        f"## {section_no}. {_short_scenario(result['scenario'])} seed {result['seed']}{nl}{nl}"
        f"`{result['scenario']}` seed {result['seed']}を{count}番目のセルとして実行した。"
        f"run IDは`{result['run_id']}`、manifestは`COMPLETED`、`summary.valid=true`だった。{nl}{nl}"
        f"{_detail_table(result, nl)}{nl}{nl}"
        f"Parameter SHA {result['parameter_sha']}、入力SHA {result['input_sha']}、出力SHA {result['output_sha']}、"
        "event行数・SHA、人物・request CSV集計、VKT、Warning/Error実数を独立再計算して全て一致した。"
        + ("全20セル完了前の方向判断は行わない。" if count < total else "これで中核20セルが全て揃った。")
        + f"{nl}{nl}{next_section}{nl}"
    )
    return text[: match.start()] + detail


def _summary_line(result: dict[str, Any], count: int, next_cell: tuple[str, int] | None) -> str:
    return (
        f"JDRT v2 {result['scenario']} seed{result['seed']} `{result['run_id']}`完了。COMPLETED/valid、"
        f"人物{result['evacuated']:,}避難＋{result['stranded']:,}立ち往生＝{result['evacuated'] + result['stranded']:,}、"
        f"request{result['request_completed']:,}完了＋{result['request_stranded']:,}立ち往生＝"
        f"{result['request_completed'] + result['request_stranded']:,}、Type4 {result['type4_evacuated']:,}・"
        f"Type3 {result['type3_evacuated']:,}、DRT {result['total_vkt_km']:.6f}km、"
        f"controller{result['controller_steps']:,}・観測{result['observations']:,}、"
        "teleport/collision/gridlock teleport/未処理Error全0。"
        f"Parameter{result['parameter_sha']}・入力{result['input_sha']}・出力{result['output_sha']}・"
        f"event{result['event_count']:,}行/SHA全PASS。中核{count}/20、次は{_next_text(next_cell)}"
    )


def _update_documents(root: Path, result: dict[str, Any]) -> dict[str, Any]:
    parameters = _json(root / PARAMETERS_REL)
    parameter_sha = _sha256(root / PARAMETERS_REL)
    cells = _cells(parameters)
    manifests = _matching_manifests(root, parameter_sha)
    completed = _completed_by_cell(manifests)
    current = (str(result["scenario"]), int(result["seed"]))
    if current not in cells:
        raise ValueError("run is not a fixed core cell")
    index = cells.index(current)
    if any(cell not in completed for cell in cells[: index + 1]):
        raise ValueError("a preceding core cell is not completed and valid")

    full_record_path = root / FULL_RECORD_REL
    full_record = _read_preserved(full_record_path)
    for cell in cells[:index]:
        if completed[cell]["run_id"] not in full_record:
            raise ValueError(f"preceding cell is not recorded: {cell}")
    count = index + 1
    total = len(cells)
    next_cell = cells[index + 1] if index + 1 < total else None
    seed_status = _seed_status(cells, count)
    today = date.today().isoformat()
    summary = _summary_line(result, count, next_cell)

    paths = [root / rel for rel in [FULL_RECORD_REL, TASKS_REL, CONTEXT_REL, DECISIONS_REL, PROGRESS_REL]]
    originals = {path: _read_preserved(path) for path in paths}
    ledger_path = root / LEDGER_REL
    ledger_existed = ledger_path.is_file()
    originals[ledger_path] = _read_preserved(ledger_path) if ledger_existed else ""
    ledger_ids = _recorded_ids(root)
    documents_recorded = all(result["run_id"] in originals[path] for path in paths)
    historical_backfill = result["run_id"] in full_record and any(
        cell in completed and completed[cell]["run_id"] in full_record for cell in cells[index + 1 :]
    )
    if (documents_recorded or historical_backfill) and result["run_id"] in ledger_ids:
        return {"record_status": "ALREADY_RECORDED", "count": count, "next": next_cell}

    updates: dict[Path, str] = {}
    updates[paths[0]] = (
        originals[paths[0]] if result["run_id"] in originals[paths[0]]
        else _update_full_record(originals[paths[0]], result, count, total, seed_status, next_cell)
    )

    tasks = originals[paths[1]]
    tasks = re.sub(r"^> 状態：.*$", f"> 状態：v1は技術停止して保全。常総市限定v2中核{count}/{total}、{seed_status}", tasks, count=1, flags=re.M)
    tasks = re.sub(r"現在はv2中核\d+/20[^。\r\n]*。", f"現在はv2中核{count}/{total}、{seed_status}。", tasks, count=1)
    task_state = f"✅ {count}/{total}" if count == total else f"🔄 {count}/{total}"
    task_row = (
        f"| JDRT-V2-R | v2中核4方式×5seed | {task_state} | JDRT-V2-G1 | "
        f"v2 validated runs、`JDRT-v2_full実験記録.md` | {seed_status}。直近`{result['run_id']}`、次は{_next_text(next_cell)} |"
    )
    tasks = re.sub(r"^\| JDRT-V2-R \|.*$", task_row, tasks, count=1, flags=re.M)
    updates[paths[1]] = tasks

    context = originals[paths[2]]
    context = re.sub(r"^\*\*最終更新：\*\*.*$", f"**最終更新：** {today}（常総市限定JDRT v2中核{count}/{total}、{seed_status}）", context, count=1, flags=re.M)
    context = re.sub(
        r"^\*\*Phase 1・2・3、主結論、先生コメント対応Scenario Cは確定済み。.*\*\*$",
        f"**Phase 1・2・3、主結論、先生コメント対応Scenario Cは確定済み。常総市限定JDRT v1は保全し、v2 {seed_status}、全{count}セルが全ゲートPASS。**",
        context,
        count=1,
        flags=re.M,
    )
    context = re.sub(
        r"^\| JDRT \|.*$",
        f"| JDRT | 常総市限定：動的配車・将来道路閉鎖情報の活用 | {'✅' if count == total else '🔄'} v1は保全。v2 {seed_status}、全{count}セルがCOMPLETED/valid・全ゲートPASS。次は{_next_text(next_cell)} |",
        context,
        count=1,
        flags=re.M,
    )
    context = re.sub(
        r"^\| 14 \| JDRT中核full実験 \|.*$",
        f"| 14 | JDRT中核full実験 | {'✅' if count == total else '🔄'} v1は保全。常総市限定v2中核{count}/{total}。次は{_next_text(next_cell)} |",
        context,
        count=1,
        flags=re.M,
    )
    if result["run_id"] not in context:
        nl = _nl(context)
        header = f"| 日付 | 内容 |{nl}|------|------|{nl}"
        context = context.replace(header, header + f"| {today} | {summary} |{nl}", 1)
    updates[paths[2]] = context

    decisions = originals[paths[3]]
    if result["run_id"] not in decisions:
        nl = _nl(decisions)
        decision = f"- **【常総市JDRT v2 {_short_scenario(result['scenario'])} seed{result['seed']}完了・{today}】** {summary}。途中解釈は行わない。"
        marker = nl + nl + "---" + nl + nl + "## 正本ファイル対応表"
        if marker not in decisions:
            raise ValueError("decision log insertion marker was not found")
        decisions = decisions.replace(marker, nl + decision + marker, 1)
    updates[paths[3]] = decisions

    progress = originals[paths[4]]
    if result["run_id"] not in progress:
        nl = _nl(progress)
        numbers = [int(value) for value in re.findall(r"(?m)^## (\d+)\.", progress)]
        section_no = max(numbers) + 1
        section = (
            f"## {section_no}. 常総市JDRT v2 {_short_scenario(result['scenario'])} seed {result['seed']}完了{nl}{nl}"
            f"`{result['run_id']}`を単独実行し、manifestの`COMPLETED`と`summary.valid=true`を確認した。{nl}{nl}"
            f"人物は避難完了{result['evacuated']:,}人（Type4 {result['type4_evacuated']:,}人、Type3 {result['type3_evacuated']:,}人）と"
            f"立ち往生{result['stranded']:,}人、requestは完了{result['request_completed']:,}件と立ち往生{result['request_stranded']:,}件だった。"
            f"DRT総VKTは{result['total_vkt_km']:.6f}km、空車VKTは{result['empty_vkt_km']:.6f}km、"
            f"到着時刻P95は{result['arrival_p95_sec'] if result['arrival_p95_sec'] is not None else 'NA'}秒、eventは{result['event_count']:,}件だった。"
            f"controller {result['controller_steps']:,}回、技術観測{result['observations']:,}回、teleport・collision teleport・gridlock teleport・未処理Errorは全0。"
            f"SUMO Warningは{result['warnings']:,}件、Error {result['errors']:,}件は全てcontroller捕捉済みroute拒否だった。{nl}{nl}"
            f"Parameter SHA {result['parameter_sha']}、入力SHA {result['input_sha']}、出力SHA {result['output_sha']}、event行数・SHA、人物・request CSV集計、VKT、Warning/Error実数を独立再計算し全PASS。"
            f"このrunをv2中核{count}/{total}セルへ採用する。次は{_next_text(next_cell)}。{nl}"
        )
        progress = progress.rstrip("\r\n") + nl + nl + section
    updates[paths[4]] = progress

    if documents_recorded or historical_backfill:
        updates = {path: originals[path] for path in paths}
    updates[ledger_path] = originals[ledger_path]
    if result["run_id"] not in ledger_ids:
        entry = {"recorded_on": today, "core_index": count, **result}
        separator = "" if not originals[ledger_path] or originals[ledger_path].endswith("\n") else "\n"
        updates[ledger_path] += separator + json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
    changed = [path for path, content in updates.items() if content != originals[path]]
    try:
        for path in changed:
            _atomic_write(path, updates[path])
        verification_paths = [paths[0]] if historical_backfill else paths
        missing = [str(path.relative_to(root)) for path in verification_paths if result["run_id"] not in _read_preserved(path)]
        if missing:
            raise RuntimeError(f"record verification failed for: {missing}")
        if result["run_id"] not in _recorded_ids(root):
            raise RuntimeError("record verification failed for ledger")
    except Exception:
        for path in changed:
            if path == ledger_path and not ledger_existed:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, originals[path])
        raise
    return {"record_status": "RECORDED", "count": count, "next": next_cell, "files": [str(path.relative_to(root)) for path in changed]}


def _process_alive(pid: int) -> bool:
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


def _state_path(root: Path, run_id: str) -> Path:
    return root / DRIVER_LOGS_REL / f"{run_id}.state.json"


def status(root: Path) -> dict[str, Any]:
    parameters_path = root / PARAMETERS_REL
    parameters = _json(parameters_path)
    cells = _cells(parameters)
    manifests = _matching_manifests(root, _sha256(parameters_path))
    completed = _completed_by_cell(manifests)
    full_record = _read_preserved(root / FULL_RECORD_REL)
    ledger_ids = _recorded_ids(root)
    completed_unrecorded = [
        {"scenario": cell[0], "seed": cell[1], "run_id": completed[cell]["run_id"]}
        for cell in cells
        if cell in completed and (completed[cell]["run_id"] not in full_record or completed[cell]["run_id"] not in ledger_ids)
    ]
    running = [
        {"run_id": item.get("run_id"), "scenario": item.get("scenario_id"), "seed": item.get("seed")}
        for item in manifests
        if item.get("status") == "RUNNING"
    ]
    next_incomplete = next((cell for cell in cells if cell not in completed), None)
    return {
        "completed_valid": len(completed),
        "recorded": sum(completed[cell]["run_id"] in full_record and completed[cell]["run_id"] in ledger_ids for cell in cells if cell in completed),
        "completed_unrecorded": completed_unrecorded,
        "running": running,
        "next_incomplete": None if next_incomplete is None else {"scenario": next_incomplete[0], "seed": next_incomplete[1]},
    }


def start_next(root: Path) -> dict[str, Any]:
    current = status(root)
    if current["completed_unrecorded"]:
        raise RuntimeError(f"record completed cell first: {current['completed_unrecorded'][0]}")
    if current["running"]:
        raise RuntimeError(f"a v2 run is already RUNNING: {current['running']}")
    cell = current["next_incomplete"]
    if cell is None:
        raise RuntimeError("all core cells are completed")
    scenario, seed = str(cell["scenario"]), int(cell["seed"])
    slug = scenario.removeprefix("JDRT-").lower().replace("-", "_")
    stem = f"core_v2_{slug}_seed{seed}_{date.today().strftime('%Y%m%d')}_skill"
    runs_dir = root / RUNS_REL
    counter = 1
    while (runs_dir / f"{stem}{counter:02d}").exists():
        counter += 1
    run_id = f"{stem}{counter:02d}"
    program = root / "04_プログラム"
    python = program / "venv/Scripts/python.exe"
    common = [
        str(python), "-m", "scripts.jdrt.full_run", "--project-root", "..",
        "--scenario", scenario, "--seed", str(seed), "--protocol-version", "v2", "--run-id", run_id,
    ]
    preflight = subprocess.run([*common, "--preflight-only"], cwd=program, text=True, capture_output=True, check=True)
    preflight_data = json.loads(preflight.stdout)
    if preflight_data.get("status") != "READY":
        raise RuntimeError(f"preflight was not READY: {preflight_data}")
    log_dir = root / DRIVER_LOGS_REL
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{run_id}.stdout.log"
    stderr_path = log_dir / f"{run_id}.stderr.log"
    kwargs: dict[str, Any] = {"cwd": program, "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000
    else:
        kwargs["start_new_session"] = True
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(common, stdout=stdout, stderr=stderr, **kwargs)
    state = {
        "run_id": run_id,
        "pid": process.pid,
        "scenario": scenario,
        "seed": seed,
        "started_on": date.today().isoformat(),
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "preflight": preflight_data,
    }
    _atomic_write(_state_path(root, run_id), json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return {"start_status": "STARTED", **state}


def check_run(root: Path, run_id: str) -> dict[str, Any]:
    state_path = _state_path(root, run_id)
    state = _json(state_path) if state_path.is_file() else {"run_id": run_id, "pid": None}
    manifest_path = root / RUNS_REL / run_id / "manifest.json"
    manifest = _json(manifest_path) if manifest_path.is_file() else {}
    pid = int(state["pid"]) if state.get("pid") is not None else -1
    status_value = manifest.get("status", "MISSING")
    events_path = manifest_path.parent / "events.jsonl"
    last_event = None
    observed_events = 0
    if events_path.is_file():
        with events_path.open("rb") as handle:
            for line in handle:
                if line.strip() and line.endswith(b"\n"):
                    observed_events += 1
                    last_event = json.loads(line)
    return {
        "run_id": run_id,
        "pid": None if pid < 0 else pid,
        "process_alive": _process_alive(pid),
        "manifest_status": status_value,
        "ready_to_record": status_value == "COMPLETED" and manifest.get("summary", {}).get("valid") is True,
        "started_on": state.get("started_on"),
        "observed_event_count": observed_events,
        "last_event_sim_time_sec": None if last_event is None else last_event.get("sim_time_sec"),
        "last_event_type": None if last_event is None else last_event.get("event_type"),
    }


def recover(root: Path, run_id: str) -> dict[str, Any]:
    check = check_run(root, run_id)
    if check["manifest_status"] != "RUNNING":
        raise RuntimeError("only a RUNNING manifest can be recovered")
    if check["pid"] is None:
        raise RuntimeError("no skill state file/PID exists; inspect manually")
    if check["process_alive"]:
        raise RuntimeError("recorded process is still alive")
    program = root / "04_プログラム"
    sys.path.insert(0, str(program))
    from scripts.jdrt.full_run import finalize_interrupted_run

    path = finalize_interrupted_run(root, run_id, "Skill-recorded process ended before manifest finalization; PID confirmed absent.")
    return {"recovery_status": "FAILED_PRESERVED", "manifest": str(path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", help="repository root; auto-detected when omitted")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("start-next")
    for command in ["check", "recover", "validate", "record"]:
        child = subparsers.add_parser(command)
        child.add_argument("--run-id", required=True)
    args = parser.parse_args()
    root = _find_project_root(args.project_root)
    started = time.monotonic()
    try:
        if args.command == "status":
            result = status(root)
        elif args.command == "start-next":
            result = start_next(root)
        elif args.command == "check":
            result = check_run(root, args.run_id)
        elif args.command == "recover":
            result = recover(root, args.run_id)
        elif args.command == "validate":
            result = validate_run(root, args.run_id)
        else:
            validation = validate_run(root, args.run_id)
            if validation["validation"] != "PASS":
                raise RuntimeError(f"validation failed: {validation['issues']}")
            result = {**validation, **_update_documents(root, validation)}
        _log_operation(root, args.command, getattr(args, "run_id", None), started, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    except Exception as exc:
        failure = {"command": args.command, "error_type": type(exc).__name__, "error": str(exc)}
        try:
            _log_operation(root, args.command, getattr(args, "run_id", None), started, failure)
        except OSError as log_error:
            failure["operation_log_error"] = str(log_error)
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
