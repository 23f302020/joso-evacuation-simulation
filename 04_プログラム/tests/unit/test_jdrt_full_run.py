from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from jdrt import EvacueeStatus, load_joso_input_bundle
from jdrt.full_run import (
    CORE_SCENARIOS,
    _completed_core_cells,
    _write_sumocfg,
    build_dispatcher,
    build_result_rows,
    finalize_interrupted_run,
    preflight_full_run,
    summarize_sumo_error_log,
    write_initial_bus_route,
    write_private_vehicle_route,
)
from jdrt.workspace import JDRTWorkspace


def test_core_dispatchers_keep_true_and_predicted_information_separate(
    program_dir: Path,
) -> None:
    bundle = load_joso_input_bundle(program_dir.parent)

    for scenario_id in ("JDRT-B2", "JDRT-B3"):
        _, predicted = build_dispatcher(scenario_id, bundle)
        assert predicted is None

    _, perfect = build_dispatcher("JDRT-P1", bundle)
    _, late = build_dispatcher("JDRT-P2-L15", bundle)
    assert perfect == bundle.true_closures.closure_time_by_edge
    assert late == {
        edge_id: closure_time + 900
        for edge_id, closure_time in bundle.true_closures.closure_time_by_edge.items()
    }
    assert perfect is not bundle.true_closures.closure_time_by_edge


def test_private_route_contains_only_formally_retained_cars(
    program_dir: Path, tmp_path: Path
) -> None:
    bundle = load_joso_input_bundle(program_dir.parent)
    route_path = tmp_path / "private.rou.xml"

    digest = write_private_vehicle_route(route_path, bundle)

    root = ET.parse(route_path).getroot()
    trips = root.findall("trip")
    assert len(trips) == 8_164
    assert {trip.attrib["id"] for trip in trips} == {
        item.vehicle_id for item in bundle.private_vehicles
    }
    assert all(not trip.attrib["id"].startswith("rescue_") for trip in trips)
    assert len(digest) == 64


def test_initial_bus_route_preloads_the_fixed_fleet(
    program_dir: Path, tmp_path: Path
) -> None:
    bundle = load_joso_input_bundle(program_dir.parent)
    route_path = tmp_path / "initial_buses.rou.xml"

    digest = write_initial_bus_route(
        route_path,
        bundle,
        program_dir
        / "output"
        / "sumo"
        / "regions"
        / "08211"
        / "network"
        / "08211.net.xml",
        21_600,
    )

    vehicles = ET.parse(route_path).getroot().findall("vehicle")
    assert [item.attrib["id"] for item in vehicles] == [
        item.vehicle_id for item in bundle.vehicles
    ]
    assert all(item.find("stop") is not None for item in vehicles)
    assert all(item.find("stop").attrib["parking"] == "false" for item in vehicles)
    assert len(digest) == 64


def test_result_rows_compute_metrics_from_current_states(program_dir: Path) -> None:
    bundle = load_joso_input_bundle(program_dir.parent)
    bundle.evacuees[0].status = EvacueeStatus.EVACUATED
    bundle.evacuees[0].arrival_time = 100

    people, requests, metrics = build_result_rows(bundle)

    assert len(people) == 3_255
    assert len(requests) == 1_440
    assert metrics["all_drt_evacuated"] == 1
    expected_type = bundle.evacuees[0].person_type
    assert metrics[f"type{expected_type}_evacuated"] == 1
    assert metrics["arrival_time_p95_sec_nearest_rank"] == 100


def test_preflight_checks_each_fixed_scenario_without_writing_runs(
    program_dir: Path,
) -> None:
    runs_dir = program_dir / "output" / "sumo" / "regions" / "08211" / "experiments" / "jdrt" / "runs"
    before = {path.name for path in runs_dir.iterdir() if path.is_dir()}

    for scenario_id in CORE_SCENARIOS:
        for seed in (23423, 42, 1, 7, 101):
            try:
                result = preflight_full_run(program_dir.parent, scenario_id, seed)
            except RuntimeError as error:
                assert "completed core cell already exists" in str(error)
                continue
            assert result["status"] == "READY"
            assert result["scenario_id"] == scenario_id
            assert result["private_vehicle_count"] == 8_164
            assert result["request_count"] == 1_440
            break

    after = {path.name for path in runs_dir.iterdir() if path.is_dir()}
    assert after == before


