from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from p3_validate_b_measure_gate import validate_ac2, validate_ac5, validate_ac6


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
