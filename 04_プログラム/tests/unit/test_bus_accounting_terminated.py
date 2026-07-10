from __future__ import annotations

import csv
import json
from typing import Any

import p3_bus_accounting as acc
from p3_correct_bus_passenger_accounting import corrected_bus_accounting


def _bus_unit() -> acc.BusUnit:
    return acc.BusUnit(
        bus_id="bus_std_2",
        vtype="bus_standard",
        capacity=8,
        pickup_stop_id="bs_origin_0084",
        pickup_edge="pickup_edge",
        shelter_id="shelter_5",
        shelter_edge="shelter_edge",
        is_welfare=False,
    )


def _board_one_trip(
    bus: acc.BusUnit,
    rt: acc.BusRuntime,
    *,
    sim_time: int,
) -> None:
    queues = {bus.pickup_stop_id: {"type4": 0, "type3_mob": 0, "type3": 8}}
    stop_meta = {
        bus.pickup_stop_id: {
            "origin_id": "origin_0084",
            "KEY_CODE": "5439071234",
            "shelter_id": bus.shelter_id,
        }
    }
    rt.trip_board_time = sim_time
    boarded = acc.board_passengers(bus, rt, queues, stop_meta, sim_time=sim_time)
    assert len(boarded) == 8


def test_terminated_onboard_passengers_are_not_arrived_sixteen_person_fixture() -> None:
    passenger_rows: list[dict[str, Any]] = []
    bus_rows: list[dict[str, Any]] = []

    for bus_id, trip_seq in (("bus_std_2", 0), ("bus_std_5", 1)):
        bus = _bus_unit()
        bus = acc.BusUnit(**{**bus.__dict__, "bus_id": bus_id})
        rt = acc.BusRuntime(trip_seq=trip_seq)
        _board_one_trip(bus, rt, sim_time=1200 + trip_seq * 1000)
        acc.alight_passengers(
            bus,
            rt,
            sim_time=21600,
            passenger_rows=passenger_rows,
            bus_rows=bus_rows,
            terminated=True,
            termination_reason="closure_unreachable",
        )

    assert len(passenger_rows) == 16
    assert sum(1 for row in passenger_rows if row["arrived"]) == 0
    assert sum(1 for row in passenger_rows if not row["arrived"]) == 16
    assert {row["arrival_time_s"] for row in passenger_rows} == {""}
    assert [row["alight_count"] for row in bus_rows] == [0, 0]
    assert [row["termination_reason"] for row in bus_rows] == [
        "closure_unreachable",
        "closure_unreachable",
    ]


def test_corrected_bus_accounting_reclassifies_terminated_sixteen_person_fixture(tmp_path) -> None:
    passenger_log = tmp_path / "scenario_b_passenger_log.csv"
    bus_log = tmp_path / "scenario_b_bus_log.csv"
    summary = tmp_path / "scenario_b_bus_summary.json"
    passenger_fields = ["passenger_id", "bus_id", "trip_seq", "arrival_time_s", "arrived"]
    bus_fields = ["bus_id", "trip_seq", "boarded_count", "terminated"]

    with passenger_log.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=passenger_fields)
        writer.writeheader()
        for bus_id, trip_seq in (("bus_std_2", "0"), ("bus_std_5", "1")):
            for index in range(8):
                writer.writerow(
                    {
                        "passenger_id": f"{bus_id}_{trip_seq}_{index}",
                        "bus_id": bus_id,
                        "trip_seq": trip_seq,
                        "arrival_time_s": "21600",
                        "arrived": "True",
                    }
                )
        for index in range(125):
            writer.writerow(
                {
                    "passenger_id": f"ok_{index}",
                    "bus_id": "bus_std_1",
                    "trip_seq": "0",
                    "arrival_time_s": "1200",
                    "arrived": "True",
                }
            )

    with bus_log.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=bus_fields)
        writer.writeheader()
        writer.writerow({"bus_id": "bus_std_2", "trip_seq": "0", "boarded_count": "8", "terminated": "True"})
        writer.writerow({"bus_id": "bus_std_5", "trip_seq": "1", "boarded_count": "8", "terminated": "True"})
        writer.writerow({"bus_id": "bus_std_1", "trip_seq": "0", "boarded_count": "125", "terminated": "False"})

    summary.write_text(
        json.dumps(
            {
                "initial_bus_candidate_total": 247,
                "two_layer_report": {"residual_queue_total": 106},
                "run_manifest": {"run_id": "measure_fixture", "sim_end_sec": 21600},
            }
        ),
        encoding="utf-8",
    )

    result = corrected_bus_accounting(
        passenger_log_path=passenger_log,
        bus_log_path=bus_log,
        summary_path=summary,
    )

    assert result["source_boarded_passengers"] == 141
    assert result["corrected_bus_arrived_passengers"] == 125
    assert result["corrected_bus_not_arrived_passengers"] == 16
    assert result["residual_queue_total"] == 106
    assert result["conservation_ok"] is True
