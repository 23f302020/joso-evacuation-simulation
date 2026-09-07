from __future__ import annotations

import json
from pathlib import Path

import pytest

import scenario_c_evaluate as evaluate


def write_manifest(
    root: Path,
    run_id: str,
    *,
    technical_valid: bool,
    full: bool = True,
) -> None:
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    manifest = {
        "run_id": run_id,
        "condition": {"condition_id": "condition_a"},
        "seed": 7,
        "technical_valid": technical_valid,
        "full_sumo_run_executed": full,
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_discover_runs_selects_valid_and_preserves_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(evaluate, "EXPECTED_RUNS", {"condition_a": (7,)})
    write_manifest(tmp_path, "invalid_run", technical_valid=False)
    write_manifest(tmp_path, "valid_run", technical_valid=True)

    selected, invalid = evaluate.discover_runs(tmp_path)

    assert selected[("condition_a", 7)].name == "valid_run"
    assert invalid == ["invalid_run"]


def test_discover_runs_rejects_duplicate_valid_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(evaluate, "EXPECTED_RUNS", {"condition_a": (7,)})
    write_manifest(tmp_path, "valid_run_a", technical_valid=True)
    write_manifest(tmp_path, "valid_run_b", technical_valid=True)

    with pytest.raises(RuntimeError, match="duplicate valid full runs"):
        evaluate.discover_runs(tmp_path)


def test_discover_runs_rejects_missing_registered_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(evaluate, "EXPECTED_RUNS", {"condition_a": (7,)})

    with pytest.raises(RuntimeError, match="missing valid full runs"):
        evaluate.discover_runs(tmp_path)


def test_percentile_uses_linear_interpolation() -> None:
    assert evaluate.percentile([], 0.9) is None
    assert evaluate.percentile([5], 0.9) == 5
    assert evaluate.percentile([0, 10], 0.9) == 9


def test_validate_run_rejects_changed_primary_output(tmp_path: Path) -> None:
    summary = {"population": 21_539, "completed_people": 1}
    accounting = {
        "unfinished_people": 21_538,
        "population_closes": True,
        "completion_accounting_closes": True,
        "processed_closure_event_count": 8,
        "expected_closure_event_count": 8,
        "closed_edge_entry_violation_count": 0,
        "pending_person_reroute_count": 0,
        "pending_vehicle_reroute_count": 0,
        "run_error": "",
    }
    (tmp_path / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (tmp_path / "accounting_validation.json").write_text(
        json.dumps(accounting), encoding="utf-8"
    )
    for filename in (
        "vehicle_log.csv",
        "person_log.csv",
        "car_occupancy_ledger.csv",
        "walk_person_ledger.csv",
    ):
        (tmp_path / filename).write_text("header\n", encoding="utf-8")
    (tmp_path / "sumo.log").write_text("Simulation ended\n", encoding="utf-8")
    output_files = (
        "run_summary.json",
        "accounting_validation.json",
        "vehicle_log.csv",
        "person_log.csv",
        "car_occupancy_ledger.csv",
        "walk_person_ledger.csv",
    )
    manifest = {
        "run_id": "valid",
        "technical_valid": True,
        "full_sumo_run_executed": True,
        "last_sim_time": 21_600,
        "run_error": "",
        "existing_outputs_modified": False,
        "sentinel_before": {"a": "same"},
        "sentinel_after": {"a": "same"},
        "output_sha256": {
            filename: evaluate.sha256(tmp_path / filename) for filename in output_files
        },
    }
    (tmp_path / "run_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    evaluate.validate_run(tmp_path)
    (tmp_path / "vehicle_log.csv").write_text("changed\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="output SHA mismatch: vehicle_log.csv"):
        evaluate.validate_run(tmp_path)


def test_summarize_event_logs_counts_shallow_and_reroutes() -> None:
    vehicles = [
        {"reroute_count": "2", "reroute_failed": "false", "long_stopped": "true", "max_consecutive_stop_sec": "12"},
        {"reroute_count": "1", "reroute_failed": "true", "long_stopped": "false", "max_consecutive_stop_sec": "5"},
    ]
    people = [
        {"person_xml_emitted": "true", "reroute_count": "1", "reroute_failed": "false", "shallow_entry_count": "2", "shallow_time_sec": "7", "dry_speed_restore_count": "1", "max_consecutive_stop_sec": "3"},
        {"person_xml_emitted": "false", "reroute_count": "0", "reroute_failed": "true", "shallow_entry_count": "0", "shallow_time_sec": "0", "dry_speed_restore_count": "0", "max_consecutive_stop_sec": "0"},
    ]

    result = evaluate.summarize_event_logs(vehicles, people)

    assert result["vehicle_reroute_count"] == 3
    assert result["vehicle_reroute_failed_count"] == 1
    assert result["vehicle_long_stopped_count"] == 1
    assert result["walk_xml_emitted_count"] == 1
    assert result["walk_shallow_exposed_people"] == 1
    assert result["walk_shallow_entry_count"] == 2
    assert result["walk_shallow_person_seconds"] == 7
    assert result["walk_dry_speed_restore_count"] == 1
