"""Independent event logs and manifests for Joso City JDRT runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .workspace import JDRTWorkspace, JOSO_CITY_CODE


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class JDRTEvent:
    sim_time_sec: int
    event_type: str
    entity_id: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sim_time_sec < 0:
            raise ValueError("sim_time_sec must be non-negative")
        if not self.event_type.strip():
            raise ValueError("event_type must not be empty")
        if not self.entity_id.strip():
            raise ValueError("entity_id must not be empty")


class RunRecorder:
    """Create one immutable run directory and record its state transitions."""

    def __init__(
        self,
        workspace: JDRTWorkspace,
        run_id: str,
        scenario_id: str,
        seed: int,
        parameter_file: Path,
        input_sha256_by_role: Mapping[str, str],
    ) -> None:
        if not scenario_id.startswith("JDRT-"):
            raise ValueError("scenario_id must use the JDRT- namespace")
        if seed < 0:
            raise ValueError("seed must be non-negative")
        if not parameter_file.is_file():
            raise FileNotFoundError(parameter_file)

        self.run_dir = workspace.run_dir(run_id)
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.events_path = self.run_dir / "events.jsonl"
        self.manifest_path = self.run_dir / "manifest.json"
        self._event_count = 0
        self._finalized = False
        self._manifest: dict[str, Any] = {
            "schema_version": "1.0",
            "run_id": run_id,
            "city_code": JOSO_CITY_CODE,
            "scenario_id": scenario_id,
            "seed": seed,
            "status": "RUNNING",
            "parameter_file": str(parameter_file.resolve()),
            "parameter_sha256": _sha256(parameter_file),
            "input_sha256_by_role": dict(sorted(input_sha256_by_role.items())),
            "event_log": self.events_path.name,
            "event_count": 0,
        }
        self._write_manifest()

    def _write_manifest(self) -> None:
        self.manifest_path.write_text(
            json.dumps(self._manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    def append(self, event: JDRTEvent) -> None:
        if self._finalized:
            raise RuntimeError("cannot append to a finalized run")
        with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(asdict(event), ensure_ascii=False, sort_keys=True) + "\n"
            )
        self._event_count += 1

    def finalize(
        self,
        status: str,
        summary: Mapping[str, Any] | None = None,
    ) -> Path:
        if self._finalized:
            raise RuntimeError("run is already finalized")
        if status not in {"COMPLETED", "INVALID", "FAILED"}:
            raise ValueError("status must be COMPLETED, INVALID, or FAILED")
        self._manifest["status"] = status
        self._manifest["event_count"] = self._event_count
        self._manifest["event_log_sha256"] = (
            _sha256(self.events_path) if self.events_path.exists() else None
        )
        self._manifest["summary"] = dict(summary or {})
        self._write_manifest()
        self._finalized = True
        return self.manifest_path