def test_preflight_rejects_unregistered_seed(program_dir: Path) -> None:
    with pytest.raises(ValueError, match="seed must be one of"):
        preflight_full_run(program_dir.parent, "JDRT-B2", 999)


def test_completed_cells_are_separate_by_parameter_sha(tmp_path: Path) -> None:
    workspace = JDRTWorkspace(tmp_path)
    for run_id, parameter_sha in (("v1_run", "v1-sha"), ("v2_run", "v2-sha")):
        run_dir = workspace.run_dir(run_id)
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "status": "COMPLETED",
                    "scenario_id": "JDRT-B3",
                    "seed": 23423,
                    "parameter_sha256": parameter_sha,
                    "summary": {"purpose": "core_experiment"},
                }
            ),
            encoding="utf-8",
        )

    assert _completed_core_cells(workspace, "v1-sha") == {("JDRT-B3", 23423)}
    assert _completed_core_cells(workspace, "v2-sha") == {("JDRT-B3", 23423)}
    assert _completed_core_cells(workspace, "unknown-sha") == set()


def test_v2_sumocfg_fixes_step_and_collision_gate(tmp_path: Path) -> None:
    config_path = tmp_path / "run" / "jdrt.sumocfg"
    config_path.parent.mkdir()
    _write_sumocfg(
        config_path,
        tmp_path / "network.net.xml",
        tmp_path / "initial.rou.xml",
        tmp_path / "private.rou.xml",
        tmp_path / "vtypes.add.xml",
        21_600,
        step_length_sec=0.5,
        collision_action="teleport",
        time_to_teleport_sec=-1,
    )

    root = ET.parse(config_path).getroot()
    assert root.find("./time/step-length").attrib["value"] == "0.5"
    assert root.find("./processing/collision.action").attrib["value"] == "teleport"
    assert root.find("./processing/time-to-teleport").attrib["value"] == "-1"


def test_sumo_log_summary_separates_warnings_and_errors(tmp_path: Path) -> None:
    log = tmp_path / "sumo_error.log"
    log.write_text(
        "Warning: one\n"
        "Warning: Teleporting vehicle 'car_1'; side collision with vehicle 'car_2'.\n"
        "Warning: Teleporting vehicle 'car_3'; waited too long (jam).\n"
        "Error: two\n"
        "Error: Answered with error: Route replacement failed for vehicle 'bus_std_3'.\n"
        "Warning: three\n",
        encoding="utf-8",
    )

    assert summarize_sumo_error_log(log) == {
        "bytes": log.stat().st_size,
        "warning_count": 4,
        "error_count": 2,
        "handled_route_rejection_count": 1,
        "unhandled_error_count": 1,
        "collision_teleport_count": 1,
        "gridlock_teleport_count": 1,
    }


def test_interrupted_run_recovery_only_accepts_running_manifest(tmp_path: Path) -> None:
    project_root = tmp_path
    run_dir = (
        project_root
        / "04_プログラム"
        / "output"
        / "sumo"
        / "regions"
        / "08211"
        / "experiments"
        / "jdrt"
        / "runs"
        / "run_1"
    )
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text('{"event": 1}\n', encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        '{"status":"RUNNING","event_log":"events.jsonl"}\n', encoding="utf-8"
    )

    manifest_path = finalize_interrupted_run(project_root, "run_1", "timeout")
    recovered = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
    assert recovered["status"] == "FAILED"
    assert recovered["event_count"] == 1
    assert recovered["summary"]["error"] == "timeout"

    with pytest.raises(ValueError, match="RUNNING"):
        finalize_interrupted_run(project_root, "run_1", "again")
