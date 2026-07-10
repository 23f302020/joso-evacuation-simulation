from __future__ import annotations

import csv
from pathlib import Path

from p3_allocation_shadow_reweighting import allocation_shadow_reweighting


def _write_type_map(path: Path) -> Path:
    fields = ["vehicle_id", "origin_id", "person_type", "arrived"]
    rows = [
        {"vehicle_id": "t3_o1_1", "origin_id": "o1", "person_type": "type3", "arrived": "True"},
        {"vehicle_id": "t3_o1_2", "origin_id": "o1", "person_type": "type3", "arrived": "False"},
        {"vehicle_id": "t4_o1_1", "origin_id": "o1", "person_type": "type4", "arrived": "True"},
        {"vehicle_id": "t3_o2_1", "origin_id": "o2", "person_type": "type3", "arrived": "True"},
        {"vehicle_id": "t3_o2_2", "origin_id": "o2", "person_type": "type3", "arrived": "True"},
        {"vehicle_id": "t4_o2_1", "origin_id": "o2", "person_type": "type4", "arrived": "True"},
        {"vehicle_id": "t4_o2_2", "origin_id": "o2", "person_type": "type4", "arrived": "True"},
        {"vehicle_id": "t4_o2_3", "origin_id": "o2", "person_type": "type4", "arrived": "True"},
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_allocation_shadow_reweighting_splits_composition_and_residual(tmp_path: Path) -> None:
    result = allocation_shadow_reweighting(_write_type_map(tmp_path / "type_map.csv"))
    summary = result["summary"]

    assert summary["type3_completion_rate"] == 0.75
    assert summary["type4_completion_rate"] == 1.0
    assert summary["observed_type4_minus_type3_gap"] == 0.25
    assert summary["type3_reweighted_to_type4_origin_mix"] == 0.875
    assert summary["composition_effect"] == 0.125
    assert summary["within_origin_residual"] == 0.125
    assert summary["composition_share_of_observed_gap"] == 0.5
    assert summary["paired_origin_count"] == 2
