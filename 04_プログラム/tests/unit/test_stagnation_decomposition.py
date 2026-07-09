from __future__ import annotations

import csv
import json
from pathlib import Path

from p3_stagnation_decomposition import (
    LAYER_INTERSECTION,
    LAYER_PHYSICAL,
    LAYER_QUEUE,
    decompose_stagnation,
    edge_from_lane,
)


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_edge_from_lane_preserves_internal_edge_id() -> None:
    assert edge_from_lane("12365#7_1") == "12365#7"
    assert edge_from_lane(":junction_2_0") == ":junction_2"


def test_decompose_stagnation_classifies_three_layers(tmp_path: Path) -> None:
    vehicle_log = tmp_path / "vehicle_log.csv"
    with vehicle_log.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "vehicle_id",
                "origin_id",
                "KEY_CODE",
                "to_sumo_edge_id",
                "arrived",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"vehicle_id": "v_physical", "origin_id": "o1", "KEY_CODE": "k1", "to_sumo_edge_id": "dest", "arrived": "False"},
                {"vehicle_id": "v_intersection", "origin_id": "o2", "KEY_CODE": "k2", "to_sumo_edge_id": "dest", "arrived": "False"},
                {"vehicle_id": "v_queue", "origin_id": "o3", "KEY_CODE": "k3", "to_sumo_edge_id": "dest", "arrived": "False"},
                {"vehicle_id": "v_arrived", "origin_id": "o4", "KEY_CODE": "k4", "to_sumo_edge_id": "dest", "arrived": "True"},
            ]
        )

    fcd = _write(
        tmp_path / "fcd.xml",
        """<fcd-export>
  <timestep time="100">
    <vehicle id="v_physical" lane="closed_0" speed="0" pos="95" />
    <vehicle id="v_intersection" lane=":j_0_0" speed="0" pos="5" />
    <vehicle id="v_queue" lane="open_0" speed="0" pos="90" />
  </timestep>
</fcd-export>
""",
    )
    net = _write(
        tmp_path / "net.xml",
        """<net>
  <edge id="closed"><lane id="closed_0" length="100" /></edge>
  <edge id="closed_next"><lane id="closed_next_0" length="100" /></edge>
  <edge id="open"><lane id="open_0" length="100" /></edge>
  <edge id="mid"><lane id="mid_0" length="100" /></edge>
  <edge id="dest"><lane id="dest_0" length="100" /></edge>
  <edge id=":j_0" function="internal"><lane id=":j_0_0" length="10" /></edge>
  <connection from="closed" to="closed_next" />
  <connection from="open" to="mid" />
  <connection from="mid" to="dest" />
  <connection from="open" to="dest" via=":j_0_0" />
</net>
""",
    )
    closure = tmp_path / "closure.json"
    closure.write_text(
        json.dumps(
            {
                "closures": [
                    {"sim_time_sec": 50, "closed_sumo_edge_ids": ["closed", "closed_next"]},
                    {"sim_time_sec": 100, "closed_sumo_edge_ids": ["dest"]},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = decompose_stagnation(
        vehicle_log_path=vehicle_log,
        fcd_path=fcd,
        net_xml_path=net,
        closure_timeline_path=closure,
    )
    assert result["summary"]["not_arrived_count"] == 3
    assert result["summary"]["effective_closed_edge_count"] == 2
    assert result["summary"]["layer_counts"] == {
        LAYER_PHYSICAL: 1,
        LAYER_INTERSECTION: 1,
        LAYER_QUEUE: 1,
    }
