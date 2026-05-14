"""Phase 2 SUMO environment helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path


DEFAULT_SUMO_HOME = (
    Path.home()
    / "AppData"
    / "Local"
    / "Programs"
    / "sumo-1.26.0-msi-extract"
    / "PFiles"
    / "Eclipse"
    / "Sumo"
)


def configure_sumo_environment(require_tools: bool = False) -> Path | None:
    """Add SUMO tools and binaries to the current process when available."""
    candidates: list[Path] = []
    if os.environ.get("SUMO_HOME"):
        candidates.append(Path(os.environ["SUMO_HOME"]))
    candidates.extend(
        [
            DEFAULT_SUMO_HOME,
            Path("C:/Program Files/Eclipse/Sumo"),
            Path("C:/Program Files (x86)/Eclipse/Sumo"),
        ]
    )

    for sumo_home in candidates:
        tools_dir = sumo_home / "tools"
        bin_dir = sumo_home / "bin"
        if not tools_dir.exists() and not bin_dir.exists():
            continue

        os.environ.setdefault("SUMO_HOME", str(sumo_home))
        if tools_dir.exists() and str(tools_dir) not in sys.path:
            sys.path.append(str(tools_dir))
        if bin_dir.exists():
            current_path = os.environ.get("PATH", "")
            bin_text = str(bin_dir)
            if bin_text.lower() not in current_path.lower():
                os.environ["PATH"] = bin_text + os.pathsep + current_path
        return sumo_home

    if require_tools:
        raise RuntimeError("SUMO_HOME is not set and a local SUMO installation was not found.")
    return None
