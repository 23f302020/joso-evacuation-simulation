"""Independent post-analysis readback; only reads source and analysis files."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    root = Path(__file__).resolve().parents[3]
    folder = root / "06_研究結果/jdrt"
    evidence = json.loads((folder / "JDRT-v2_中核比較_manifest.json").read_text(encoding="utf-8"))
    for relative, expected in evidence["source_sha256"].items():
        assert digest(root / relative) == expected, relative
    for filename, item in evidence["artifacts"].items():
        assert digest(folder / filename) == item["sha256"], filename
        if "rows" in item:
            assert len(rows(folder / filename)) == item["rows"], filename
    parameters = json.loads((root / "04_プログラム/config/jdrt_parameters_v2.json").read_text(encoding="utf-8"))
    ledger = [json.loads(line) for line in (root / "05_タスク管理/jdrt/JDRT-v2_セル検証台帳.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    cell_results = {}
    for entry in ledger:
        people = rows(root / "04_プログラム/output/sumo/regions/08211/experiments/jdrt/runs" / entry["run_id"] / "person_results.csv")
        assert len(people) == len({person["person_id"] for person in people}) == parameters["population"]["drt_eligible"]
        type4 = [person for person in people if person["person_type"] == "4"]
        assert len(type4) == parameters["population"]["type4"]
        completed = sum(person["status"] == "EVACUATED" for person in type4)
        assert completed == entry["type4_evacuated"]
        times = sorted(float(person["arrival_time_sec"]) for person in people if person["status"] == "EVACUATED")
        assert times[math.ceil(.95 * len(times)) - 1] == entry["arrival_p95_sec"]
        cell_results[(entry["scenario"], entry["seed"])] = completed
    primary = [row for row in rows(folder / "JDRT-v2_中核比較_paired.csv") if row["role"] == "primary_PAP"]
    differences = []
    for seed in parameters["experiment"]["paired_seeds"]:
        number = cell_results[(parameters["dispatchers"]["primary_proposal"], seed)] - cell_results[(parameters["dispatchers"]["primary_baseline"], seed)]
        difference = number * 100 / parameters["population"]["type4"]
        saved = next(row for row in primary if int(row["seed"]) == seed)
        assert int(saved["type4_evacuated"]) == number
        assert math.isclose(float(saved["type4_rate_pct"]), difference, abs_tol=1e-10)
        differences.append(difference)
    saved_summary = next(row for row in rows(folder / "JDRT-v2_中核比較_summary.csv") if row["group_type"] == "comparison" and row["group"] == evidence["primary_contrast"] and row["metric"] == "type4_rate_pct")
    for field, actual in [("median", statistics.median(differences)), ("min", min(differences)), ("max", max(differences))]:
        assert math.isclose(float(saved_summary[field]), actual, abs_tol=1e-10)
    print(json.dumps({"verification": "PASS", "source_sha": len(evidence["source_sha256"]), "output_sha": len(evidence["artifacts"]), "cells": len(cell_results), "primary_seed_differences_pp": differences, "median_pp": statistics.median(differences)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
