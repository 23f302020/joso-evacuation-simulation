from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from jdrt import JDRTEvent, JDRTWorkspace, RunRecorder


def make_parameter_file(tmp_path: Path) -> Path:
    path = tmp_path / "parameters.json"
    path.write_text('{"city_code":"08211"}\n', encoding="utf-8")
    return path


def test_run_recorder_writes_independent_manifest_and_events(tmp_path: Path) -> None:
    workspace = JDRTWorkspace(tmp_path)
    parameter_file = make_parameter_file(tmp_path)
    recorder = RunRecorder(
        workspace,
        "smoke_001",
        "JDRT-B3",
        23423,
        parameter_file,
        {"population_and_types": "abc"},
    )
    recorder.append(
        JDRTEvent(
            sim_time_sec=60,
            event_type="REQUEST_ASSIGNED",
            entity_id="request_1",
            details={"vehicle_id": "vehicle_1"},
        )
    )
    manifest_path = recorder.finalize("COMPLETED", {"evacuated": 1})

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    events = (recorder.run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert manifest["status"] == "COMPLETED"
    assert manifest["event_count"] == 1
    assert manifest["summary"] == {"evacuated": 1}
    assert manifest["event_log_sha256"] == hashlib.sha256(
        events.encode("utf-8")
    ).hexdigest()
    assert "REQUEST_ASSIGNED" in events


def test_run_recorder_refuses_existing_run_directory(tmp_path: Path) -> None:
    workspace = JDRTWorkspace(tmp_path)
    parameter_file = make_parameter_file(tmp_path)
    RunRecorder(workspace, "same_run", "JDRT-B3", 1, parameter_file, {})

    with pytest.raises(FileExistsError):
        RunRecorder(workspace, "same_run", "JDRT-B3", 1, parameter_file, {})


def test_run_recorder_rejects_non_jdrt_scenario(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="JDRT-"):
        RunRecorder(
            JDRTWorkspace(tmp_path),
            "run_1",
            "Scenario-C",
            1,
            make_parameter_file(tmp_path),
            {},
        )


def test_finalized_run_rejects_more_events(tmp_path: Path) -> None:
    recorder = RunRecorder(
        JDRTWorkspace(tmp_path),
        "run_1",
        "JDRT-P2-L15",
        42,
        make_parameter_file(tmp_path),
        {},
    )
    recorder.finalize("INVALID", {"reason": "technical gate"})

    with pytest.raises(RuntimeError, match="finalized"):
        recorder.append(JDRTEvent(0, "TEST", "entity"))
    with pytest.raises(RuntimeError, match="already finalized"):
        recorder.finalize("FAILED")
