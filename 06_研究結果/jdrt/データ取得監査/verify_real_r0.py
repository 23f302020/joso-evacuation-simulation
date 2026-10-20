"""Read-only independent CSV audit of the preserved REAL-R0 pilot.

Writes only the requested audit JSON, never simulation inputs or run artifacts.
This is a data-readiness audit, not formal acceptance of the realistic series.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--run-id", default="real_r0_seed23423_20260911_skill03")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("R0独立監査_20261015.json"))
    args = parser.parse_args()
    root = args.project_root.resolve()
    base = root / "04_プログラム/output/sumo/regions/08211"
    run = base / "experiments/jdrt_realistic/runs" / args.run_id
    sources: dict[str, dict] = {}

    def source(path: Path) -> None:
        key = path.relative_to(root).as_posix()
        if key not in sources:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            sources[key] = {"sha256": digest.hexdigest(), "size_bytes": path.stat().st_size}

    def read_json(path: Path) -> dict:
        source(path)
        return json.loads(path.read_text(encoding="utf-8"))

    def read_csv(path: Path) -> list[dict]:
        source(path)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            sources[path.relative_to(root).as_posix()].update(columns=reader.fieldnames, row_count=len(rows))
            return rows

    def idset(rows: list[dict], field: str) -> set[str]:
        return {row[field] for row in rows}

    parameters = read_json(root / "04_プログラム/config/jdrt_realistic_parameters_v1.json")
    manifest = read_json(run / "manifest.json")
    engine = run / "engine" / manifest["summary"]["engine_run_id"]
    engine_manifest = read_json(engine / "run_manifest.json")
    accounting = read_json(engine / "accounting_validation.json")
    mode = read_csv(engine / "scenario_c_mode_ledger.csv")
    walk = read_csv(engine / "walk_person_ledger.csv")
    occupants = read_csv(engine / "car_occupancy_ledger.csv")
    cars = read_csv(engine / "car_assignment.csv")
    people_log = read_csv(engine / "person_log.csv")
    vehicle_log = read_csv(engine / "vehicle_log.csv")
    closure_log = read_csv(engine / "closure_log.csv")
    edge_rows = read_csv(run / "edge_congestion.csv")
    closure_events = sorted(read_json(base / "derived/closure_timeline_sumo.json")["closures"], key=lambda x: x["sim_time_sec"])
    registered_sha = {}
    for item in parameters["inputs"]:
        path = root / item["path"]
        source(path)
        registered_sha[item["path"]] = sources[item["path"]]["sha256"] == item["sha256"]
    mids, wids, oids = idset(mode, "person_id"), idset(walk, "person_id"), idset(occupants, "person_id")
    cids = idset(cars, "vehicle_id")
    occupancy = Counter(row["vehicle_id"] for row in occupants)
    occupant_map = {row["person_id"]: row for row in occupants}
    person_map = {row["person_id"]: row for row in people_log}
    vehicle_map = {row["vehicle_id"]: row for row in vehicle_log}
    checks = {
        "registered_input_sha": all(registered_sha.values()),
        "mode_ids_unique": len(mids) == len(mode),
        "walk_ids_unique": len(wids) == len(walk),
        "occupant_ids_unique": len(oids) == len(occupants),
        "mode_partition_exact": not wids & oids and wids | oids == mids,
        "walk_log_ids_exact_unique": idset(people_log, "person_id") == wids and len(person_map) == len(people_log),
        "vehicle_ids_exact_unique": idset(vehicle_log, "vehicle_id") == cids and len(vehicle_map) == len(vehicle_log) == len(cids),
        "occupant_vehicle_references_exact": idset(occupants, "vehicle_id") == cids,
        "vehicle_occupancy_counts_match": all(int(row["occupancy_count"]) == occupancy[row["vehicle_id"]] for row in vehicle_log),
        "car_person_origin_age_match": all(all(row[col] == occupant_map[row["person_id"]][col] for col in ("origin_id", "KEY_CODE", "age_group")) for row in mode if row["assigned_mode"] == "car"),
        "assigned_modes_match_ledgers": {row["person_id"] for row in mode if row["assigned_mode"] == "car"} == oids and {row["person_id"] for row in mode if row["assigned_mode"] == "walk"} == wids,
    }
    type_population, type_arrived, terminals = Counter(), Counter(), Counter()
    for row in mode:
        result = vehicle_map[occupant_map[row["person_id"]]["vehicle_id"]] if row["assigned_mode"] == "car" else person_map[row["person_id"]]
        type_population[row["person_type"]] += 1
        type_arrived[row["person_type"]] += result["arrived"].lower() == "true"
        terminals[result["final_status"]] += 1
    completed = sum(type_arrived.values())
    checks["population_matches_registry"] = len(mode) == parameters["population"]["total_people"] and len(walk) == parameters["population"]["walk_people"] and len(occupants) == parameters["population"]["car_people"]
    checks["completion_matches_accounting"] = completed == accounting["completed_people"] and len(mode) - completed == accounting["unfinished_people"]
    cumulative, index, flag_mismatches, invalid_counts = set(), 0, 0, 0
    for row in edge_rows:
        while index < len(closure_events) and closure_events[index]["sim_time_sec"] <= float(row["sim_time_sec"]):
            cumulative.update(closure_events[index]["closed_sumo_edge_ids"])
            index += 1
        flag_mismatches += (row["closed"] == "true") != (row["edge_id"] in cumulative)
        invalid_counts += not (0 <= int(row["halting_vehicle_count"]) <= int(row["vehicle_count"]) and float(row["mean_speed_mps"]) >= 0)
    cumulative = set()
    closure_counts = []
    for event in closure_events:
        cumulative.update(event["closed_sumo_edge_ids"])
        closure_counts.append(len(cumulative))
    times = sorted({int(row["sim_time_sec"]) for row in edge_rows})
    edges = idset(edge_rows, "edge_id")
    keys = {(row["sim_time_sec"], row["edge_id"]) for row in edge_rows}
    checks.update(
        edge_time_ids_unique=len(keys) == len(edge_rows),
        edge_time_grid_matches_registry=times == list(range(0, parameters["experiment"]["end_sec"] + 1, parameters["experiment"]["edge_observation_interval_sec"])),
        edge_counts_valid=invalid_counts == 0,
        edge_closure_flags_match=flag_mismatches == 0,
        closure_event_times_match=[int(row["sim_time_sec"]) for row in closure_log] == [int(row["sim_time_sec"]) for row in closure_events],
        closure_cumulative_counts_match=[int(row["vehicle_cumulative_closed_edges"]) for row in closure_log] == closure_counts,
    )
    network = base / "experiments/scenario_c/network/08211_ped.net.xml"
    source(network)
    net_edges = set()
    for _, element in ET.iterparse(network, events=("end",)):
        if element.tag == "edge":
            if not element.attrib.get("id", "").startswith(":"):
                net_edges.add(element.attrib["id"])
            element.clear()
    checks["edge_ids_exist_in_pedestrian_network"] = edges <= net_edges
    cfg = engine / "scenario_c.sumocfg"
    source(cfg)
    xml = ET.parse(cfg)
    fcd_period = xml.find("output/device.fcd.period").get("value")
    step_element = xml.find("time/step-length")
    logpath = engine / "sumo.log"
    source(logpath)
    log = logpath.read_text(encoding="utf-8", errors="replace").splitlines()
    errors = sum("Error:" in line for line in log)
    warnings = sum("Warning:" in line for line in log)
    checks.update(sumo_error_lines_zero=errors == 0, sumo_teleport_collision_tokens_absent=not any("teleport" in line.lower() or "collision" in line.lower() for line in log))
    v2_path = next((base / "experiments/jdrt/runs").glob("core_v2_b3_seed23423*/metrics.json"))
    v2 = read_json(v2_path)
    source(Path(__file__).resolve())
    output_sha = {
        path: details["sha256"] == manifest["output_sha256"][str((root / path).relative_to(run)).replace("\\", "/")]
        for path, details in sources.items()
        if (root / path).is_relative_to(run) and root / path != run / "manifest.json"
    }
    checks["read_run_output_sha"] = all(output_sha.values())
    departures = [float(row["depart"]) for row in vehicle_log if row["depart"]]
    report = {
        "generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
        "scope": "preserved REAL-R0 pilot CSV readback; not formal record or new simulation",
        "run_id": args.run_id,
        "checks": checks,
        "checked_csv_invariants": "PASS" if all(checks.values()) else "FAIL",
        "registered_input_sha_checks": registered_sha,
        "read_run_output_sha_checks": output_sha,
        "population": {"total": len(mode), "walk": len(walk), "car_people": len(occupants), "vehicles": len(cars), "completed": completed, "unfinished": len(mode) - completed, "by_type": dict(type_population), "completed_by_type": dict(type_arrived), "terminal_people_by_reason": dict(terminals), "occupancy_histogram": dict(sorted(Counter(occupancy.values()).items()))},
        "departures": {"planned_time_counts": dict(Counter(row["depart"] for row in cars)), "actual_count": len(departures), "missing_actual_count": len(vehicle_log) - len(departures), "actual_min_sec": min(departures), "actual_max_sec": max(departures), "arrivals_after_registered_horizon": sum(float(row["arrival"]) > parameters["experiment"]["end_sec"] for row in people_log + vehicle_log if row["arrival"])},
        "edge_coverage": {"row_count": len(edge_rows), "unique_time_edge_count": len(keys), "time_count": len(times), "time_min_sec": min(times), "time_max_sec": max(times), "time_gap_histogram_sec": dict(Counter(b-a for a,b in zip(times,times[1:]))), "observed_edges": len(edges), "noninternal_pedestrian_net_edges": len(net_edges), "unobserved_pedestrian_net_edges": len(net_edges - edges), "zero_vehicle_rows": sum(int(row["vehicle_count"]) == 0 for row in edge_rows), "closed_true_rows": sum(row["closed"] == "true" for row in edge_rows), "closed_flag_mismatches": flag_mismatches, "coverage_denominator_limit": "Pedestrian-enabled network edge count, not a vehicle-passable-road denominator; vehicle-class permission filtering not performed. Only occupied noninternal edges are written; absent rows are not observed zero traffic."},
        "technical_evidence": {"registered_step_sec": parameters["experiment"]["step_length_sec"], "sumocfg_explicit_step_sec": None if step_element is None else step_element.get("value"), "fcd_period_sec": float(fcd_period), "engine_last_sim_time_sec": engine_manifest["last_sim_time"], "requested_end_sec": engine_manifest["requested_end_sec"], "sumo_error_line_count": errors, "sumo_warning_line_count": warnings, "engine_reported_closed_entry_violations": accounting["closed_edge_entry_violation_count"], "engine_reported_pending_person_reroutes": accounting["pending_person_reroute_count"], "engine_reported_pending_vehicle_reroutes": accounting["pending_vehicle_reroute_count"], "distinction": "Closure timeline/CSV flags and error lines were recomputed. Entry violations and pending queues above are engine reports, not independently reconstructed trajectories."},
        "cross_series": {"v2_example_type4_denominator": v2["type4_denominator"], "r0_type4_population": type_population["type4"], "v2_example_drt_denominator": v2["all_drt_denominator"], "r0_walk_population": len(walk), "paired_person_mapping": "not supplied; v2 and R0 are different cohorts/protocols; R0/R1/R2 common person ledger is not yet available"},
        "not_verified": ["Per-step runtime observation continuity; step length is registered 1 second but not explicitly present in saved SUMO config.", "Full FCD trajectory reconstruction and independently recomputed closure-entry violations; full FCD was not parsed.", "Vehicle-class-specific network denominator and route capacity limits.", "R0/R1/R2 common-person, mode-transfer and permitted-condition-difference checks: R1/R2 not available.", "Shelter capacity/opening/overflow, real fleet/depot availability, real reservations/modal shares/background demand.", "Full run-output SHA rehash in this script: only sources read here are rehashed; existing skill validate separately returned PASS for registered full output hashes.", "Formal REAL-R0 adoption is withheld; technical CSV PASS does not satisfy REAL-P1/P2 research gates."],
        "sources": sources,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "checked_csv_invariants": report["checked_csv_invariants"], "checks": len(checks), "sources": len(sources)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
