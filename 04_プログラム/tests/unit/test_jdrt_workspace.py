from __future__ import annotations

from pathlib import Path

import pytest

from jdrt import JDRTWorkspace, JOSO_CITY_CODE


def test_workspace_is_fixed_to_joso(tmp_path: Path) -> None:
    workspace = JDRTWorkspace(tmp_path)

    assert JOSO_CITY_CODE == "08211"
    assert workspace.region_dir == (
        tmp_path.resolve() / "output" / "sumo" / "regions" / "08211"
    )
    assert workspace.runs_dir == (
        tmp_path.resolve()
        / "output"
        / "sumo"
        / "regions"
        / "08211"
        / "experiments"
        / "jdrt"
        / "runs"
    )


def test_workspace_rejects_other_municipality(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Joso City only"):
        JDRTWorkspace(tmp_path, city_code="08201")


def test_workspace_lists_only_jdrt_run_directories(tmp_path: Path) -> None:
    workspace = JDRTWorkspace(tmp_path)
    workspace.ensure_output_dirs()
    workspace.run_dir("run_b").mkdir()
    workspace.run_dir("run_a").mkdir()

    other_city = (
        tmp_path / "output" / "sumo" / "regions" / "08201" / "experiments"
    )
    other_city.mkdir(parents=True)
    unrelated = workspace.experiments_dir / "scenario_c" / "runs" / "old_run"
    unrelated.mkdir(parents=True)

    assert workspace.iter_run_dirs() == (
        workspace.run_dir("run_a"),
        workspace.run_dir("run_b"),
    )


@pytest.mark.parametrize("run_id", ["", ".", "..", "../escape", "nested/run"])
def test_workspace_rejects_unsafe_run_id(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(ValueError, match="run_id"):
        JDRTWorkspace(tmp_path).run_dir(run_id)
