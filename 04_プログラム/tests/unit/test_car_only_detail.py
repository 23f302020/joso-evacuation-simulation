from __future__ import annotations

import csv
from pathlib import Path

from p3_car_only_detail import (
    aggregate_fcd_edges,
    build_vehicle_details,
    load_canonical_runs,
    summarize_groups,
    summarize_run,
)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_load_canonical_runs_uses_only_a1_to_a3(tmp_path: Path) -> None:
    fields = ["scenario", "run", "seed", "run_id", "artifact_dir"]
    rows = [
        {"scenario": "A", "run": f"A#{index}", "seed": index, "run_id": f"run_{index}", "artifact_dir": tmp_path / f"a{index}"}
        for index in (1, 2, 3, 4)
    ]
    rows.append({"scenario": "B", "run": "B#1", "seed": 1, "run_id": "b", "artifact_dir": tmp_path / "b"})
    source = _write_csv(tmp_path / "replicates.csv", fields, rows)

    result = load_canonical_runs(source)

    assert [row["run"] for row in result] == ["A#1", "A#2", "A#3"]
    assert [row["seed"] for row in result] == [1, 2, 3]


def test_fcd_edge_aggregation_uses_sampled_observations(tmp_path: Path) -> None:
    fcd = tmp_path / "fcd.xml"
    fcd.write_text(
        """<fcd-export>
<timestep time="60"><vehicle id="v1" lane="edgeA_0" speed="0"/><vehicle id="v2" lane=":j0_0_0" speed="2"/></timestep>
<timestep time="120"><vehicle id="v1" lane="edgeA_1" speed="4"/></timestep>
</fcd-export>""",
        encoding="utf-8",
    )

    rows = {row["edge_id"]: row for row in aggregate_fcd_edges(fcd)}

    assert rows["edgeA"]["observed_vehicle_count"] == 1
    assert rows["edgeA"]["observation_count"] == 2
    assert rows["edgeA"]["mean_speed_mps"] == 2.0
    assert rows["edgeA"]["stopped_observation_count"] == 1
    assert rows["edgeA"]["sampled_stopped_vehicle_seconds"] == 60.0
    assert rows[":j0_0"]["observed_vehicle_count"] == 1


def test_vehicle_and_group_accounting() -> None:
    logs = [
        {"vehicle_id": "v1", "arrived": "True", "duration": "100", "arrival": "110", "depart": "10"},
        {"vehicle_id": "v2", "arrived": "False", "duration": "", "arrival": "", "depart": "20", "long_stopped": "True"},
    ]
    assignments = {
        "v1": {"vehicle_id": "v1", "vehicle_kind": "private_car", "origin_id": "o1", "KEY_CODE": "k1", "shelter_id": "s1", "shelter_name": "Shelter", "passenger_equivalent": "2.3"},
        "v2": {"vehicle_id": "v2", "vehicle_kind": "rescue_car", "origin_id": "o1", "KEY_CODE": "k1", "shelter_id": "s1", "shelter_name": "Shelter", "passenger_equivalent": "1"},
    }
    tripinfo = {"v1": {"routeLength": 1000.0, "waitingTime": 5.0}}
    stagnation = {"v2": {"layer": "queue_behind_blockage", "current_edge": "e1"}}

    details = build_vehicle_details(logs, assignments, tripinfo, stagnation)
    run = summarize_run(details)
    origins = summarize_groups(details, ("origin_id", "KEY_CODE"))

    assert run["vehicle_count"] == 2
    assert run["arrived_count"] == 1
    assert run["not_arrived_count"] == 1
    assert run["passenger_equivalent_total"] == 3.3
    assert details[1]["stagnation_layer"] == "queue_behind_blockage"
    assert origins[0]["vehicle_count"] == 2
    assert origins[0]["completion_rate"] == 0.5
