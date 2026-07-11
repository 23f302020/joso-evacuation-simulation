from __future__ import annotations

from pathlib import Path

import p2_traci_bus as bus


def test_build_sumo_command_uses_explicit_default_seed() -> None:
    command = bus.build_sumo_command(
        Path("scenario_b.sumocfg"),
        "sumo",
        bus.DEFAULT_SUMO_SEED,
    )

    assert bus.DEFAULT_SUMO_SEED == 23423
    assert command[-2:] == ["--seed", "23423"]


def test_build_sumo_command_accepts_replication_seed() -> None:
    command = bus.build_sumo_command(Path("scenario_b.sumocfg"), "sumo", 42)

    assert command[-2:] == ["--seed", "42"]
