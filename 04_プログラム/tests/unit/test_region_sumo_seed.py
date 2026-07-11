from __future__ import annotations

from pathlib import Path

import p2_region_pipeline as region
import p2_traci_common as common


def test_region_sumo_command_uses_explicit_default_seed() -> None:
    command = region.build_region_sumo_command(
        "sumo",
        Path("scenario_a.sumocfg"),
        "60",
        region.DEFAULT_SUMO_SEED,
    )

    assert region.DEFAULT_SUMO_SEED == 23423
    assert command[-2:] == ["--seed", "23423"]


def test_region_sumo_command_accepts_replication_seed() -> None:
    command = region.build_region_sumo_command(
        "sumo",
        Path("scenario_a.sumocfg"),
        "60",
        42,
    )

    assert command[-2:] == ["--seed", "42"]


def test_archive_copies_input_route_without_removing_it(tmp_path: Path) -> None:
    route = tmp_path / "scenario_a.rou.xml"
    route.write_text("<routes />", encoding="utf-8")

    archived = common.archive_existing_outputs(
        {},
        tmp_path / "archive_runs",
        "scenario_a_full",
        copy_paths={"route_file": route},
    )

    archived_route = Path(archived["route_file"])
    assert route.exists()
    assert archived_route.read_bytes() == route.read_bytes()
    assert archived_route.parent.parent == tmp_path / "archive_runs"
