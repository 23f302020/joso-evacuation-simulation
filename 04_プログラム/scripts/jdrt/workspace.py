"""Active workspace paths for the Joso-only JDRT study."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


JOSO_CITY_CODE = "08211"


@dataclass(frozen=True)
class JDRTWorkspace:
    """Resolve only the active Joso City inputs and JDRT outputs.

    The class intentionally rejects other municipality codes and never scans
    ``output/sumo/regions``.  This keeps archived regional results outside the
    JDRT runtime path.
    """

    program_dir: Path
    city_code: str = JOSO_CITY_CODE

    def __post_init__(self) -> None:
        program_dir = self.program_dir.resolve()
        object.__setattr__(self, "program_dir", program_dir)
        if self.city_code != JOSO_CITY_CODE:
            raise ValueError(
                f"JDRT supports Joso City only: expected {JOSO_CITY_CODE}, "
                f"got {self.city_code}"
            )

    @property
    def region_dir(self) -> Path:
        return self.program_dir / "output" / "sumo" / "regions" / self.city_code

    @property
    def network_dir(self) -> Path:
        return self.region_dir / "network"

    @property
    def derived_dir(self) -> Path:
        return self.region_dir / "derived"

    @property
    def scenarios_dir(self) -> Path:
        return self.region_dir / "scenarios"

    @property
    def evaluation_dir(self) -> Path:
        return self.region_dir / "evaluation"

    @property
    def experiments_dir(self) -> Path:
        return self.region_dir / "experiments"

    @property
    def jdrt_dir(self) -> Path:
        return self.experiments_dir / "jdrt"

    @property
    def runs_dir(self) -> Path:
        return self.jdrt_dir / "runs"

    def ensure_output_dirs(self) -> Path:
        """Create only the JDRT output root and return it."""

        self.runs_dir.mkdir(parents=True, exist_ok=True)
        return self.runs_dir

    def run_dir(self, run_id: str) -> Path:
        if not run_id or run_id in {".", ".."}:
            raise ValueError("run_id must not be empty or relative traversal")
        if any(separator in run_id for separator in ("/", "\\")):
            raise ValueError("run_id must be a single path component")
        return self.runs_dir / run_id

    def iter_run_dirs(self) -> tuple[Path, ...]:
        """List JDRT runs without scanning other experiments or cities."""

        if not self.runs_dir.exists():
            return ()
        return tuple(sorted(path for path in self.runs_dir.iterdir() if path.is_dir()))
