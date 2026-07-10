from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import p3_validate_b_measure_gate as gate
from p3_validate_b_measure_gate import (
    validate_ac2,
    validate_ac5,
    validate_ac6,
    validate_terminated_passenger_accounting,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_validate_ac2_counts_arrived_not_arrived_and_blocked(tmp_path: Path) -> None:
    vehicle_log = tmp_path / "vehicle_log.csv"
    with vehicle_log.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["vehicle_id", "arrived", "departure_blocked_by_closure"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"vehicle_id": "v1", "arrived": "True", "departure_blocked_by_closure": "False"},
                {"vehicle_id": "v2", "arrived": "False", "departure_blocked_by_closure": "False"},
                {"vehicle_id": "v3", "arrived": "False", "departure_blocked_by_closure": "True"},
            ]
        )

    result = validate_ac2(vehicle_log, expected_vehicles=3)
    assert result["ok"] is True
    assert result["arrived"] == 1
    assert result["not_arrived_unblocked"] == 1
    assert result["departure_blocked"] == 1
    assert result["not_arrived_total"] == 2


def test_validate_ac5_checks_manifest_hashes_and_log_times(tmp_path: Path) -> None:
    fcd = _write(
        tmp_path / "fcd.xml",
        """<fcd-export><timestep time="10"><vehicle id="bus_1" /></timestep></fcd-export>""",
    )
    tripinfo = _write(tmp_path / "tripinfo.xml", "<tripinfos></tripinfos>")
    passenger_log = tmp_path / "passenger.csv"
    passenger_log.write_text("board_time_s,arrival_time_s\n1,9\n", encoding="utf-8")
    bus_log = tmp_path / "bus.csv"
    bus_log.write_text("board_time_s,arrive_shelter_time_s\n1,8\n", encoding="utf-8")
    other = _write(tmp_path / "vehicle.csv", "vehicle_id\n")

    summary = {
        "run_manifest": {
            "started_at": "2026-07-10T00:00:00",
            "ended_at": "2026-07-10T00:01:00",
            "git_commit": "a" * 40,
            "git_dirty_scripts": False,
            "git_scope_path": str(tmp_path.resolve()),
            "outputs": {
                "fcd": {"path": str(fcd), "sha256": _sha(fcd), "size_bytes": fcd.stat().st_size},
                "tripinfo": {"path": str(tripinfo), "sha256": _sha(tripinfo), "size_bytes": tripinfo.stat().st_size},
                "passenger_log": {"path": str(passenger_log), "sha256": _sha(passenger_log), "size_bytes": passenger_log.stat().st_size},
                "bus_log": {"path": str(bus_log), "sha256": _sha(bus_log), "size_bytes": bus_log.stat().st_size},
                "vehicle_log": {"path": str(other), "sha256": _sha(other), "size_bytes": other.stat().st_size},
            },
        }
    }

    result = validate_ac5(summary, expected_scope_path=tmp_path)
    assert result["ok"] is True
    assert result["log_time_le_fcd"] is True


def test_validate_ac6_checks_bus_conservation() -> None:
    summary = {
        "bus_boarded_passengers": 8,
        "bus_arrived_passengers": 6,
        "bus_not_arrived_passengers": 2,
        "initial_bus_candidate_total": 10,
        "two_layer_report": {"residual_queue_total": 2},
    }
    assert validate_ac6(summary)["ok"] is True

    broken = dict(summary)
    broken["bus_not_arrived_passengers"] = 1
    assert validate_ac6(broken)["ok"] is False


def test_validate_terminated_passenger_accounting_rejects_arrived_terminal_trip(tmp_path: Path) -> None:
    passenger_log = tmp_path / "passenger.csv"
    passenger_log.write_text(
        "bus_id,trip_seq,arrival_time_s,arrived\nbus_std_2,0,21600,True\n",
        encoding="utf-8",
    )
    bus_log = tmp_path / "bus.csv"
    bus_log.write_text(
        "bus_id,trip_seq,boarded_count,terminated\nbus_std_2,0,1,True\n",
        encoding="utf-8",
    )
    summary = {
        "run_manifest": {
            "sim_end_sec": 21600,
            "outputs": {
                "passenger_log": {"path": str(passenger_log)},
                "bus_log": {"path": str(bus_log)},
            },
        }
    }

    result = validate_terminated_passenger_accounting(summary)

    assert result["ok"] is False
    assert result["terminated_passenger_count"] == 1
    assert result["terminated_arrived_passenger_count"] == 1
    assert result["terminal_arrival_time_arrived_count"] == 1


def test_validate_b_measure_generates_layers_without_total_divergence(monkeypatch, tmp_path: Path) -> None:
    bus_summary = tmp_path / "summary.json"
    bus_summary.write_text(
        json.dumps({"run_manifest": {"outputs": {"vehicle_log": {"path": "vehicle.csv"}}}}),
        encoding="utf-8",
    )
    calls = {"compare": 0}

    monkeypatch.setattr(
        gate,
        "validate_ac2",
        lambda _path, _expected: {"ok": True, "not_arrived_total": 479},
    )
    monkeypatch.setattr(gate, "validate_ac5", lambda _summary, _scope: {"ok": True})
    monkeypatch.setattr(gate, "validate_ac6", lambda _summary: {"ok": True})

    def fake_compare(_city_code: str, _a_scenario: str, _b_scenario: str) -> dict:
        calls["compare"] += 1
        return {
            "a_summary": {"layer_counts": {"physical_isolation": 68}},
            "b_summary": {
                "layer_counts": {
                    "physical_isolation": 68,
                    "intersection_blockage": 24,
                    "queue_behind_blockage": 387,
                }
            },
        }

    monkeypatch.setattr(gate, "compare_stagnation_layers", fake_compare)

    result = gate.validate_b_measure(city_code="08211", bus_summary_path=bus_summary)
    assert calls["compare"] == 1
    assert result["gates_ok"] is True
    assert result["halt_required"] is False
    assert result["layer_comparison"] is not None


def test_validate_b_measure_halts_on_layer1_and_layer2_rules(monkeypatch, tmp_path: Path) -> None:
    bus_summary = tmp_path / "summary.json"
    bus_summary.write_text(
        json.dumps({"run_manifest": {"outputs": {"vehicle_log": {"path": "vehicle.csv"}}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        gate,
        "validate_ac2",
        lambda _path, _expected: {"ok": True, "not_arrived_total": 479},
    )
    monkeypatch.setattr(gate, "validate_ac5", lambda _summary, _scope: {"ok": True})
    monkeypatch.setattr(gate, "validate_ac6", lambda _summary: {"ok": True})
    monkeypatch.setattr(
        gate,
        "compare_stagnation_layers",
        lambda _city_code, _a_scenario, _b_scenario: {
            "a_summary": {"layer_counts": {"physical_isolation": 68}},
            "b_summary": {
                "layer_counts": {
                    "physical_isolation": 10,
                    "intersection_blockage": 50,
                    "queue_behind_blockage": 50,
                }
            },
        },
    )

    result = gate.validate_b_measure(city_code="08211", bus_summary_path=bus_summary)
    assert result["halt_required"] is True
    assert len(result["halt_reasons"]) == 2
    assert "physical_isolation" in result["halt_reason"]
    assert "intersection_blockage" in result["halt_reason"]
