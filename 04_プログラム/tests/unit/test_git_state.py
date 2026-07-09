from __future__ import annotations

import re
import subprocess
from pathlib import Path

from p2_traci_common import git_state


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_git_state_records_repo_and_scripts_dirty_separately(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    program_dir = repo / "04_プログラム"
    scripts_dir = program_dir / "scripts"
    docs_dir = repo / "docs"
    scripts_dir.mkdir(parents=True)
    docs_dir.mkdir()

    (scripts_dir / "tool.py").write_text("VALUE = 1\n", encoding="utf-8")
    (docs_dir / "note.md").write_text("clean\n", encoding="utf-8")
    _git(repo.parent, "init", str(repo))
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")

    clean = git_state(program_dir, scripts_dir)
    assert re.fullmatch(r"[0-9a-f]{40}", clean["git_commit"])
    assert clean["git_dirty_repo"] is False
    assert clean["git_dirty_scripts"] is False
    assert clean["git_scope_path"] == str(scripts_dir.resolve())

    (docs_dir / "note.md").write_text("repo dirty\n", encoding="utf-8")
    repo_dirty = git_state(program_dir, scripts_dir)
    assert repo_dirty["git_dirty_repo"] is True
    assert repo_dirty["git_dirty_scripts"] is False

    (scripts_dir / "tool.py").write_text("VALUE = 2\n", encoding="utf-8")
    scripts_dirty = git_state(repo, scripts_dir)
    assert scripts_dirty["git_dirty_repo"] is True
    assert scripts_dirty["git_dirty_scripts"] is True
    assert scripts_dirty["git_scope_path"] == str(scripts_dir.resolve())
